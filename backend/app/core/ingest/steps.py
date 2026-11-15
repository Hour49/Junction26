"""The steps of the stages around the readers (decision 0018): what identify, normalise and the
second count did inside, from what they already return. A step not timed on its own (a
comparison, the EXIF turn) has `ms` 0 and begins with its stage."""

from collections.abc import Sequence

from app.core.drawing.model import Conflict
from app.core.ingest.model import Normalised, Probed, Triage
from app.core.pipeline.model import StepTrace
from app.core.pipeline.steps import Span
from app.core.wording import count


def probe_step(probed: Probed, span: Span) -> StepTrace:
    """The content probe, with the sheet-kind signal it asked when it did."""
    did = probed.did
    if probed.p_plan_sheet is not None:
        did += f"; sheet-kind signal: P(plan) {probed.p_plan_sheet:.2f}"
    elif probed.signal_missing is not None:
        did += f"; {probed.signal_missing}"
    return StepTrace(
        id="probe",
        label="Content probe",
        did=did,
        at_ms=span.at_ms,
        ms=span.ms,
        cost_usd=span.cost_usd,
        state="failed" if span.faults else "done",
    )


def triage_step(triage: Triage | None, said: str, span: Span) -> StepTrace:
    """Triage's classifier, and its describer when the file is not a floor plan."""
    label = "Triage: is it a floor plan?"
    if triage is not None and triage.description is not None:
        label = "Triage: is it a floor plan? Then described"
    return StepTrace(
        id="classifier",
        label=label,
        did=said.removeprefix("triage: ") or "not an image: not triaged",
        at_ms=span.at_ms,
        ms=span.ms,
        cost_usd=span.cost_usd,
        state="failed" if span.faults or (triage is None and said) else "done",
    )


def frame_steps(frame: Normalised | None, ms: float) -> list[StepTrace]:
    """The EXIF turn and the rectifier that brought an image upright (timed together, `ms`)."""
    if frame is None:
        return []
    steps: list[StepTrace] = []
    if frame.exif not in (None, 1):
        steps.append(
            StepTrace(id="exif", label="EXIF orientation", did=f"orientation {frame.exif} applied")
        )
    if frame.rectified:
        steps.append(
            StepTrace(
                id="rectifier",
                label=f"Photo rectifier ({frame.rectifier})",
                did=f"paper seen straight on: {frame.width}x{frame.height} px",
            )
        )
    if steps:
        steps[-1] = steps[-1].model_copy(update={"ms": ms})
    return steps


# What a comparison's step is called, by the quantity or the second method: (id, label)
COMPARED = {
    "ifc_model": ("ifc_vs_sheet", "Building model vs the sheet"),
    "schedule": ("schedule_tags", "Schedule vs the tags on the plan"),
    "scale": ("scale_check", "Scale: printed text vs scale bar"),
    "room_area": ("room_areas", "Room areas: printed vs measured"),
}


def second_count_steps(conflicts: Sequence[Conflict] | None) -> list[StepTrace]:
    """One step per kind of comparison: what was compared, how many agree and conflict."""
    kinds: dict[tuple[str, str], list[Conflict]] = {}
    for entry in conflicts or ():
        methods = {value.method for value in entry.values}
        key = next(
            (COMPARED[name] for name in ("ifc_model", "schedule") if name in methods),
            COMPARED.get(
                entry.quantity,
                ("second_count", f"{entry.quantity.replace('_', ' ').capitalize()}: "
                 + " vs ".join(sorted(m.replace("_", " ") for m in methods))),
            ),
        )  # fmt: skip
        kinds.setdefault(key, []).append(entry)
    steps: list[StepTrace] = []
    for (step_id, label), entries in kinds.items():
        conflict = sum(entry.status == "conflict" for entry in entries)
        agree = len(entries) - conflict
        steps.append(
            StepTrace(
                id=step_id,
                label=label,
                did=f"{count(len(entries), 'quantity', 'quantities')} compared: {agree} agree, "
                f"{count(conflict, 'conflict')}",
                found={"agree": agree, "conflict": conflict},
            )
        )
    return steps
