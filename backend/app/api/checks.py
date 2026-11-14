"""Building-code pre-checks of a drawing or a whole project against one rule pack (story #139,
docs/decisions/0009-building-code-checks.md, docs/API.md "Building-code checks"). The pack is a
choice on the screen (`?pack=`, one at a time; none chosen: no checks), not stored on the project;
the check runs on each request over the drawing model as ingest read it. A pre-check of a few
rules, not a compliance certificate."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import DrawingId, Ingest, IngestDep, ProjectId, as_uploaded
from app.api.views import View, drawings_of
from app.core.checks.check import check_drawing, overall
from app.core.checks.model import (
    COMPARISON_TEXT,
    NOTE,
    AppliesTo,
    CheckUnit,
    Clause,
    Comparison,
    Op,
    RuleCheck,
    RulePack,
    RuleStatus,
)
from app.core.errors import UnknownPackError
from app.core.ingest.model import ProjectStatus
from app.core.review.review import NotAllowedError

router = APIRouter(prefix="/api")

PACK = Query(description="the rule pack to check against: an id from GET /api/info rule_packs")


class RuleView(View):
    """A rule as the pack states it. `op` is the machine check type, never shown; `comparison`
    is machine (">="), `comparison_text` the words the screen shows ("at least")."""

    id: str
    title: str
    op: Op
    applies_to: AppliesTo
    comparison: Comparison
    comparison_text: str
    limit: float
    unit: CheckUnit
    key: str | None
    clause: Clause


class RulePackView(View):
    """A pack as GET /api/info lists it, for the country picker: the flag from `country`, the
    country's name, the pack's name and law line, and every rule with the clause it quotes."""

    id: str
    country: str  # ISO 3166-1 alpha-2, "FI"
    country_name: str  # "Finland"
    name: str  # the pack's display name
    law: str
    version: str
    note: str  # always NOTE: a pre-check, not a compliance certificate
    fail_means: str | None  # what a fail means under this law, to show with NOTE
    rules: list[RuleView]


class DrawingChecks(View):
    drawing_id: str
    file: str  # as this project uploaded it (with `project`), else the drawing's stored name
    file_id: str | None  # the project's file id (f1, f2...); None outside a project
    pack: str
    note: str
    # fail when a rule fails, else cannot tell, else pass; not_applicable: no rule applies
    status: RuleStatus
    rules: list[RuleCheck]


class ProjectChecks(View):
    project_id: str
    pack: str
    note: str
    status: RuleStatus  # over its drawings, as a drawing's is over its rules
    drawings: list[DrawingChecks]


def pack_views(packs: tuple[RulePack, ...]) -> list[RulePackView]:
    return [
        RulePackView(
            id=pack.id,
            country=pack.country,
            country_name=pack.country_name,
            name=pack.name,
            law=pack.law,
            version=pack.version,
            note=NOTE,
            fail_means=pack.fail_means,
            rules=[
                RuleView(
                    **rule.model_dump(exclude={"applies_to", "clause"}),
                    applies_to=rule.applies_to,
                    clause=rule.clause,
                    comparison_text=COMPARISON_TEXT[rule.comparison],
                )
                for rule in pack.rules
            ],
        )
        for pack in packs
    ]


def get_rule_packs(request: Request) -> tuple[RulePack, ...]:
    return request.app.state.rule_packs


RulePacksDep = Annotated[tuple[RulePack, ...], Depends(get_rule_packs)]


def pack_of(request: Request, pack_id: str) -> RulePack:
    """The pack `?pack=` names; 404 `unknown-pack` when there is none."""
    return find_pack(get_rule_packs(request), pack_id)


def find_pack(packs: tuple[RulePack, ...], pack_id: str) -> RulePack:
    """The pack with this id among the loaded ones; UnknownPackError when there is none."""
    found = next((pack for pack in packs if pack.id == pack_id), None)
    if found is None:
        raise UnknownPackError(f"no rule pack {pack_id!r}")
    return found


def file_id_of(status: ProjectStatus, drawing_id: str, path: str) -> str | None:
    """The id of the project's file `path` that holds the drawing."""
    return next(
        (file.id for file in status.files if file.drawing_id == drawing_id and file.path == path),
        None,
    )


def drawing_checks(
    ingest: Ingest, drawing_id: str, file: str, file_id: str | None, pack: RulePack
) -> DrawingChecks:
    route = ingest.drawing_info(drawing_id).route  # raster: read off a picture
    rules = check_drawing(ingest.drawing(drawing_id), pack, route)
    return DrawingChecks(
        drawing_id=drawing_id,
        file=file,
        file_id=file_id,
        pack=pack.id,
        note=NOTE,
        status=overall(check.status for check in rules),
        rules=list(rules),
    )


@router.get("/drawings/{drawing_id}/checks")
def checks(
    request: Request,
    drawing_id: DrawingId,
    ingest: IngestDep,
    pack: Annotated[str, PACK],
    project: Annotated[str | None, Query(description="the project it is shown in")] = None,
) -> DrawingChecks:
    """Every rule of the pack on one drawing: pass, fail or cannot tell per room, door or sheet."""
    chosen = pack_of(request, pack)
    found = ingest.drawing(drawing_id)  # 404 for an unknown drawing, before the project
    if project is None:
        return drawing_checks(ingest, drawing_id, found.file, None, chosen)
    named = as_uploaded(ingest, ingest.drawing_info(drawing_id), project)
    file_id = file_id_of(ingest.status(project), drawing_id, named.path)
    return drawing_checks(ingest, drawing_id, named.path, file_id, chosen)


@router.get("/projects/{project_id}/checks")
def project_checks(
    request: Request, project_id: ProjectId, ingest: IngestDep, pack: Annotated[str, PACK]
) -> ProjectChecks:
    """Every drawing of the project checked against the pack, in the project's drawing order.
    409 `not-allowed` until the project's ingest is done, as for the project's questions."""
    chosen = pack_of(request, pack)
    status = ingest.status(project_id)
    if status.state != "done":
        raise NotAllowedError(f"project {project_id} is {status.state}; check it when it is done")
    drawings = [
        drawing_checks(
            ingest,
            entry.drawing_id,
            entry.file,
            file_id_of(status, entry.drawing_id, entry.file),
            chosen,
        )
        for entry in drawings_of(status)
    ]
    return ProjectChecks(
        project_id=status.id,
        pack=chosen.id,
        note=NOTE,
        status=overall(check.status for check in drawings),
        drawings=drawings,
    )
