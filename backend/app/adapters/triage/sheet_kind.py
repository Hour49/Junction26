"""The VLM sheet-kind step (SHEET_KIND=carbon): one gemini-4-carbon call per uploaded image says
what the sheet is, so a piping or foundation plan is not read as a floor plan
(.agents/exp/vlm-kind.md, .agents/exp/hard-photos.md).

It is a triage `Classifier` around the configured one (`inner`, or none):

1. `inner` answers first. A file it calls not a floor plan stays so and nothing is sent: the step
   only looks at files that would otherwise be read, so it can set aside more, never fewer.
2. Otherwise the model is asked (the cache first). A failed call, or a spent Gemini budget, leaves
   `inner`'s answer; with no `inner` it is `Unavailable` ("triage not available: <why>; read as
   today").
3. `decide`: set aside only a sheet the model says has no floor plan, with a kind other than
   architectural_floor_plan, at confidence >= the cut; any other "not a plan" sign is a doubt
   (read, and its answers say so); else read. `advanced` (the model's flag, or an upload over
   4,000 px on its long side) is recorded for the Carbon reader (r8 AS-2); nothing reads it yet.

PROMPT, SCHEMA, KINDS, PLAN_KINDS, `decide` and `advanced` are prototypes/sheet-kind/contract.py's
(sheet-kind-2, frozen 2026-11-14 17:29), word for word, and PROMPT_SHA is pinned by a test. The
model is Carbon (Bogdan, 2026-11-14 17:2x: "Carbon first"; r8 section AS-1). Its price is not
confirmed (third-party pages: 2 / 10 USD per M tokens in / out, introductory until 2026-11-30,
then 4 / 20), so every call is charged at 4 / 20 to the trace and the spend guard.

Replies are cached whole, as generateContent gave them (`usageMetadata` included), by the uploaded
file's sha256, the prompt hash and the model, so a file is paid for once. A cache file that does
not parse is a miss; only a reply that parses is cached.
"""

import base64
import hashlib
import http.client
import json
import logging
import re
import struct
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from PIL import Image

from app.adapters.raster_ocr.gemini import URL, GeminiError, _status, reply_text
from app.adapters.triage.gemini_describer import encode
from app.adapters.whole_file import write_whole
from app.core import cost
from app.core.errors import InvalidInputError
from app.core.ingest.model import (
    Classified,
    Probed,
    Sheet,
    SheetDecision,
    TriageClass,
    Unavailable,
)
from app.core.ingest.ports import Classifier
from app.core.spend import SpendGuard

log = logging.getLogger(__name__)

VERSION = "sheet-kind-2"  # change it with PROMPT, SCHEMA or the image encoding
MODEL = "gemini-4-carbon"
THINKING = "low"
TEMPERATURE = 0.2
MAX_TOKENS = 2048
MAX_SIDE = 3072  # long side of the JPEG sent, pixels (Lanczos, never enlarged)
# px of the uploaded image; above it the sheet is advanced whatever the model says
ADVANCED_LONG_SIDE = 4000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# JPEG start-of-frame markers (baseline, progressive, ...; not DHT C4, JPG C8, DAC CC)
SOF_MARKERS = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
USD_PER_M_INPUT, USD_PER_M_OUTPUT = 4.0, 20.0  # Carbon after 2026-11-30 (unconfirmed)
CHARGED_AS = "gemini sheet kind"
UNAVAILABLE = "the sheet-kind model could not answer"

KINDS = {
    "architectural_floor_plan": "a floor plan",
    "multi_view_sheet": "a sheet with several views",
    "mep_plan": "a piping, plumbing, ventilation or electrical plan",
    "structural_plan": "a structural plan (foundation, slab, framing or reinforcement)",
    "roof_or_ceiling_plan": "a roof plan or ceiling plan",
    "site_plan_or_map": "a site plan or map",
    "elevation": "an elevation",
    "section": "a section",
    "detail": "a construction detail",
    "perspective_or_axonometric": "a perspective or 3D view",
    "schedule_or_text": "a schedule, table or text sheet",
    "not_a_drawing": "not a drawing",
    "other": "another kind of drawing",
}  # the words are the ones a set-aside reason shows

PROMPT = (
    "You are looking at one sheet that someone uploaded to a tool that counts rooms, "
    "doors, windows and fixtures on architectural floor plans. It may be a scan, an image "
    "export or a camera photo. Say what the sheet is. Answer in JSON.\n"
    "\n"
    "Definitions:\n"
    "- An architectural floor plan shows a floor of a building from above so that its "
    "rooms or spaces can be told apart: walls and door openings, usually windows, often "
    "room names, furniture or fixtures. Old, hand-drawn, sketched, coloured, concept, "
    "photographed, rotated, faded or partly damaged plans all count. So do plans of "
    "churches, castles, halls, barns and other buildings with few rooms.\n"
    "- A plan where the building's walls are only the background for something else is "
    "NOT an architectural floor plan: piping, plumbing, heating, ventilation, electrical "
    "or fire protection plans (mep_plan); foundation, slab, framing or reinforcement "
    "plans (structural_plan); roof plans and reflected ceiling plans "
    "(roof_or_ceiling_plan); site plans, town plans and maps that show buildings only as "
    "outlines (site_plan_or_map).\n"
    "- multi_view_sheet: several views on one sheet (for example plans with elevations or "
    "sections), none of them the clear main content.\n"
    "\n"
    "Fields:\n"
    "- seen: one sentence on what is drawn.\n"
    "- sheet_kind: the one kind that fits the sheet best.\n"
    "- floor_plan_on_sheet: true if an architectural floor plan, as defined above, is "
    "drawn anywhere on the sheet, even small, even beside elevations, sections or "
    "details, even inside a site plan when the rooms are drawn. false otherwise.\n"
    "- takeoff_possible: true if a person could count the rooms and doors of a building "
    "floor from this sheet.\n"
    "- confidence: from 0 to 1, how sure you are of floor_plan_on_sheet. When the sheet "
    "is hard to judge, say what you think and give a low number.\n"
    "- title: the sheet title as printed in the title block or caption, else null. Never "
    "a private person's name, address or phone number.\n"
    "- sheet_number: as printed, else null.\n"
    '- printed_scale: the scale as printed (for example "1:100" or "1/4 in = 1 ft"), '
    '"bar" when only a scale bar is drawn, else null.\n'
    "- advanced: false when floor_plan_on_sheet is false, and false for a clean scan or "
    "export of one small residential floor plan. true when the floor plan is harder than "
    "that for any of these reasons: several floor plans on one sheet; a large or dense "
    "sheet where doors and fixtures are tiny; a colour or concept plan; a building that "
    "is not a home (school, office, hospital, dormitory, church, factory); dense "
    "annotation or dimensions over the plan; a camera photo of a plan; a hand-drawn plan.\n"
    "- advanced_why: the reason in a few words when advanced is true, else null."
)

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "seen": {"type": "STRING"},
        "sheet_kind": {"type": "STRING", "enum": list(KINDS)},
        "floor_plan_on_sheet": {"type": "BOOLEAN"},
        "takeoff_possible": {"type": "BOOLEAN"},
        "confidence": {"type": "NUMBER"},
        "title": {"type": "STRING", "nullable": True},
        "sheet_number": {"type": "STRING", "nullable": True},
        "printed_scale": {"type": "STRING", "nullable": True},
        "advanced": {"type": "BOOLEAN"},
        "advanced_why": {"type": "STRING", "nullable": True},
    },
    "required": ["seen", "sheet_kind", "floor_plan_on_sheet", "takeoff_possible", "confidence",
                 "title", "sheet_number", "printed_scale", "advanced", "advanced_why"],
    "propertyOrdering": ["seen", "sheet_kind", "floor_plan_on_sheet", "takeoff_possible",
                         "confidence", "title", "sheet_number", "printed_scale", "advanced",
                         "advanced_why"],
}  # fmt: skip

PROMPT_SHA = hashlib.sha256((PROMPT + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()

PLAN_KINDS = frozenset({"architectural_floor_plan", "multi_view_sheet"})
NOT_DRAWING = frozenset({"not_a_drawing", "schedule_or_text"})  # set aside as not_drawing


def decide(form: dict[str, Any], cut: float) -> SheetDecision:
    """ "read", "doubt" or "set_aside" for one parsed reply.

    Set aside only when the model says: no floor plan on the sheet, a kind other than
    architectural_floor_plan, and confidence >= cut. A sheet it calls no floor plan but that is
    not set aside is a doubt, and so is one it calls a plan while giving it a non-plan kind and
    no takeoff: the sheet is read and its answers say so. The rest is read.

    (The contract's `strict` row, which also needs takeoff_possible false, is scored, not built.)"""
    no_plan = form["floor_plan_on_sheet"] is False
    no_takeoff = form["takeoff_possible"] is False
    kind = form["sheet_kind"]
    if no_plan and kind != "architectural_floor_plan":
        return "set_aside" if float(form["confidence"]) >= cut else "doubt"
    if no_plan or (no_takeoff and kind not in PLAN_KINDS):
        return "doubt"
    return "read"


def advanced(form: dict[str, Any], long_side_px: int | None) -> tuple[bool, str | None]:
    """The routing flag for the Carbon reader (brief AS-2): the model's, or the size rule. The
    model sees a 3,072 px copy, so a larger upload is advanced whatever it says. `long_side_px`
    None: not known (a PDF scan), the model's flag alone."""
    if long_side_px is not None and long_side_px > ADVANCED_LONG_SIDE:
        return True, f"large sheet ({long_side_px} px on its long side)"
    return bool(form["advanced"]), form["advanced_why"] if form["advanced"] else None


def long_side(data: bytes) -> int | None:
    """The uploaded image's long side in pixels, read from its PNG or JPEG header alone (no pixel
    is decoded and PIL's decompression-bomb limit does not apply, so the largest sheets keep the
    size rule); None for a PDF, another format or a header that does not parse."""
    if data.startswith(PNG_SIGNATURE) and data[12:16] == b"IHDR" and len(data) >= 24:
        return max(struct.unpack(">II", data[16:24]))
    if data.startswith(b"\xff\xd8"):
        return _jpeg_long_side(data)
    return None


def _jpeg_long_side(data: bytes) -> int | None:
    """The size in a JPEG's start-of-frame segment, walking the segments from the start."""
    at = 2
    while at + 4 <= len(data):
        if data[at] != 0xFF:
            return None
        marker = data[at + 1]
        if marker == 0xFF:  # fill byte
            at += 1
            continue
        if marker in (0x01, *range(0xD0, 0xD8)):  # segments with no length
            at += 2
            continue
        length = int.from_bytes(data[at + 2 : at + 4], "big")
        if marker in SOF_MARKERS and at + 9 <= len(data):
            height, width = struct.unpack(">HH", data[at + 5 : at + 9])
            return max(height, width)
        if marker == 0xDA or length < 2:  # image data starts: no frame header before it
            return None
        at += 2 + length
    return None


def price(answer: dict[str, Any]) -> float:
    """Dollars of one reply from its `usageMetadata`, at Carbon's 4 / 20 USD per M tokens."""
    usage = answer.get("usageMetadata") or {}
    tokens_in = int(usage.get("promptTokenCount", 0))
    tokens_out = int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
    return (tokens_in * USD_PER_M_INPUT + tokens_out * USD_PER_M_OUTPUT) / 1e6


def request_body(jpeg: bytes) -> dict[str, Any]:
    image = {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(jpeg).decode()}}
    return {
        "contents": [{"parts": [image, {"text": PROMPT}]}],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": MAX_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "thinkingConfig": {"thinkingLevel": THINKING},
        },
    }


def form_of(answer: dict[str, Any]) -> dict[str, Any]:
    """The reply's form; raises GeminiError when it is not the schema's form (a missing field, a
    kind outside the enum, a confidence outside 0 to 1, a field of the wrong type)."""
    try:
        form = json.loads(reply_text(answer))
    except json.JSONDecodeError:
        raise GeminiError("the answer is not JSON") from None
    if not isinstance(form, dict):
        raise GeminiError("the answer is not the sheet-kind form")
    form = cast(dict[str, Any], form)
    missing = [key for key in cast(list[str], SCHEMA["required"]) if key not in form]
    if missing:
        raise GeminiError(f"the answer has no {', '.join(missing)}")
    confidence = form["confidence"]
    wrong = (
        form["sheet_kind"] not in KINDS
        or not isinstance(form["floor_plan_on_sheet"], bool)
        or not isinstance(form["takeoff_possible"], bool)
        or isinstance(confidence, bool)
        or not isinstance(confidence, int | float)
        or not 0 <= confidence <= 1
        or not isinstance(form["seen"], str)
        or not isinstance(form["advanced"], bool)
        or any(form[key] is not None and not isinstance(form[key], str)
               for key in ("title", "sheet_number", "printed_scale", "advanced_why"))
    )  # fmt: skip
    if wrong:
        raise GeminiError("the answer is not the sheet-kind form")
    return form


class SheetKindModel(Protocol):
    @property
    def model(self) -> str: ...

    def ask(self, jpeg: bytes) -> dict[str, Any]:
        """The generateContent answer about the JPEG; raises `GeminiError`."""
        ...


class GeminiSheetKindClient:
    def __init__(
        self,
        api_key: str,
        timeout_s: float,
        model: str = MODEL,
        budget: SpendGuard | None = None,
    ) -> None:
        if not api_key:
            raise InvalidInputError("GEMINI_API_KEY is empty: SHEET_KIND=carbon needs a key")
        self._key = api_key
        self.model = model
        self._timeout = timeout_s
        self._budget = budget  # GEMINI_BUDGET_USD (app/core/spend.py); None: no limit

    def __repr__(self) -> str:
        return f"GeminiSheetKindClient({self.model})"

    def ask(self, jpeg: bytes) -> dict[str, Any]:
        """One request, asked once more when it times out (rag's pilot: 1 of 10 calls timed out
        at 120 s and answered in 9 s the second time); any other failure is not repeated. The
        budget is checked before each request, and only a reply is charged."""
        for attempt in (1, 2):
            if self._budget is not None and (refused := self._budget.exhausted()):
                raise GeminiError(refused)
            try:
                answer = self._post(jpeg)
            except TimeoutError:
                if attempt == 2:
                    raise GeminiError("no answer: TimeoutError") from None
                log.warning("the sheet-kind call timed out after %.0f s; asked once more",
                            self._timeout)  # fmt: skip
                continue
            if self._budget is not None:  # the reader charges the thread's trace (`cost`) itself
                self._budget.charge(price(answer), CHARGED_AS)
            return answer
        raise AssertionError("unreachable")

    def _post(self, jpeg: bytes) -> dict[str, Any]:
        """The generateContent answer; raises TimeoutError on a timeout, else `GeminiError`."""
        request = urllib.request.Request(
            f"{URL}/{self.model}:generateContent",
            data=json.dumps(request_body(jpeg)).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._key},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise GeminiError(f"HTTP {error.code} {_status(error)}".strip()) from None
        except urllib.error.URLError as error:  # a timeout while connecting comes wrapped
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError(str(error.reason)) from None
            raise GeminiError(f"no answer: {type(error).__name__}") from None
        except TimeoutError:  # while reading the reply
            raise
        except (OSError, http.client.HTTPException) as error:  # resets, refused connections
            raise GeminiError(f"no answer: {type(error).__name__}") from None
        except json.JSONDecodeError:
            raise GeminiError("the answer is not JSON") from None


@dataclass(frozen=True)
class SheetReply:
    form: dict[str, Any]
    usd: float  # 0 from the cache
    model: str
    said: str  # "gemini-4-carbon, sheet-kind-1" (+ ", cached")


class SheetKindReader:
    """One reply per uploaded file, cached by its bytes."""

    def __init__(self, model: SheetKindModel, cache_dir: Path) -> None:
        self._model = model
        self._cache = cache_dir

    def read(self, data: bytes) -> SheetReply | Unavailable:
        digest = hashlib.sha256(data).hexdigest()
        name = f"sheetkind-{digest}-{PROMPT_SHA[:12]}-{self._model.model}.json"
        path = self._cache / re.sub(r"[^A-Za-z0-9.-]", "_", name)
        model = self._model.model
        said = f"{model}, {VERSION}"
        if path.is_file():
            try:
                return SheetReply(
                    form_of(json.loads(path.read_text())), 0.0, model, f"{said}, cached"
                )
            except (OSError, ValueError, GeminiError) as error:
                log.warning("the cached reply %s could not be read (%s), so it is asked again",
                            path.name, error)  # fmt: skip
        try:
            jpeg = encode(data, MAX_SIDE)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            return Unavailable(note=f"{UNAVAILABLE}: the image could not be opened ({error})")
        try:
            answer = self._model.ask(jpeg)
        except GeminiError as error:
            return Unavailable(note=f"{UNAVAILABLE}: {error}")
        usd = price(answer)
        cost.charge(usd)  # a call that was paid for counts even when its reply is unusable
        try:
            form = form_of(answer)
        except GeminiError as error:
            return Unavailable(note=f"{UNAVAILABLE}: {error}")
        write_whole(path, json.dumps(answer, ensure_ascii=False))
        return SheetReply(form, usd, model, said)


def sheet_of(found: SheetReply, image: bytes, cut: float, set_aside: bool = True) -> Sheet:
    """The reply as `Triage.sheet` holds it, with its decision at `cut`; with `set_aside` false
    (SHEET_KIND_SET_ASIDE) a sheet it would set aside is a doubt: read, and flagged."""
    form = found.form
    decision = decide(form, cut)
    if decision == "set_aside" and not set_aside:
        decision = "doubt"
    # a set-aside sheet is not read, so it routes no reader (hardphotos: the size rule marked
    # 13 of 14 set-aside non-plans advanced)
    hard, why = (False, None) if decision == "set_aside" else advanced(form, long_side(image))
    return Sheet(
        kind=form["sheet_kind"],
        kind_words=KINDS[form["sheet_kind"]],
        decision=decision,
        takeoff_possible=form["takeoff_possible"],
        confidence=float(form["confidence"]),
        title=form["title"],
        sheet_number=form["sheet_number"],
        printed_scale=form["printed_scale"],
        advanced=hard,
        advanced_why=why,
        seen=form["seen"],
        model=found.model,
    )


class SheetKindClassifier:
    """The `Classifier` port (app/core/ingest/ports.py): `inner`, then the sheet-kind model."""

    def __init__(
        self,
        inner: Classifier | None,
        reader: SheetKindReader,
        cut: float,
        set_aside: bool = True,
    ) -> None:
        self._inner = inner
        self._reader = reader
        self._cut = cut
        self._set_aside = set_aside  # False (SHEET_KIND_SET_ASIDE): warn only, never set aside

    def classify(self, image: bytes, probed: Probed) -> Classified | Unavailable:
        before = None if self._inner is None else self._inner.classify(image, probed)
        if isinstance(before, Classified) and before.class_ != "floor_plan":
            return before  # not a plan already: no call
        found = self._reader.read(image)
        if isinstance(found, Unavailable):
            return before if isinstance(before, Classified) else found
        form = found.form
        sheet = sheet_of(found, image, self._cut, self._set_aside)
        decision = sheet.decision
        method = f"Gemini sheet kind ({found.said})"
        if isinstance(before, Classified):
            method = f"{before.method}; {method}"
        elif isinstance(before, Unavailable):
            method = f"{method}; {before.note}"
        p_plan = sheet.confidence if form["floor_plan_on_sheet"] else 1 - sheet.confidence
        fields: dict[str, Any] = {
            "p_plan": p_plan,
            "method": method,
            "cost_usd": found.usd + (before.cost_usd if isinstance(before, Classified) else 0.0),
            "sheet": sheet,
        }
        if decision == "set_aside":  # `class_of` would make the register a floor plan again
            kind: TriageClass = "not_drawing" if sheet.kind in NOT_DRAWING else "other_drawing"
            return Classified.model_validate({**fields, "class": kind})
        register = before.register_ if isinstance(before, Classified) else None
        return Classified.model_validate({**fields, "class": "floor_plan", "register": register})
