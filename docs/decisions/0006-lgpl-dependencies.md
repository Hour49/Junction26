# 0006: LGPL libraries are allowed as unmodified PyPI dependencies

- Status: accepted
- Date: 2026-11-13 23:03 (Europe/Helsinki)
- Decided by: Bogdan ("1yes", answering: "ifcopenshell (LGPL) as an unmodified dependency so we can commit
  ifc_gold.py? Recommended: yes.")
- Board thread: #14 (Tudor's orchestrator asked)

## Context

There is no IFC route without ifcopenshell, which is LGPL-3.0-or-later. `docs/ENGINEERING.md` §4 allowed only MIT,
BSD, Apache-2.0 and ISC, so `prototypes/extraction-gold/ifc_gold.py` (the IFC-based extraction gold) could not be
committed. LGPL lets MIT code import and use a library unchanged. It asks that users can replace the library, that
its licence notice is kept, and that we do not copy its code into ours.

## Decision

LGPL-3.0-or-later libraries are allowed as dependencies if all of this holds:

- installed unmodified from PyPI and pinned through the lockfile or the script's inline metadata;
- imported as a library, never vendored, copied, patched or statically bundled;
- the library's licence notice stays with it (it ships in the package; we do not strip it).

GPL, AGPL and non-commercial licences stay out of shipped code. Other rules for new dependencies in
`docs/ENGINEERING.md` §4 are unchanged. First use: ifcopenshell 0.8.5 in `ifc_gold.py`.

## Alternatives considered

- Skip IFC and build the gold from PDFs alone: loses the model truth (object classes, storeys, quantities) that the
  IFC sheets give.
- Write our own IFC parser: far too much work for the event, and it would be worse than ifcopenshell.

## Consequences

`ifc_gold.py` can be committed. If a container image bundles ifcopenshell, keep it as a normal pip install so it stays
swappable. Revisit if we need to patch ifcopenshell (then the patch must be published under LGPL) or if a GPL or
AGPL library is proposed.
