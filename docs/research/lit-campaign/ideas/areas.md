# Areas

7 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i279"></a>
### 279. Expect area bias from boundaries, not only scale

- What: Do not attribute all area error to scale: takeoff areas run low 1-11% with correct scale; floorplan2bim recognition adds 5.3% median floor-area error.
- Evidence (floor-plans): Sadeh et al.; floorplan2bim round-53 table (own computation).
- Source: [github.com](https://github.com/jjjzhu-5847/floorplan2bim)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Separate scale and segmentation error on dev (true-scale runs).
- What breaks on our images: none
- Moves: scale-areas. Why this group: Good error accounting.
- Reports: lit-scale-a, lit-scale-b

<a id="i280"></a>
### 280. Printed room area wins over polygon area

- What: Use a printed room area or a dimension-line scale when present and fall back to polygon area only for rooms without one.
- Evidence (floor-plans): Judge tolerance for areas is 2% (docs/GOLDEN.md); best published pixel-count area error is 5.68% per room on clean renders; PlanQ 4.33% median with known scale.
- Source: [pp.bme.hu](https://pp.bme.hu/ci/article/view/44138)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: On dev plans with printed areas, compare read-area against polygon-area error and count rooms inside 2%.
- What breaks on our images: Plans with no printed areas; OCR misses a quarter of printed sizes even on clean images (Dodge 2017).
- Moves: scale-areas. Why this group: polygon area cannot reach 2% alone
- Reports: lit-rooms-a, lit-rooms-b, lit-rooms-c

<a id="i281"></a>
### 281. Erode regions back by any wall dilation used

- What: Undo the dilation applied before flood fill.
- Evidence (our-idea): tonkane recipe thickens walls by several pixels per side; 1 px shift costs 1.9% on a 3 m room and 3.7% on a 1.5 m closet at 855 px.
- Source: [github.com](https://github.com/tonkane/RoomSegmentation)
- Licence: MIT. CubiCasa5K leakage: n/a.
- Cost: 30 min
- Experiment: Area bias sign and size on dev.
- What breaks on our images: none
- Moves: scale-areas. Why this group: signed bias of 134 of 177 plans in PlanQ was negative
- Reports: lit-rooms-a, lit-rooms-b

## Try next

<a id="i282"></a>
### 282. Model the flat total against sum of rooms

- What: Measure how far the printed total exceeds the sum of printed net room areas.
- Evidence (floor-plans): One real marketing plan: 67.5 vs 70.0 m2 (3.6%).
- Source: [sivakka.fi](https://sivakka.fi/tampuuri/attachments/manual-floorplan-menninkaisentie3c69)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Dev sheets with both numbers; the median gap settles the bias term.
- What breaks on our images: One plan only.
- Moves: scale-areas. Why this group: Needed for the area routes.
- Reports: lit-scale-b

## Later

<a id="i283"></a>
### 283. State how scale error becomes area error

- What: Publish an error budget: a scale error of 2% moves areas about 4%; total area can be right while the room count is wrong.
- Evidence (adjacent-field): quantity-lab (MIT) on ten CubiCasa5K plans: scale +-2% gives +-3.6% to 4.2%; merges and splits leave total area almost unchanged; iGUIDE error budget 1 cm walls, about 1% area.
- Source: [github.com](https://github.com/dzakybd/quantity-lab), [help.youriguide.com](https://help.youriguide.com/hc/en-us/articles/27645625048210-iGuide-Measurements-and-Drafting-Standards)
- Licence: MIT. CubiCasa5K leakage: yes.
- Cost: 2 h (estimate)
- Experiment: Perturb scale on dev plans and report area error.
- What breaks on our images: Ten plans only.
- Moves: scale-areas. Why this group: framing
- Reports: lit-market-b, lit-market-c

## Idea or pitch only

<a id="i284"></a>
### 284. Prefer an area reference to a length reference for areas

- What: When a printed total exists, scale areas directly from it instead of squaring a length scale.
- Evidence (adjacent-field): Easy Leaf Area: 1.18% mean error with a known-area square; 5% length error gives 10% area.
- Source: [ncbi.nlm.nih.gov](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4103476/)
- Licence: no licence. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Compare area error from total-direct against length-squared on dev.
- What breaks on our images: Needs a printed total.
- Moves: scale-areas. Why this group: Follows from printed-total route.
- Reports: lit-scale-c

## Do not try (with the reason)

<a id="i285"></a>
### 285. Pixel counting beats VLMs for areas

- What: Do not ask a VLM for areas.
- Evidence (adjacent-field): MAPE about 43% for open VLMs vs 5.68% pixel counting (abstract).
- Source: [pp.bme.hu](https://pp.bme.hu/ci/article/view/44138)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: Colour-coded clean plans.
- Moves: scale-areas. Why this group: geometry beats VLM
- Reports: lit-floorplan-a
