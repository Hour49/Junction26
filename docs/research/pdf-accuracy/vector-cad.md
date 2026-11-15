# vector-cad: reading vector CAD/Revit sheets (layers, symbols, curve text, multi-view sheets)

Worker vector-cad, 2026-11-15. Angle: vector PDF sheets exported from Revit/AutoCAD, the A-701 Restrooms 0/4 case.
Stoa data not touched. All numbers marked **own run** come from 7 public US bid sets downloaded to the scratchpad
(sources at the end) and probed with pypdfium2 (already a backend dependency). Literature numbers are from the papers.

## Summary (5 lines)

1. A-701 is a multi-view sheet whose fixtures are symbols, not text: the reader needs **(a) the sheet split into views
   by their title + scale notes** and **(b) a symbol count inside one view**. Both are doable on vector PDFs with
   pypdfium2 alone.
2. **View titles**: "text directly above a scale note" found 13/13 view titles on a public restroom sheet like A-701
   (Rialto A201: 3 plans + 10 elevations), 2/2 on A202, 5/9 on a detail sheet (misses `1-1/2" = 1'-0"` forms).
3. **Layers (OCGs)**: when the PDF came from AutoCAD with layers, pypdfium2 gives every object its layer name; the
   `A-FLOR-FIXT-N` layer, grouped into touching-box instances and assigned to views, gave **14/14 toilets and 7/7
   sinks in the right view, 1 extra object**. But only 2 of 7 public sets had layers, and **Revit's own PDF export
   writes none** (0 OCGs on 20/20 Revit pages, and Autodesk users confirm Revit cannot).
4. **Layer-free route** (merge touching curved paths, fingerprint the group): the 14 toilets form one signature
   (14/14) on the same sheet; sinks share a signature with toilets drawn in elevations, so it only works after the view
   split. Revit exports tessellate arcs (0 Bézier segments on 4/4 Revit pages), so this needs a line-based variant: NEXT.
5. **Curve text**: AutoCAD SHX text is geometry, but AutoCAD hides the string in "AutoCAD SHX Text" comments
   (257 strings missing from the text layer on one restroom sheet, incl. fixture tags `TP-1`, `SN-1`): read them, S
   effort. Learned vector symbol spotters (SymPoint PQ 83.3, VecFormer 91.1 on FloorPlanCAD) are research only (CC BY-NC
   training data, multi-GPU training): SKIP.

## Ranked table

| # | Finding | Verdict | Number (dataset) | Licence | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | Split a sheet into views: title text right above a scale note, objects go to the nearest title row below, last title to their left | ADOPT NOW | 13/13 titles A201, 2/2 A202, 5/9 A501 (Rialto restroom set, own run); fixtures 21/21 in the right view after the rule fix | pypdfium2 Apache-2.0/BSD-3 | S-M |
| 2 | Read each object's OCG layer through pypdfium2 marked content; count NCS fixture/door layers as touching-box instances | ADOPT NOW (gated on the PDF having layers) | 14/14 toilets, 7/7 sinks, 1 FP (Rialto A201, own run); layers in 2/7 public sets, 0/20 Revit pages | pypdfium2 | S |
| 3 | Read AutoCAD "SHX Text" hidden comments (Contents + Rect) as text | ADOPT NOW | 27-257 strings per sheet missing from the text layer, 5/5 AutoCAD pages of the Madison set (own run) | pypdfium2 | S |
| 4 | View type from the title words (PLAN / RCP / ELEV / SECTION / DETAIL / SCHEDULE); default plan | ADOPT NOW, with #1 | 13/13 correct on A201 by eye (own run); no paper number | none | S |
| 5 | Layer-free symbol count: group touching paths, fingerprint (paths, segments, sorted w×h), count repeats inside one view | NEXT | 14/14 toilets as one signature (A201); sinks collide with elevation toilets until #1; 0 groups on Revit pages (no Béziers) | pypdfium2 | M |
| 6 | Text drawn as curves without SHX comments: render the region and OCR it | NEXT | Madison A-sheet p3: 1 text object vs 20,435 paths (own run); OCR accuracy on such sheets not measured | RapidOCR Apache-2.0 (already a dep) | S-M |
| 7 | Revit page metadata keys `/revit_metadata_view_sheet_number`, `_view_name` | ADOPT NOW (tiny) | 20/20 Revit pages of the Madison set carry them (own run) | pdfminer.six MIT or pikepdf MPL-2.0 | S |
| 8 | Read text inside form XObjects (`max_depth=1` today) | NEXT (small, low gain) | +48 text objects of 436 on one title sheet; 0 symbol blocks found in forms on any sheet page (own run) | pypdfium2 | S |
| 9 | Hatch/fill regions as rooms | SKIP for now | no measurement; layer names like `E-HATCH POCHE` exist | - | M |
| 10 | Learned vector symbol spotting (FloorPlanCAD family) | SKIP (research only) | PQ: PanCADNet 55.3, CADTransformer 68.9, GAT-CADNet 73.7, SymPoint 83.3, SymPoint-V2 90.1, VecFormer 91.1 (FloorPlanCAD) | data CC BY-NC; code MIT/Apache/none | L |

## What A-701 is and why it reads 0/4

From `prototypes/extraction-gold/opening_design_gold.py`: the 4 questions ask about fixtures in detail views 6A
"RESTROOMS" (toilets, sinks), 6B "RESTROOM WITH SHOWER" (toilet, sink, shower), with 6D/6E also on the sheet; the
fixtures "are not text: they are block symbols". `backend/app/adapters/vector_pdf/objects.py` reads paths and text
objects at `max_depth=1` with no notion of layers, views or symbols, so nothing in the pipeline can answer "toilets in
6A". The view titles in A-701 do not contain the word PLAN ("RESTROOMS", "WATER CLOSET TYP."), so title-based view
typing must default to plan and only exclude ELEV/SECTION/DETAIL-type words when the question asks for a plan.

**First step for whoever may open the Stoa data:** check A-701's producer, OCGs, Bézier count and SHX comments with the
probe in section 2 (the `mark_layer` function; a page-level layer count). If it has layers, #1 + #2 answer it; if it
is a native Revit export (likely: Sports_Complex, "typical Revit sheet"), it has no layers and #1 + #5 (line-based) or
#1 + a raster fixture detector on the view crop are the routes.

## 1. Split a multi-view sheet into views (ADOPT NOW, S-M)

US sheets (Revit and AutoCAD alike) label every view the same way: a numbered bubble, an underlined title, and a scale
note right under it (`1/4" = 1'-0"`, `SCALE: 1/2" = 1'-0"`, `NTS`). Revit places this as the "view title" family; the
geometry sits above it.

Rule tried (own run, pypdfium2 text objects in rendered coordinates):
- scale note = text matching `^(SCALE:?\s*)?(\d+(\s*\d+)?(/\d+)?\s*["”]\s*=\s*\d+\s*['’]\s*-?\s*\d*["”]?|NTS|N\.T\.S\.)$`;
- title = nearest text 0-25 pt above it, left edge within 15 pt;
- an object belongs to the nearest title row below it (rows bucketed at 60 pt), and in that row to the title whose left
  edge is the last one left of the object (+40 pt slack).

Results:
- Rialto A201 (restroom floor plan, RCP, demolition plan, 10 interior elevations): **13/13** titles with their scales.
- Rialto A202: 2/2 ("ENLARGED WOMEN'S ROOM", "ENLARGED MEN'S ROOM").
- Rialto A501 details: 5/9; the misses use `1-1/2" = 1'-0"` and `SCALE: 1 ½" = 1'-0"` (extend the regex to mixed
  numbers and the ½ glyph) or put the scale right-aligned.
- Assignment: the first rule (nearest title by distance) put all 22 fixture instances in the demolition plan, because
  both bottom titles are on the same row; with "last title to the left" all 21 real fixtures went to "ENLARGED
  WOMEN'S ROOM FLOOR PLAN". On A202 the 42 instances split 22/20 between the two plans (not checked by eye).

Free side effects: each view's own scale (the A201 demolition plan is 3/16", the rest 1/4"), which also feeds the
"scale disagrees" problem in the brief, and a crop box per view to hand to the raster route or a VLM. Limits: views
with no scale note (NTS details are fine, bare titles are not), titles above the view (rare in US sets), schedules.
Plug-in: new `vector_pdf/views.py` returning `(title, number, scale_text, bbox)`; route/answer picks the view whose
title best matches the question (fuzzy, which also needs the partial/plural matching the brief lists).

No paper measures view segmentation of CAD sheets; the closest is the lit-campaign sheet work (`lit-sheet-*.md`).

## 2. Layers (OCGs) per object (ADOPT NOW when layers exist, S)

How exporters name them (verified on the files and vendor docs):
- AutoCAD `DWG To PDF.pc3` with "Include layer information": one OCG per plotted layer, named exactly as the DWG
  layer, xref layers as `<xref>|<layer>`. Seen: `RST FP01_v4|A-FLOR-FIXT-N`, `A-DOOR-FULL-E`, `A-WALL-FIRE-02HR`,
  `x_1117ttblk_Capwell|SHBD-TEXT--`, `E-HATCH POCHE`, `X-DOOR`. These follow the US National CAD Standard layer form
  (discipline-major-minor-status, `-N` new, `-E` existing, `-D` demolition): `A-FLOR-FIXT` plumbing fixtures,
  `A-DOOR` doors, `A-GLAZ` windows, `A-WALL` walls, `P-FIXT` plumbing.
- Layers without plotted objects are dropped; viewport layer overrides are lost (one OCG state per page).
- Revit's built-in PDF export (2022+) writes no layers; Autodesk forum users say they must go through AutoCAD to
  deliver layered PDFs. Own run: 0 OCGs on the 20 Revit pages of the Madison set. Bluebeam's Revit plugin can add them.
- Coverage in the 7 public sets: 2 had OCGs (Alameda Capwell, 292 OCGs; Rialto, 104), both AutoCAD-origin.

Reading them needs no new dependency: PDFium exposes marked content per page object, and `/OC /MCx BDC` marks carry
the OCG dictionary, so the layer name is the mark's `Name` parameter (own run: every object on 9/9 Rialto pages got a
layer, 0 without):

```python
def mark_layer(obj):  # obj: pypdfium2 page object; returns the OCG name or None
    for m in range(raw.FPDFPageObj_CountMarks(obj.raw)):
        mk = raw.FPDFPageObj_GetMark(obj.raw, m)
        n = ctypes.c_ulong(); raw.FPDFPageObjMark_GetName(mk, None, 0, n)
        buf = ctypes.create_string_buffer(n.value)
        raw.FPDFPageObjMark_GetName(mk, ctypes.cast(buf, ctypes.POINTER(ctypes.c_ushort)), n.value, n)
        if buf.raw.decode("utf-16-le").rstrip("\x00") != "OC":
            continue
        raw.FPDFPageObjMark_GetParamStringValue(mk, b"Name", None, 0, n)
        if n.value > 2:
            buf = ctypes.create_string_buffer(n.value)
            raw.FPDFPageObjMark_GetParamStringValue(
                mk, b"Name", ctypes.cast(buf, ctypes.POINTER(ctypes.c_ushort)), n.value, n)
            return buf.raw.decode("utf-16-le").rstrip("\x00")
    return None
```

Counting (own run, Rialto A201 "Enlarged Women's Room"): the `A-FLOR-FIXT-N` layer holds 806 path objects; merging
paths whose boxes touch (1 pt slack) gives 22 instances: 14 of 24-25 × 42-43 pt (toilets), 7 of 28 × 30 pt (sinks),
1 thin 7 × 57 pt object. Checked against the render by eye: 14 toilets and 7 sinks in plan 2, **14/14 and 7/7, 1 FP**.
Toilets drawn in the elevations and the existing toilets in the demolition plan are on other layers, so they are
correctly not counted. Size classes would need a label: either the legend/keynote text near the instance, or a
size rule per fixture (toilet ≈ 20-30" × 28-31" at the view's scale). Plug-in: `PdfPath.layer` in `objects.py`
(one more field), a `layer_instances(page, pattern)` helper; route "how many toilets/sinks/doors" to it when the page
has OCGs. Effort S.

## 3. AutoCAD SHX text from hidden comments (ADOPT NOW, S)

SHX fonts are stroke shapes, so AutoCAD plots them as paths; since AutoCAD 2016 SP1 the `PDFSHX` variable (default 1)
also writes each string as a hidden comment titled "AutoCAD SHX Text" with the string in `/Contents` and its box in
`/Rect`. pypdfium2 reads them (`FPDFPage_GetAnnot`, `FPDFAnnot_GetStringValue(b"Contents")`, `FPDFAnnot_GetRect`;
they come as Square annotations, subtype 5). Own run on the Madison locker-room set: 34, 116, 77, 296, 130 comments on
5 AutoCAD pages, of which 27, 105, 67, 257, 124 strings are missing from the text layer. On the restroom sheet A4.1
they include room tags, dimensions and fixture/accessory tags (`TP-1`, `SN-1`, `GB-2`, `M-1`), and the title block,
sheet number and `SCALE: 1/4" = 1'-0"` notes the view split (#1) needs. Plug-in: add them as `PdfText` in
`objects.py` (bounds from `/Rect`). Caveat: users can turn `PDFSHX` off, and a printed-through-Bluebeam set (Powder
Springs) has 13 "AutoCAD SHX Text" strings in the file but 0 as page annotations (not traced further).

## 4. Plan vs elevation/section/detail (ADOPT NOW with #1, S)

Classify each view from its title: `ELEV`, `SECTION`, `DETAIL`, `SCHEDULE`, `TYPES`, `RCP`/`REFLECTED CEILING`,
`DEMOLITION` vs the rest = plan. On A201 this sorts 13/13 by eye (1 floor plan, 1 demolition plan, 1 RCP, 10
elevations). This is what A-701 needs: it mixes plans 6A/6B with other views, and fixtures drawn in elevations must
not be counted as plan fixtures (A201: elevation toilets share the sink fingerprint, #5). No paper number; the
`lit-sheet-*` reports cover sheet-level classification, not views.

## 5. Layer-free symbol counting by geometry repetition (NEXT, M)

Neither Revit nor AutoCAD keeps blocks/families as form XObjects: 0 symbol-bearing form XObjects on every sheet page
probed (forms appear only as stamps/logos, 3-136 per page, almost all empty of paths: `max_depth=1` vs deep counts
differ by 0-77 paths). So "count the XObject references" is not available; symbols must be found by geometry.

Own run, A201 (ignoring layers): paths with Bézier segments merged when their boxes touch, fingerprint =
(number of paths, number of segments, sorted rounded w × h). The most repeated large group is (35 paths, 146 segments,
23 × 29 pt) × 14 = **exactly the 14 plan toilets**. The sink group (6, 24, 20 × 26) × 14 holds the 7 plan sinks and 7
elevation toilets, so the count is right only after #1/#4 restrict it to the plan view.

Two blockers before it ships:
- Native Revit exports contain **no Bézier segments** (0 of 4,226-5,341 segments on 4 Revit pages; arcs are
  tessellated into lines), so the curve filter finds 0 groups. Including all short paths (< 60 pt) made the Revit
  page's signature list noisy (229 tick marks, 189 short lines first; a 15 × (23, 100) group may be fixtures, not
  verified) and on A201 merged toilets into partitions. A line-based variant needs stroke-width/colour grouping
  (Revit gives fixtures their own pen weight) or a seed: the user's click, the legend symbol, or the fixture a raster
  detector found first, then exact-match the rest (template retrieval; TempFit, 2610.17776, does this with learning,
  Greedy PQ 86.2 on FloorPlanCAD, no licence file).
- Mirrored/rotated instances: sorted w × h covers 90° turns and mirrors; arbitrary angles need a moment-based key.

Plug-in: `vector_pdf/symbols.py`, called per view; answer = size of the group the question names (label from nearby
text or a size rule). Effort M; worth an experiment on the Stoa vector sheets once A-701's producer is known.

## 6. Text drawn as curves without comments (NEXT, S-M)

Some sheets carry no text objects and no SHX comments: Madison p3 (AutoCAD "High Quality Print" pc3) has 1 text
object (the plot stamp) and 20,435 paths. Options: (a) render the view or title-block crop at 200-300 dpi and run
RapidOCR (Apache-2.0, already a backend dependency) for titles, scale notes and tags; (b) glyph matching: SHX glyphs
are identical stroke sets, so the same fingerprint as #5 clusters every "A", then OCR one sample per cluster. No paper
measures either on CAD sheets (searched; the lit-campaign OCR reports cover raster plans only). Detect the case with
"text objects / path objects < 0.001 and no SHX comments".

## 7. Revit page metadata (ADOPT NOW, tiny)

Revit's native export adds non-standard page keys: `/revit_metadata_view_sheet_number` (`P 100`),
`/revit_metadata_view_name` (`P 100 - Plumbing Layout`), `/revit_metadata_view_type` (`VT_Drafting`) on 20/20 Revit
pages of the Madison set. That gives sheet number and title without reading the title block, and flags "this page is a
native Revit export" (so skip the OCG and Bézier routes). PDFium has no API for arbitrary page-dict keys; pdfminer.six
(MIT, `PDFPage.attrs`) or pikepdf (MPL-2.0, file-level copyleft, fine to ship unmodified) read them. pdfplumber is
MIT and sits on pdfminer.six.

## 8. Form XObjects (NEXT, small)

`objects.py` reads `max_depth=1`, so text and paths inside form XObjects are skipped. Own run: a Powder Springs title
sheet has 388 text objects at depth 1 and 436 in all (+48, title block); every plan page differed by 0-6 text objects.
Low gain for A-701; change only if a sheet's title block hides in a form.

## 9. Hatches and fills as rooms (SKIP for now)

The Swiss route already uses fills (`wall_fills.py`). US CAD sheets put hatches on their own layers (`E-HATCH POCHE`,
NCS `A-FLOR-PATT`) and Revit draws room fills only when a colour scheme is on. No measured number found; not the
A-701 failure.

## 10. Learned vector symbol spotting (SKIP, research only)

FloorPlanCAD (ICCV 2021, 15k+ sheets, 30 classes incl. doors, windows, toilets, sinks, bath) is CC BY-NC, so every
model trained on it is research only for us. Panoptic quality on FloorPlanCAD (SymPoint, ICLR 2024, Table 1):
PanCADNet 55.3, CADTransformer 68.9 (code MIT), GAT-CADNet 73.7, SymPoint 83.3 (1000 epochs; repo licence
NOASSERTION/non-commercial); semantic F1 80.6 / 82.2 / 85.0 / 86.8. Later (from the lit-campaign, `lit-vector-b.md`):
SymPoint-V2 90.1 (no licence), CADSpotting 87.4 (no licence), VecFormer 91.1 with layer prior / 88.4 without
(Apache-2.0, no weights), TempFit Greedy PQ 86.2, ArchCAD DPSS PQ 70.6; text features add ~2 PQ to CADTransformer
(0.7152 → 0.7352). All take DXF/SVG primitives (lines, arcs, circles); a PDF export gives the same primitives except
Revit's tessellated arcs. VecFormer's own ablation (+2.7 PQ from the layer prior) agrees with #2: the layer name is
strong evidence. Training needs 8 GPUs and non-commercial data; nothing to ship before the freeze.

## Sources

Vendor docs and forums:
- AutoCAD PDFSHX: https://help.autodesk.com/cloudhelp/2019/ENU/AutoCAD-LT/files/GUID-56EA988C-A1DA-4E85-8765-B3F31A01AB02.htm
- AutoCAD export to PDF: https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-LT-MAC/files/GUID-310657DF-8614-4125-B2E7-1FBF8B67333F.htm
- SHX comments shown by viewers: https://kbpdfstudio.qoppa.com/pdf-created-by-autocad-shows-sticky-note-bubbles-on-document/
- Layered PDFs from AutoCAD: https://blog.draftsperson.net/how-to-create-pdf-with-layers-from-autocad-file/
- Revit cannot write PDF layers (users): https://forums.autodesk.com/t5/revit-ideas/2d-pdf-printing-support/idc-p/6509582
- Revit PDF export: https://help.autodesk.com/cloudhelp/2026/ENU/Revit-DocumentPresent/files/GUID-773AD069-024B-425E-8B9A-05D5246BDD16.htm
- Bluebeam Revit plugin keeps layers: https://novedge.com/blogs/design-news/bluebeam-tip-optimize-revit-to-pdf-exports-for-bluebeam-revu

Papers and code:
- SymPoint (ICLR 2024), tables with PanCADNet/CADTransformer/GAT-CADNet: https://arxiv.org/html/2401.10556
- CADTransformer code (MIT): https://github.com/VITA-Group/CADTransformer
- SymPoint code (licence NOASSERTION): https://github.com/nicehuster/SymPoint
- VecFormer (Apache-2.0): https://github.com/WesKwong/VecFormer ; other numbers via `docs/research/lit-campaign/reports/lit-vector-b.md`
- Libraries: pypdfium2 (Apache-2.0 or BSD-3-Clause; PDFium BSD-3) https://github.com/pypdfium2-team/pypdfium2 ;
  pdfplumber MIT https://github.com/jsvine/pdfplumber ; pdfminer.six MIT https://github.com/pdfminer/pdfminer.six ;
  pikepdf MPL-2.0 https://github.com/pikepdf/pikepdf ; RapidOCR Apache-2.0 https://github.com/RapidAI/RapidOCR

Public drawing sets probed (own run, not committed, scratchpad only):
- Rialto Square Theatre restroom renovation (AutoCAD layers, A201/A202/A501): https://rialtosquare.com/wp-content/uploads/2024/04/2022-07-29_Rialto-Square-Theatre-Arch-Permit-and-Bid-Set.pdf
- City of Madison locker room (AutoCAD SHX pages + 20 native Revit pages): https://www.cityofmadison.com/business/pw/contracts/documents/9659%20Plans%20Version%20CB-01.pdf
- Alameda County Capwell (AutoCAD, 292 OCGs): https://www.acgov.org/gsaapp/purchasing/bidContent_ftp/rfpDocs/CapwellADASet.pdf
- NIST reference building (Bluebeam): https://www.nist.gov/system/files/documents/2023/07/31/NIST_Reference_Building_Plumbing_Models_Architectural_Drawings.pdf
- Addison TX park restroom (AutoCAD 2012): https://gis.addisontx.gov/GIS_Documents/BuildingPlans/Vitruvian/Drawings/Park%20Restroom%20Building/1-Arch/A1.1.pdf
- Powder Springs restroom (Bluebeam): https://www.powderspringsga.gov/DocumentCenter/View/8945/RFP-25-012---Powder-Springs-Park---Phase-2---Restroom-Alteration-CD-PDF
- CDH Idaho restroom bid set (Bluebeam): https://cdh.idaho.gov/wp-content/uploads/2024/11/2024-10-CDH-Restroom-Renovation-Bid-Set-1.pdf
