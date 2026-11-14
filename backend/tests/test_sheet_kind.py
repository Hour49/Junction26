"""The VLM sheet-kind step (SHEET_KIND=carbon, .agents/exp/vlm-kind.md): the contract's prompt
and rule, the classifier around an inner one, the cache and the spend guard. A fake model; no
network."""

import hashlib
import io
import json
import struct
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from typing import Any, get_args

import pytest
from PIL import Image
from triage_fakes import FakeClassifier

from app.adapters.triage.sheet_kind import (
    ADVANCED_LONG_SIDE,
    KINDS,
    MODEL,
    PLAN_KINDS,
    PNG_SIGNATURE,
    PROMPT_SHA,
    GeminiSheetKindClient,
    SheetKindClassifier,
    SheetKindReader,
    advanced,
    decide,
    long_side,
    price,
)
from app.core.ingest.model import (
    SHEET_PLAN_KINDS,
    Classified,
    Probed,
    Register,
    SheetKindName,
    Triage,
    Unavailable,
)
from app.core.ingest.triage import set_aside_reason, sheet_doubt, sheet_flag
from app.core.spend import SpendGuard
from app.settings import Settings

CUT = 0.9  # the default (settings.sheet_kind_cut)
PNG_PROBED = Probed(kind="png_plan", did="a drawing image")


def form(kind: str, plan: bool, takeoff: bool, confidence: float, **more: Any) -> dict[str, Any]:
    return {
        "seen": "a sheet",
        "sheet_kind": kind,
        "floor_plan_on_sheet": plan,
        "takeoff_possible": takeoff,
        "confidence": confidence,
        "title": None,
        "sheet_number": None,
        "printed_scale": None,
        "advanced": False,
        "advanced_why": None,
    } | more


PIPING = form("mep_plan", False, True, 0.98, title="PIPING PLAN", sheet_number="M-101A")
PLAN = form("architectural_floor_plan", True, True, 0.97, printed_scale="1:100")
SCHEDULE = form("schedule_or_text", False, False, 0.95)
STRUCTURAL_UNSURE = form("structural_plan", False, False, 0.6)


def reply(found: dict[str, Any]) -> dict[str, Any]:
    """A generateContent answer: 2,200 tokens in, 200 out (0.0128 USD at 4 / 20 per M)."""
    return {
        "candidates": [{"content": {"parts": [{"text": json.dumps(found)}]}}],
        "usageMetadata": {"promptTokenCount": 2200, "candidatesTokenCount": 200},
    }


class FakeModel:
    """The sheet-kind model, faked: every call gets `answer` (or raises its error). Counts calls."""

    model = MODEL

    def __init__(self, answer: dict[str, Any] | None = None, error: Exception | None = None):
        self.answer, self.error, self.calls = answer, error, 0

    def ask(self, jpeg: bytes) -> dict[str, Any]:
        self.calls += 1
        assert jpeg.startswith(b"\xff\xd8")  # a JPEG is sent
        if self.error is not None:
            raise self.error
        assert self.answer is not None
        return self.answer


def png(width: int = 64, height: int = 48) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def triage_of(found: Classified) -> Triage:
    """The file's triage record from a classifier's answer, as ingest builds it."""
    fields = found.model_dump()
    fields.pop("cost_usd")
    return Triage.model_validate(fields)


def classifier(
    tmp_path: Path, model: FakeModel, inner: FakeClassifier | None = None
) -> SheetKindClassifier:
    return SheetKindClassifier(inner, SheetKindReader(model, tmp_path / "cache"), CUT)


def test_the_prompt_is_the_contracts_and_the_kinds_are_the_apis() -> None:
    assert PROMPT_SHA == "707beba5467d3b42d3ecdc02612e23030994334433c4f84d0bb5569f0b4da166"
    assert MODEL == "gemini-4-carbon"
    assert set(KINDS) == set(get_args(SheetKindName))
    assert PLAN_KINDS == SHEET_PLAN_KINDS


@pytest.mark.parametrize(
    ("found", "decision"),
    [
        (PIPING, "set_aside"),  # an MEP plan with takeoff true is set aside (draft 2 was not)
        (form("multi_view_sheet", False, False, 0.9), "set_aside"),  # no plan on it
        (SCHEDULE, "set_aside"),
        (STRUCTURAL_UNSURE, "doubt"),  # all signs, under the cut
        (form("architectural_floor_plan", False, False, 0.95), "doubt"),  # a plan kind, no plan
        (form("mep_plan", True, False, 0.9), "doubt"),  # a plan on it, non-plan kind, no takeoff
        (form("architectural_floor_plan", True, False, 0.9), "read"),  # takeoff false alone
        (PLAN, "read"),
    ],
)
def test_the_decision_rule(found: dict[str, Any], decision: str) -> None:
    assert decide(found, CUT) == decision


def test_advanced_is_the_models_flag_unless_the_upload_is_larger_than_the_model_sees() -> None:
    hard = form("architectural_floor_plan", True, True, 0.9, advanced=True, advanced_why="school")
    assert advanced(hard, 3000) == (True, "school")
    assert advanced(PLAN, ADVANCED_LONG_SIDE) == (False, None)
    assert advanced(PLAN, ADVANCED_LONG_SIDE + 1) == (
        True,
        f"large sheet ({ADVANCED_LONG_SIDE + 1} px on its long side)",
    )
    assert advanced(hard, None) == (True, "school")  # a PDF scan: the model's flag


def test_an_mep_plan_is_set_aside_with_its_kind_title_and_number_and_no_register(
    tmp_path: Path,
) -> None:
    model = FakeModel(reply(PIPING))
    found = classifier(tmp_path, model).classify(png(), PNG_PROBED)
    assert isinstance(found, Classified)
    assert (found.class_, found.register_, model.calls) == ("other_drawing", None, 1)
    assert found.p_plan == pytest.approx(0.02)  # 1 - confidence: the model says no plan
    assert found.cost_usd == pytest.approx(0.0128)
    assert found.method == "Gemini sheet kind (gemini-4-carbon, sheet-kind-2)"
    assert found.sheet is not None
    assert (found.sheet.decision, found.sheet.title, found.sheet.sheet_number) == (
        "set_aside",
        "PIPING PLAN",
        "M-101A",
    )
    triage = triage_of(found)
    assert set_aside_reason(triage) == (
        "not a floor plan: a piping, plumbing, ventilation or electrical plan (PIPING PLAN, M-101A)"
    )
    assert sheet_doubt(triage) is None and sheet_flag(triage) is None  # set aside, not doubted


def test_a_schedule_is_set_aside_as_not_a_drawing(tmp_path: Path) -> None:
    found = classifier(tmp_path, FakeModel(reply(SCHEDULE))).classify(png(), PNG_PROBED)
    assert isinstance(found, Classified) and found.class_ == "not_drawing"
    triage = triage_of(found)
    assert set_aside_reason(triage) == "not a floor plan: a schedule, table or text sheet"


def test_a_doubt_is_read_keeps_the_inner_register_and_its_answers_say_so(tmp_path: Path) -> None:
    image = png()
    register = Register(
        kind="floor_plan", has_floor_plan=True, photo_of_sheet=False, scale_shown="bar",
        quality="good", method="fake classifier",
    )  # fmt: skip
    inner = FakeClassifier({}, registers={image: register})
    found = classifier(tmp_path, FakeModel(reply(STRUCTURAL_UNSURE)), inner).classify(
        image, PNG_PROBED
    )
    assert isinstance(found, Classified)
    assert (found.class_, found.register_) == ("floor_plan", register)
    assert found.method == "fake classifier; Gemini sheet kind (gemini-4-carbon, sheet-kind-2)"
    triage = triage_of(found)
    assert sheet_doubt(triage) is None  # a non-plan kind: flagged instead, with its kind
    assert sheet_flag(triage) == (
        "the sheet may not be a floor plan: it looks like a structural plan (foundation, slab, "
        "framing or reinforcement)"
    )
    plan_kind = form("architectural_floor_plan", False, False, 0.9)
    found = classifier(tmp_path / "2", FakeModel(reply(plan_kind))).classify(png(), PNG_PROBED)
    assert isinstance(found, Classified) and found.sheet is not None
    assert sheet_doubt(triage_of(found)) == ("This sheet may not be a floor plan.")
    assert sheet_flag(triage_of(found)) is None  # a plan kind: read, warned, not flagged


def test_a_plan_is_read_with_no_line(tmp_path: Path) -> None:
    found = classifier(tmp_path, FakeModel(reply(PLAN))).classify(png(), PNG_PROBED)
    assert isinstance(found, Classified) and found.sheet is not None
    assert (found.class_, found.p_plan, found.sheet.decision) == ("floor_plan", 0.97, "read")
    assert sheet_doubt(triage_of(found)) is None
    assert sheet_flag(triage_of(found)) is None


def test_no_call_when_the_inner_classifier_already_says_not_a_plan(tmp_path: Path) -> None:
    image, model = png(), FakeModel(reply(PLAN))
    inner = FakeClassifier({image: "not_drawing"})
    found = classifier(tmp_path, model, inner).classify(image, PNG_PROBED)
    assert isinstance(found, Classified)
    assert (found.class_, found.sheet, model.calls) == ("not_drawing", None, 0)


def test_a_failed_call_leaves_the_inner_answer_or_is_unavailable(tmp_path: Path) -> None:
    from app.adapters.raster_ocr.gemini import GeminiError

    model = FakeModel(error=GeminiError("HTTP 503 UNAVAILABLE"))
    inner = FakeClassifier({})
    found = classifier(tmp_path, model, inner).classify(png(), PNG_PROBED)
    assert isinstance(found, Classified)
    assert (found.class_, found.sheet, found.method) == ("floor_plan", None, "fake classifier")
    alone = classifier(tmp_path, model).classify(png(), PNG_PROBED)
    assert alone == Unavailable(note="the sheet-kind model could not answer: HTTP 503 UNAVAILABLE")
    assert not list((tmp_path / "cache").glob("*"))  # nothing cached


def test_a_reply_that_is_not_the_form_is_a_failed_call_and_not_cached(tmp_path: Path) -> None:
    bad = form("floor_plan", True, True, 0.9)  # a kind outside the enum
    found = classifier(tmp_path, FakeModel(reply(bad))).classify(png(), PNG_PROBED)
    assert found == Unavailable(
        note="the sheet-kind model could not answer: the answer is not the sheet-kind form"
    )
    over = form("mep_plan", False, True, 1.5)
    assert isinstance(classifier(tmp_path, FakeModel(reply(over))).classify(png(), PNG_PROBED),
                      Unavailable)  # fmt: skip
    missing = {k: v for k, v in PLAN.items() if k != "advanced"}
    assert isinstance(
        classifier(tmp_path, FakeModel(reply(missing))).classify(png(), PNG_PROBED), Unavailable
    )
    assert not list((tmp_path / "cache").glob("*"))


def test_a_cached_reply_makes_no_call_and_costs_nothing(tmp_path: Path) -> None:
    image, model = png(), FakeModel(reply(PIPING))
    first = classifier(tmp_path, model).classify(image, PNG_PROBED)
    (cached,) = (tmp_path / "cache").glob("*.json")
    assert cached.name.startswith("sheetkind-") and cached.name.endswith(
        f"-{PROMPT_SHA[:12]}-gemini-4-carbon.json"
    )
    assert json.loads(cached.read_text())["usageMetadata"]["promptTokenCount"] == 2200  # whole
    again = classifier(tmp_path, model).classify(image, PNG_PROBED)
    assert isinstance(first, Classified) and isinstance(again, Classified)
    assert (model.calls, again.cost_usd, again.class_) == (1, 0.0, "other_drawing")
    assert again.method == "Gemini sheet kind (gemini-4-carbon, sheet-kind-2, cached)"
    cached.write_text("{")  # a cache file that does not parse is a miss
    classifier(tmp_path, model).classify(image, PNG_PROBED)
    assert model.calls == 2


def test_the_size_rule_reaches_the_stored_sheet(tmp_path: Path) -> None:
    big = png(ADVANCED_LONG_SIDE + 10, 100)
    found = classifier(tmp_path, FakeModel(reply(PLAN))).classify(big, PNG_PROBED)
    assert isinstance(found, Classified) and found.sheet is not None
    assert (found.sheet.advanced, found.sheet.advanced_why) == (
        True,
        f"large sheet ({ADVANCED_LONG_SIDE + 10} px on its long side)",
    )


def test_price_is_carbons_four_and_twenty_per_million() -> None:
    answer = {"usageMetadata": {"promptTokenCount": 1_000_000, "candidatesTokenCount": 500_000,
                                "thoughtsTokenCount": 500_000}}  # fmt: skip
    assert price(answer) == pytest.approx(4.0 + 20.0)


def test_a_spent_budget_sends_nothing_and_a_paid_call_charges_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[int] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        sent.append(1)
        return io.BytesIO(json.dumps(reply(PIPING)).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    spent = GeminiSheetKindClient("test-key-not-real", 5.0, budget=SpendGuard(0))
    found = SheetKindClassifier(None, SheetKindReader(spent, tmp_path), CUT).classify(
        png(), PNG_PROBED
    )
    assert isinstance(found, Unavailable) and "Gemini budget used up" in found.note
    assert sent == []
    guard = SpendGuard(1.0)
    client = GeminiSheetKindClient("test-key-not-real", 5.0, budget=guard)
    found = SheetKindClassifier(None, SheetKindReader(client, tmp_path), CUT).classify(
        png(), PNG_PROBED
    )
    assert isinstance(found, Classified) and sent == [1]
    assert guard.spent_by() == pytest.approx({"gemini sheet kind": 0.0128})


def png_header(width: int, height: int) -> bytes:
    """A PNG's signature, IHDR chunk and an empty IDAT: the size, no pixels."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + body))
        return struct.pack(">I", len(body)) + kind + body + crc

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return PNG_SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"IDAT", b"") + chunk(b"IEND", b"")


def jpeg_sized(width: int, height: int, progressive: bool = False) -> bytes:
    """A real small JPEG whose frame header says `width` x `height`."""
    out = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(out, format="JPEG", progressive=progressive)
    data = bytearray(out.getvalue())
    sof = data.index(b"\xff\xc2" if progressive else b"\xff\xc0")
    data[sof + 5 : sof + 9] = struct.pack(">HH", height, width)
    return bytes(data)


def test_the_size_is_read_from_the_header_even_past_pils_decompression_bomb_limit() -> None:
    huge = png_header(20_000, 10_000)  # 200 Mpx: PIL refuses to open it (limit about 179 Mpx)
    with pytest.raises(Image.DecompressionBombError):
        Image.open(io.BytesIO(huge))
    assert long_side(huge) == 20_000
    assert long_side(jpeg_sized(15_000, 14_000)) == 15_000  # 210 Mpx
    assert long_side(jpeg_sized(3_000, 4_500, progressive=True)) == 4_500
    assert long_side(png(640, 480)) == 640
    assert long_side(b"%PDF-1.7 ...") is None
    assert long_side(b"\xff\xd8\xff") is None  # a truncated JPEG


def test_a_huge_sheet_keeps_the_size_rule(tmp_path: Path) -> None:
    huge = png_header(20_000, 10_000)
    cache = tmp_path / "cache"
    cache.mkdir()
    name = f"sheetkind-{hashlib.sha256(huge).hexdigest()}-{PROMPT_SHA[:12]}-{MODEL}.json"
    (cache / name).write_text(json.dumps(reply(PLAN)))  # replayed: nothing is encoded or sent
    model = FakeModel(reply(PLAN))
    found = SheetKindClassifier(None, SheetKindReader(model, cache), CUT).classify(huge, PNG_PROBED)
    assert isinstance(found, Classified) and found.sheet is not None
    assert (found.sheet.advanced, found.sheet.advanced_why, model.calls) == (
        True,
        "large sheet (20000 px on its long side)",
        0,
    )


def test_the_default_cut_is_the_one_the_gate_run_picked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change it
    assert Settings().sheet_kind_cut == CUT == 0.9
    # 0.85: set aside at the old 0.8, a doubt (read) at 0.9
    assert decide(form("mep_plan", False, True, 0.85), CUT) == "doubt"


class FlakyNetwork:
    """urlopen, faked: raises `errors` in turn, then answers PIPING. Records every request."""

    def __init__(self, *errors: Exception) -> None:
        self.errors, self.calls = list(errors), 0

    def __call__(self, request: urllib.request.Request, timeout: float) -> io.BytesIO:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return io.BytesIO(json.dumps(reply(PIPING)).encode())


@pytest.mark.parametrize(
    "timeout",
    [TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out"))],
)
def test_a_timeout_is_asked_once_more_with_a_warning_and_only_the_answer_is_charged(
    timeout: Exception,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    network = FlakyNetwork(timeout)
    monkeypatch.setattr(urllib.request, "urlopen", network)
    guard = SpendGuard(1.0)
    client = GeminiSheetKindClient("test-key-not-real", 5.0, budget=guard)
    with caplog.at_level("WARNING"):
        found = SheetKindClassifier(None, SheetKindReader(client, tmp_path), CUT).classify(
            png(), PNG_PROBED
        )
    assert isinstance(found, Classified) and found.class_ == "other_drawing"
    assert network.calls == 2
    assert guard.spent_by() == pytest.approx({"gemini sheet kind": 0.0128})  # one paid reply
    assert any("timed out" in record.message and record.levelname == "WARNING"
               for record in caplog.records)  # fmt: skip


def test_a_second_timeout_fails_and_other_errors_are_not_asked_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    network = FlakyNetwork(TimeoutError("timed out"), TimeoutError("timed out"))
    monkeypatch.setattr(urllib.request, "urlopen", network)
    client = GeminiSheetKindClient("test-key-not-real", 5.0, budget=SpendGuard(1.0))
    found = SheetKindClassifier(None, SheetKindReader(client, tmp_path), CUT).classify(
        png(), PNG_PROBED
    )
    assert found == Unavailable(
        note="the sheet-kind model could not answer: no answer: TimeoutError"
    )
    assert network.calls == 2
    for error in (ConnectionResetError("reset"), urllib.error.URLError("no route")):
        network = FlakyNetwork(error)
        monkeypatch.setattr(urllib.request, "urlopen", network)
        found = SheetKindClassifier(None, SheetKindReader(client, tmp_path), CUT).classify(
            png(), PNG_PROBED
        )
        assert isinstance(found, Unavailable) and network.calls == 1


def test_the_budget_is_asked_again_before_the_second_try(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard = SpendGuard(1.0)

    class SpendsThenTimesOut(FlakyNetwork):
        def __call__(self, request: urllib.request.Request, timeout: float) -> io.BytesIO:
            guard.charge(1.0, "another caller")  # the budget runs out while this call waits
            return super().__call__(request, timeout)

    network = SpendsThenTimesOut(TimeoutError("timed out"))
    monkeypatch.setattr(urllib.request, "urlopen", network)
    client = GeminiSheetKindClient("test-key-not-real", 5.0, budget=guard)
    found = SheetKindClassifier(None, SheetKindReader(client, tmp_path), CUT).classify(
        png(), PNG_PROBED
    )
    assert isinstance(found, Unavailable) and "Gemini budget used up" in found.note
    assert network.calls == 1


def test_a_set_aside_sheet_is_never_advanced_and_a_doubt_keeps_the_flag(tmp_path: Path) -> None:
    big = png(ADVANCED_LONG_SIDE + 10, 100)
    hard = PIPING | {"advanced": True, "advanced_why": "dense annotation"}
    found = classifier(tmp_path, FakeModel(reply(hard))).classify(big, PNG_PROBED)
    assert isinstance(found, Classified) and found.sheet is not None
    assert (found.sheet.decision, found.sheet.advanced, found.sheet.advanced_why) == (
        "set_aside",
        False,
        None,
    )
    warned = SheetKindClassifier(
        None, SheetKindReader(FakeModel(reply(hard)), tmp_path / "warn"), CUT, set_aside=False
    ).classify(big, PNG_PROBED)
    assert isinstance(warned, Classified) and warned.sheet is not None
    assert (warned.sheet.decision, warned.sheet.advanced) == ("doubt", True)  # it is read
