"""Evidence ids (spec AC-5): every place a tool result points at gets an `ev_<k>` the model cites.
The model never writes a page or a box: the server keeps them under the id."""

from typing import Any

Json = dict[str, Any]


def mint(found: Any, ledger: dict[str, Json], first: int) -> None:
    """Gives every object in `found` (decoded tool JSON, changed in place) that has a `box` and,
    its own or its nearest parent's, a `page` and a `drawing_id` an `"ev"` field, numbered from
    `first + len(ledger)`, and records `{drawing_id, name, page, box, label, sure, level}` under
    it in `ledger`."""
    _walk(found, ledger, first, {})


def _walk(found: Any, ledger: dict[str, Json], first: int, context: Json) -> None:
    if isinstance(found, list):
        for item in found:  # pyright: ignore[reportUnknownVariableType]
            _walk(item, ledger, first, context)
        return
    if not isinstance(found, dict):
        return
    here: Json = found  # pyright: ignore[reportUnknownVariableType]
    context = {**context, **_context(here)}
    box = _box(here.get("box"))
    if box is not None and isinstance(context.get("page"), int) and context.get("drawing_id"):
        ev = f"ev_{first + len(ledger)}"
        here["ev"] = ev
        label = next(
            (here[k] for k in ("label", "subject", "name", "type", "class", "id") if here.get(k)),
            None,
        )
        ledger[ev] = {
            "drawing_id": context["drawing_id"],
            "name": context.get("drawing_name"),
            "page": context["page"],
            "box": box,
            "label": str(label) if label is not None else None,
            "sure": context.get("sure"),
            "level": context.get("level"),
        }
    for value in list(here.values()):
        if isinstance(value, dict | list):
            _walk(value, ledger, first, context)


def _context(here: Json) -> Json:
    """What an object passes down to the objects inside it."""
    out: Json = {}
    if isinstance(here.get("drawing_id"), str):
        out["drawing_id"] = here["drawing_id"]
        name = here.get("name") or here.get("file")
        out["drawing_name"] = name if isinstance(name, str) else None
    if isinstance(here.get("page"), int):
        out["page"] = here["page"]
    level = here.get("level")
    if isinstance(level, dict) and "level" in level:
        out["level"] = level
    line: Any = here.get("line")
    sure: Any = here.get("sure", line.get("sure") if isinstance(line, dict) else None)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    if isinstance(sure, bool):
        out["sure"] = sure
    return out


def _box(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, list | tuple) or len(value) != 4:  # pyright: ignore[reportUnknownArgumentType]
        return None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value):  # pyright: ignore[reportUnknownVariableType]
        return None
    x0, y0, x1, y1 = (float(v) for v in value)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return (x0, y0, x1, y1)
