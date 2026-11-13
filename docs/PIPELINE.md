# Pipeline (Stoa challenge)

Status: draft, 2026-11-13 21:50. It follows [REQUIREMENTS.md](REQUIREMENTS.md) (ingest once, answer cheaply, two
methods). The per-plan output, the drawing model, becomes decision record 0004.

## 1. Ingestion: from files to one drawing model per plan

All the drawing work happens here, once per file. A question asked later is a lookup in the result, so it costs
almost nothing.

```mermaid
flowchart TD
    IN["Project archive or single files<br/>zip, PDF, PNG, JPEG, DXF, IFC, SVG"] --> U["1 · Unpack safely<br/>path check, size caps"]
    U --> H["2 · Hash every file (sha256)"]
    H --> SEEN{"Seen before?"}
    SEEN -- yes --> REUSE["Reuse the stored drawing model"]
    SEEN -- no --> ID["3 · Identify by content,<br/>not by file extension"]
    ID --> DRW{"A drawing?"}
    DRW -- no --> ASIDE["Set aside with a reason<br/>(photo, text page, specification)"]
    DRW -- yes --> G["4 · Group the files of one drawing<br/>swiss: PDF + PNG + DXF of the same plan<br/>IFC model + its sheet PDFs + SVG"]
    G --> R["5 · Pick the richest source and record it<br/>IFC model, then DXF, then vector PDF or SVG, then raster"]
    R --> N["6 · Normalise<br/>render each page once: one frame, positions as page fractions<br/>fix rotation (0, 90, 180, 270)<br/>split a sheet into its plans<br/>find the scale, or mark it missing"]

    N -- "BIM" --> EI["IFC reader<br/>spaces, storeys, doors, windows,<br/>fixtures, quantities, GlobalIds"]
    N -- "CAD" --> EC["DXF reader<br/>layers and blocks to rooms and symbols"]
    N -- "vector" --> EV["Vector parser<br/>text objects, paths and fills:<br/>rooms with areas, doors, windows,<br/>fixtures, apartments, outdoor areas"]
    N -- "raster" --> ER["Raster reader<br/>OCR of room labels, symbol detector,<br/>plan regions"]
    N -- "schedule sheet" --> ES["Table reader<br/>schedule rows from the text layer"]

    EI & EC & EV & ER & ES --> EL["7 · Elements<br/>each with class, polygon or box, label,<br/>confidence and the method that found it"]
    EL --> C2["8 · Second count, by an independent method<br/>printed total vs summed rooms, detector vs parser,<br/>IFC model vs plan"]
    C2 --> AG{"Do the two agree?"}
    AG -- yes --> RU
    AG -- no --> CON["Conflict: keep both values,<br/>mark the contested elements"]
    CON --> RU["9 · Apply the counting rules (stored as data)<br/>e.g. one window per drawn cell;<br/>a sauna room, else its stove"]
    RU --> TK["10 · Takeoff: every known quantity precomputed<br/>value, marks, rule, confidence, status"]
    TK --> OUT[("Drawing model, one JSON per plan<br/>+ page renderings + trace + cost")]
    REUSE --> OUT

    classDef reader fill:#e8f5e9,stroke:#2e7d32,color:#111
    classDef warn fill:#fff3e0,stroke:#ef6c00,color:#111
    classDef out fill:#e3f2fd,stroke:#1565c0,color:#111
    class EI,EC,EV,ER,ES reader
    class ASIDE,CON warn
    class OUT,REUSE out
```

Every stage also appends what it found to the plan's trace (for example "rotated 90°", "9 room labels", "2
conflicts"). The ingest screen shows that trace, and the demo walks through it.

## Stages, what each one writes, and what exists today

| Stage | Writes | Requirement | Today |
| --- | --- | --- | --- |
| 1-2 Unpack, hash | file inventory with sha256 | I1, I2 | to build |
| 3-4 Identify, group | drawing groups, set-aside list with reasons | I3 | to build |
| 5 Route | the chosen source per drawing | I4 | to build |
| 6 Normalise | page renderings, rotation, plans per sheet, scale and its source | I5, I6, I7 | scale from the sheet text is in the prototypes; rotation and plan split to build |
| 7 Extract: vector | rooms, openings, fixtures, apartments | I8 | prototype, `prototypes/pdf-extract/` (swiss counts 99.9%, areas 99.97%, IFC plan areas 97%; not blind) |
| 7 Extract: raster | room labels (OCR), symbols (detector), plans | I8 | research; detector training on dev-split boxes allowed (decision 0003) |
| 7 Extract: BIM | IFC elements with GlobalIds, placed on the sheet | I8 | to build; waits on the ifcopenshell licence decision |
| 7 Extract: CAD, tables | DXF elements; schedule rows | I8 | DXF only if Stoa gives it; tables surveyed, not built |
| 8 Second count | the second value and the contested marks | I10 | to build |
| 9 Rules | rule ids per quantity | I9 | known for CubiCasa (board #15) and swiss (in the prototypes); to encode as data |
| 10 Takeoff, drawing model | one JSON per plan | I9, I11, I12 | schema proposed; decision record 0004 to write |
