"""The building-code rule packs (RULE_PACKS_DIR, decision 0009): one `<pack id>.json` per pack,
validated as `RulePack`. A pack that does not validate (a rule that quotes no clause, an unknown
op or room type, a repeated id) or whose id is not its file name stops the start, naming the
file."""

from pathlib import Path

from pydantic import ValidationError

from app.core.checks.model import RulePack
from app.core.errors import InvalidInputError


def load_packs(folder: Path) -> tuple[RulePack, ...]:
    """Every pack in `folder`, by id. A missing folder has none."""
    packs: list[RulePack] = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
        try:
            pack = RulePack.model_validate_json(path.read_bytes())
        except ValidationError as error:
            raise InvalidInputError(f"rule pack {path.name}: {error}") from error
        if pack.id != path.stem:
            raise InvalidInputError(f"rule pack {path.name}: its id is {pack.id!r}")
        packs.append(pack)
    return tuple(packs)
