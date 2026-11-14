"""The Gemini describer (app/adapters/triage/gemini_describer.py, decision 0010 sections 3 and 8):
how a reply becomes the description form, the reply cache, the cost, what a failed call leaves,
and the contact-data rule. Every test runs on a fake model or a stubbed urlopen: no network, no
partner data (the images and texts are made up)."""

import io
import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pypdfium2
import pytest
from PIL import Image
from triage_fakes import FakeClassifier, steps

from app.adapters.raster_ocr.gemini import GeminiError
from app.adapters.triage import gemini_describer
from app.adapters.triage.gemini_describer import (
    MAX_SIDE,
    GeminiDescribeClient,
    GeminiDescriber,
    cut,
    encode,
    without_contacts,
)
from app.composition import _triage  # pyright: ignore[reportPrivateUsage]
from app.core import cost
from app.core.errors import InvalidInputError
from app.core.ingest.model import (
    Classified,
    Description,
    Probed,
    ProjectContext,
    Register,
    Unavailable,
)
from app.core.ingest.triage import relevance_by_rule, triaged
from app.settings import Settings

KEY = "test-key-0123456789"
USAGE = {"promptTokenCount": 1092, "candidatesTokenCount": 600, "thoughtsTokenCount": 0}
USD = (1092 * 1.50 + 600 * 9.00) / 1e6
NOT_DRAWING = Classified.model_validate(
    {"class": "not_drawing", "p_plan": 0.03, "method": "fake classifier"}
)


@pytest.fixture(autouse=True)
def _cost_put_back() -> Iterator[None]:
    """The describer charges this thread's running cost total, which nothing resets; it is put
    back after each test, since a later test on the thread may compare a cost exactly
    (tests/ingest/test_ingest_triage.py's 0.003 failed as 0.003000000000000001 after this file)."""
    before = cost.spent()
    yield
    cost._local.usd = before  # pyright: ignore[reportPrivateUsage]


def png(width: int = 64, height: int = 48, colour: str = "white") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(out, format="PNG")
    return out.getvalue()


def form(**changes: Any) -> dict[str, Any]:
    found: dict[str, Any] = {
        "detail": "A pen drawing of the south facade of a two-storey timber house, signed.",
        "text": "South elevation of a timber house.",
        "visible_text": "VILLA ESIMERKKI\nETELÄJULKISIVU 1:50",
        "text_seen": ["VILLA ESIMERKKI", "ETELÄJULKISIVU", "1:50"],
        "language": "fi",
        "what_it_is": "drawing",
        "shows_building": True,
        "subject": "south elevation of a two-storey timber house",
    }
    return {**found, **changes}


def answer(reply: dict[str, Any] | str, finish: str = "STOP", usage: Any = None) -> dict[str, Any]:
    text = reply if isinstance(reply, str) else json.dumps(reply)
    parts = [{"text": text}] if text else []
    return {
        "candidates": [{"content": {"parts": parts}, "finishReason": finish}],
        "usageMetadata": USAGE if usage is None else usage,
    }


class FakeModel:
    """Gives its answers in order; an exception is raised instead of returned."""

    name = "fake-flash-minimal"

    def __init__(self, *answers: dict[str, Any] | Exception) -> None:
        self.answers = list(answers)
        self.asked: list[bytes] = []

    def ask(self, jpeg: bytes) -> dict[str, Any]:
        self.asked.append(jpeg)
        found = self.answers.pop(0)
        if isinstance(found, Exception):
            raise found
        return found


def describe(model: FakeModel, tmp_path: Path, image: bytes | None = None) -> Any:
    return GeminiDescriber(model, tmp_path).describe(image or png(), NOT_DRAWING)


def test_a_reply_becomes_the_description_form(tmp_path: Path) -> None:
    found = describe(FakeModel(answer(form())), tmp_path)
    assert isinstance(found, Description)
    assert (found.what_it_is, found.shows_building, found.language) == ("drawing", True, "fi")
    assert found.visible_text == "VILLA ESIMERKKI\nETELÄJULKISIVU 1:50"
    assert found.text_seen == ("VILLA ESIMERKKI", "ETELÄJULKISIVU", "1:50")
    assert found.subject == "south elevation of a two-storey timber house"
    assert found.model == "fake-flash-minimal, describe-4"
    assert found.cost_usd == pytest.approx(USD)


def test_the_cost_comes_from_usage_metadata_and_is_charged(tmp_path: Path) -> None:
    before = cost.spent()
    describe(FakeModel(answer(form())), tmp_path)
    assert cost.spent() - before == pytest.approx(USD)


def test_a_file_is_paid_for_once(tmp_path: Path) -> None:
    model = FakeModel(answer(form()), answer(form(subject="another picture")))
    describer = GeminiDescriber(model, tmp_path)
    first = describer.describe(png(), NOT_DRAWING)
    before = cost.spent()
    again = describer.describe(png(), NOT_DRAWING)
    assert len(model.asked) == 1
    assert isinstance(first, Description) and isinstance(again, Description)
    assert again.subject == first.subject
    assert again.cost_usd == 0.0 and cost.spent() == before  # a cached reply costs nothing
    other = describer.describe(png(colour="black"), NOT_DRAWING)  # other bytes: asked again
    assert isinstance(other, Description) and other.subject == "another picture"
    assert len(model.asked) == 2


def test_the_cache_name_holds_the_sha256_the_prompt_version_and_the_model(tmp_path: Path) -> None:
    import hashlib

    describe(FakeModel(answer(form())), tmp_path)
    [stored] = tmp_path.iterdir()
    assert stored.name.startswith(hashlib.sha256(png()).hexdigest() + "-describe-4-")
    assert stored.name.endswith("-fake-flash-minimal.json")


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        (answer("", finish="RECITATION"), "empty answer (RECITATION)"),
        (answer("{not json"), "not the description form"),
        (answer(form(what_it_is="sculpture")), "not the description form"),
        (answer({k: v for k, v in form().items() if k != "shows_building"}), "not the descr"),
        (answer(form(text_seen="VILLA ESIMERKKI")), "not the description form"),
    ],
)
def test_an_unusable_reply_is_unavailable_charged_and_not_cached(
    tmp_path: Path, reply: dict[str, Any], said: str
) -> None:
    model = FakeModel(reply, answer(form()))
    before = cost.spent()
    found = describe(model, tmp_path)
    assert isinstance(found, Unavailable)
    assert said in found.note and found.note.startswith("the describer could not answer")
    assert cost.spent() - before == pytest.approx(USD)  # it was paid for all the same
    assert not list(tmp_path.iterdir())
    assert isinstance(describe(model, tmp_path), Description)  # asked again, not a cached failure


def test_a_failed_call_is_unavailable(tmp_path: Path) -> None:
    found = describe(FakeModel(GeminiError("HTTP 429 RESOURCE_EXHAUSTED")), tmp_path)
    assert found == Unavailable(note="the describer could not answer: HTTP 429 RESOURCE_EXHAUSTED")


def test_a_file_that_is_not_an_image_is_unavailable_without_a_call(tmp_path: Path) -> None:
    model = FakeModel()
    found = describe(model, tmp_path, image=b"not an image at all")
    assert isinstance(found, Unavailable) and "could not be opened" in found.note
    assert model.asked == []


@pytest.mark.parametrize("word", ["null", "None", ""])
def test_the_word_null_as_language_is_no_language(tmp_path: Path, word: str) -> None:
    found = describe(FakeModel(answer(form(language=word))), tmp_path)
    assert isinstance(found, Description) and found.language is None


def test_long_texts_are_cut_to_the_form_limits(tmp_path: Path) -> None:
    lines = "\n".join(f"LABEL {n:04d} " + "X" * 40 for n in range(100))  # 5,000 characters
    reply = form(
        visible_text=lines, detail="word " * 1000, text_seen=[f"item {n}" for n in range(25)]
    )
    found = describe(FakeModel(answer(reply)), tmp_path)
    assert isinstance(found, Description)
    assert len(found.visible_text) <= 2000 and found.visible_text.endswith("X")  # a whole line
    assert len(found.detail) <= 4000
    assert found.text_seen == tuple(f"item {n}" for n in range(20))


def test_cut_keeps_whole_lines_and_short_texts() -> None:
    assert cut("short", 10) == "short"
    assert cut("one line\ntwo line", 12) == "one line"
    assert cut("no line breaks here", 12) == "no line"


@pytest.mark.parametrize(
    ("printed", "kept"),
    [
        (
            "ARKKITEHTITOIMISTO ESIMERKKI\nPUH 123456\nHELSINKI",
            "ARKKITEHTITOIMISTO ESIMERKKI\nHELSINKI",
        ),
        ("LISÄTIETOJA ANTAA PUH. 12 34 56", "LISÄTIETOJA ANTAA"),
        ("Tel.: (09) 123 4567", ""),
        ("Telefon 0211-12345, Fax 0211-12346", ","),
        ("Puhelin +358 9 123 4567", ""),
        ("call +358 40 123 4567 today", "call today"),
        ("toimisto@example.fi", ""),
        ("Mail: arkkitehti.esimerkki@toimisto.example.com.", "Mail: ."),
        ("office 09-123 4567.", "office ."),
        ("040-123 4567", ""),
    ],
)
def test_phone_numbers_and_email_addresses_are_dropped(printed: str, kept: str) -> None:
    assert without_contacts(printed) == kept


@pytest.mark.parametrize(
    "printed",
    [
        "ESIMERKKIKATU 18 A 2 00130 HELSINKI 13",  # a street address stays (relevance uses it)
        "+23.43\n+108.65\n+-000\n-050",  # levels
        "1:100 ja 1:20\n12.3.1954\n4.1.78",  # scales and dates
        "3600 2400 1200 900",  # a row of dimensions
        "PUHDISTUSHUONEEN PIIRUSTUS",  # a word that starts like the phone label
        "Mobile, Alabama 1934\nTel Aviv",  # a label word with no number after it
        "SEC @ BENCH SUPPORTS",
        "DRAWING NO 05-1954",
        "VAIHTOEHTO 2A+2B 1:2000",
    ],
)
def test_text_that_is_not_contact_data_stays(printed: str) -> None:
    assert without_contacts(printed) == printed


def test_contact_data_leaves_every_text_field(tmp_path: Path) -> None:
    reply = form(
        visible_text="VILLA ESIMERKKI\nPUH 123456\ntoimisto@example.fi",
        detail="The title block gives the office's phone, PUH 123456, and toimisto@example.fi.",
        text="A sheet by an office (PUH 123456).",
        text_seen=["VILLA ESIMERKKI", "PUH 123456", "toimisto@example.fi"],
    )
    found = describe(FakeModel(answer(reply)), tmp_path)
    assert isinstance(found, Description)
    every = json.dumps(found.model_dump(), ensure_ascii=False)
    assert "123456" not in every and "@" not in every
    assert found.visible_text == "VILLA ESIMERKKI"
    assert found.text_seen == ("VILLA ESIMERKKI",)


def test_the_request_is_the_measured_one_and_the_key_stays_in_a_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[urllib.request.Request] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        sent.append(request)
        return io.BytesIO(json.dumps(answer(form())).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    reply = GeminiDescribeClient(KEY, 30.0).ask(b"jpeg")
    assert reply["usageMetadata"] == USAGE
    [request] = sent
    assert KEY not in request.full_url and request.full_url.endswith(
        "/gemini-3.5-flash:generateContent"
    )
    assert request.get_header("X-goog-api-key") == KEY
    assert isinstance(request.data, bytes)
    config = json.loads(request.data)["generationConfig"]
    assert config["temperature"] == 0.2 and config["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert config["responseSchema"]["properties"]["what_it_is"]["enum"] == [
        "photograph", "artwork", "text_page", "object", "music", "map", "drawing", "other"
    ]  # fmt: skip


def test_an_http_error_names_its_status_never_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        body = io.BytesIO(json.dumps({"error": {"status": "RESOURCE_EXHAUSTED"}}).encode())
        raise urllib.error.HTTPError(request.full_url, 429, "quota", {}, body)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(GeminiError) as raised:
        GeminiDescribeClient(KEY, 30.0).ask(b"jpeg")
    assert str(raised.value) == "HTTP 429 RESOURCE_EXHAUSTED"


def test_an_empty_key_is_refused_at_startup() -> None:
    with pytest.raises(InvalidInputError):
        GeminiDescribeClient("", 30.0)


def test_the_image_is_sent_as_a_jpeg_at_most_2048_px_and_never_enlarged() -> None:
    with Image.open(io.BytesIO(encode(png(4096, 1024)))) as big:
        assert (big.format, big.size) == ("JPEG", (MAX_SIDE, 512))
    with Image.open(io.BytesIO(encode(png(300, 200)))) as small:
        assert small.size == (300, 200)


def test_a_pdf_scan_sends_its_first_page() -> None:
    pdf = pypdfium2.PdfDocument.new()
    pdf.new_page(600, 400)
    pdf.new_page(400, 600)  # page 2 is upright: the landscape answer is page 1
    out = io.BytesIO()
    pdf.save(out)
    pdf.close()
    with Image.open(io.BytesIO(encode(out.getvalue()))) as page:
        assert (page.format, page.size) == ("JPEG", (MAX_SIDE, 1366))


def test_a_museum_object_drawing_is_not_a_drawing_and_unrelated(tmp_path: Path) -> None:
    """Orchestrator, 2026-11-14: the answer key wins for an object's design sheet (a chalice):
    the classifier's not_architecture makes it not_drawing; the describer may call it a drawing,
    but it shows no building, so with nothing shared the rule calls it unrelated."""
    chalice = png(colour="gold")
    sheet = Register(kind="not_architecture", has_floor_plan=False, photo_of_sheet=False,
                     scale_shown="none", quality="good", method="fake classifier")  # fmt: skip
    reply = form(
        detail="An ink and wash design for a chalice with a knotted stem, front view.",
        text="A design drawing of a chalice.",
        visible_text="Kalk für die Stadtkirche",
        text_seen=["Kalk für die Stadtkirche"],
        language="de",
        what_it_is="drawing",
        shows_building=False,
        subject="design drawing of a chalice",
    )
    describer = GeminiDescriber(FakeModel(answer(reply)), tmp_path)
    found = triaged(
        steps(FakeClassifier({}, registers={chalice: sheet}), describer),  # type: ignore[arg-type]
        chalice,
        Probed(kind="png_plan", did="a PNG"),
        "png",
    ).triage
    assert found is not None and found.class_ == "not_drawing"
    assert found.description is not None
    assert (found.description.what_it_is, found.description.shows_building) == ("drawing", False)
    context = ProjectContext(
        plans=("d1",),
        project_name="Rivitalo Esimerkki",
        plan_text=("MH", "OH", "KEITTIÖ"),
        file_names=("plans/a.pdf",),
        descriptions=(),
    )
    assert relevance_by_rule(found.description, context).verdict == "unrelated"


def test_triage_describer_gemini_builds_the_gemini_describer(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        triage_classifier="rules",
        triage_describer="gemini",
        gemini_api_key=KEY,  # type: ignore[arg-type]
        triage_describer_cache_dir=tmp_path,
    )
    found = _triage(settings)
    assert found is not None and isinstance(found.describer, GeminiDescriber)
    assert "describer=gemini" in found.name
    off = _triage(Settings(_env_file=None, triage_classifier="rules"))  # type: ignore[call-arg]
    assert off is not None and off.describer is None


def test_the_prompt_is_describe_4_as_measured() -> None:
    # The measured numbers hold only for this prompt and schema: a change needs a new version
    assert gemini_describer.PROMPT_VERSION == "describe-4"
    assert gemini_describer.PROMPT_SHA.startswith("29b9a883250f")  # describe.py, 2026-11-14
