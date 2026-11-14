"""File triage at ingest (decision 0010, board #152): every image is asked "is this a floor
plan?" before any reader; a non-plan is kept, set aside, described, and judged against the
project once its plans are read. Off by default, and then ingest is as before."""

import io
import zipfile

from conftest import MakeService
from test_vector_pdf import swiss_sheet
from triage_fakes import FakeClassifier, FakeDescriber, WordJudge, steps

from app.core.ingest.model import FileStatus, Probed, ProjectStatus
from app.core.ingest.triage import NO_PLAN, NOTE_NO_DESCRIBER, NOTE_NO_JUDGE
from scripts.make_sample_archive import jpeg_bytes, png_bytes, raster_plan, site_photo

PLAN = swiss_sheet().pdf()  # a vector plan with room labels (Küche, Bad, Balkon...)
SCAN = png_bytes(raster_plan())  # a drawing as an image
PHOTO = jpeg_bytes(site_photo())  # a camera photo, not of a drawing


def zipped(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return buffer.getvalue()


def file_of(status: ProjectStatus, path: str) -> FileStatus:
    return next(file for file in status.files if file.path == path)


def ingested(make_service: MakeService, files: dict[str, bytes], **ports: object) -> ProjectStatus:
    ingest = make_service(**ports)
    return ingest.wait(ingest.start("site.zip", zipped(files)))


def test_off_by_default_nothing_is_triaged_and_the_status_names_no_triage(
    make_service: MakeService,
) -> None:
    status = ingested(make_service, {"plan.pdf": PLAN, "elevation.png": SCAN})
    assert all(file.triage is None for file in status.files)
    assert "triage" not in status.readers
    assert "triage" not in status.files[0].model_dump(mode="json")  # left out of the JSON
    assert file_of(status, "elevation.png").drawing_id is not None  # read, as before


def test_an_image_that_is_no_floor_plan_is_set_aside_described_and_never_read(
    make_service: MakeService,
) -> None:
    classifier = FakeClassifier({SCAN: "other_drawing"})
    describer = FakeDescriber({SCAN: ("the south elevation of a house", ("Küche",))})
    found = steps(classifier, describer, WordJudge())
    status = ingested(make_service, {"plan.pdf": PLAN, "elevation.png": SCAN}, triage=found)
    elevation = file_of(status, "elevation.png")
    assert (elevation.state, elevation.drawing_id, elevation.normalised) == (
        "set_aside",
        None,
        None,
    )
    assert elevation.reason.startswith("not a floor plan: another kind of drawing (an elevation")
    assert elevation.triage is not None and elevation.triage.class_ == "other_drawing"
    assert elevation.triage.description is not None
    assert elevation.triage.description.subject == "the south elevation of a house"
    assert classifier.asked == ["png_plan"]  # the vector PDF is not triaged
    assert status.readers["triage"] == "fakes"
    plan = file_of(status, "plan.pdf")
    assert plan.triage is None and plan.drawing_id is not None


def test_relevance_is_judged_against_this_projects_plans_once_they_are_read(
    make_service: MakeService,
) -> None:
    other = png_bytes(raster_plan().rotate(90, expand=True))
    classifier = FakeClassifier({SCAN: "other_drawing", other: "other_drawing"})
    describer = FakeDescriber(
        {SCAN: ("an elevation", ("Küche",)), other: ("a music score", ("Allegro",))}
    )
    judge = WordJudge()
    files = {"plan.pdf": PLAN, "elevation.png": SCAN, "score.png": other}
    status = ingested(make_service, files, triage=steps(classifier, describer, judge))
    plan = file_of(status, "plan.pdf").drawing_id
    elevation = file_of(status, "elevation.png").triage
    score = file_of(status, "score.png").triage
    assert elevation is not None and elevation.relevance is not None
    assert (elevation.verdict, elevation.relevance.matched_on) == ("related", ("Küche",))
    assert elevation.relevance.plans == (plan,)  # the judge's id from elsewhere is dropped
    assert elevation.note is None
    assert score is not None and score.verdict == "unrelated"
    (context, _) = judge.contexts
    assert context.plans == (plan,)
    assert any("Küche" in said for said in context.plan_text)
    assert "score.png" in context.file_names
    assert context.descriptions == ("a music score",)  # the others', not its own


def test_with_no_plan_in_the_project_the_verdict_is_unsure_without_asking_the_judge(
    make_service: MakeService,
) -> None:
    judge = WordJudge()
    found = steps(
        FakeClassifier({PHOTO: "not_drawing"}), FakeDescriber({PHOTO: ("a cat", ())}), judge
    )
    status = ingested(make_service, {"cat.jpg": PHOTO}, triage=found)
    triage = file_of(status, "cat.jpg").triage
    assert triage is not None and triage.relevance is not None
    assert (triage.verdict, triage.relevance.why) == ("unsure", f"Unsure: {NO_PLAN}.")
    assert judge.contexts == []


def test_a_null_description_or_relevance_says_why_in_plain_words(
    make_service: MakeService,
) -> None:
    classifier = FakeClassifier({SCAN: "other_drawing", PHOTO: "not_drawing"})
    files = {"plan.pdf": PLAN, "elevation.png": SCAN, "photo.jpg": PHOTO}
    status = ingested(make_service, files, triage=steps(classifier))
    elevation = file_of(status, "elevation.png").triage
    assert elevation is not None and elevation.description is None
    assert (elevation.note, elevation.verdict) == (NOTE_NO_DESCRIBER, None)
    describer = FakeDescriber({SCAN: ("an elevation", ())})
    ingest = make_service(triage=steps(classifier, describer))
    status = ingest.wait(ingest.start("site.zip", zipped(files)))
    elevation, photo = file_of(status, "elevation.png").triage, file_of(status, "photo.jpg")
    assert elevation is not None and photo.triage is not None
    assert (elevation.relevance, elevation.note) == (None, NOTE_NO_JUDGE)
    refused = "not described: the model refused"
    assert (photo.triage.description, photo.triage.note) == (None, refused)
    (identify,) = [
        stage for stage in ingest.trace(status.id, photo.id).stages if stage.stage == "identify"
    ]
    assert identify.did.endswith(
        f"triage: not a drawing (P(plan) 0.03, fake classifier); {refused}"
    )


def test_an_image_the_classifier_calls_a_floor_plan_is_read_even_where_the_probe_said_not(
    make_service: MakeService,
) -> None:
    class Unknown:  # what the kind signal answers for an image it calls not a drawing
        def probe(self, data: bytes) -> Probed:
            return Probed(kind="unknown", did="not a drawing: P(not a drawing) 0.62")

    status = ingested(
        make_service, {"plan.png": SCAN}, probe=Unknown(), triage=steps(FakeClassifier({}))
    )
    plan = file_of(status, "plan.png")
    assert (plan.kind, plan.state != "set_aside", plan.drawing_id is not None) == (
        "png_plan", True, True,
    )  # fmt: skip
    # without triage the same image is set aside, as today
    status = ingested(make_service, {"plan.png": SCAN}, probe=Unknown())
    assert file_of(status, "plan.png").state == "set_aside"


def test_a_classifier_that_cannot_answer_leaves_the_file_as_today(
    make_service: MakeService,
) -> None:
    found = steps(FakeClassifier({SCAN: "other_drawing"}, unavailable=True))
    ingest = make_service(triage=found)
    project = ingest.start("site.zip", zipped({"scan.png": SCAN}))
    scan = file_of(ingest.wait(project), "scan.png")
    assert scan.triage is None and scan.drawing_id is not None
    (identify,) = [
        stage for stage in ingest.trace(project, scan.id).stages if stage.stage == "identify"
    ]
    assert "triage not available: the classifier is not reachable; read as today" in identify.did


def test_description_and_judge_costs_count_in_the_file_and_the_project(
    make_service: MakeService,
) -> None:
    classifier = FakeClassifier({SCAN: "other_drawing"})
    found = steps(
        classifier, FakeDescriber({SCAN: ("an elevation", ())}, usd=0.002), WordJudge(usd=0.001)
    )
    status = ingested(make_service, {"plan.pdf": PLAN, "elevation.png": SCAN}, triage=found)
    assert file_of(status, "elevation.png").cost_usd == 0.003
    assert status.cost_usd == 0.003
