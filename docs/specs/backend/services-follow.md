# Services follow: one plan edit, every discipline

Decision: [0016](../../decisions/0016-services-follow.md). Builds on decision 0013 (the agent chat and its plan
edits) and on #311 (`facts_mep.mep_elements`, the discipline taxonomy). Setting `SERVICES_FOLLOW=off|on`,
default off.

## What it does

When the chat proposes a plan edit on a sheet that was drawn from a building model, and the project also holds
service models of that building, the proposal comes back with what the edit does to each discipline:

- what hangs on a removed wall and where it can go;
- what runs inside the wall and what that pipework fed;
- what only passes through and stays;
- what stands in the wall and serves other storeys;
- what a new wall crosses;
- and, for every lane, whether it was checked at all.

The person sees one proposal: the architectural change and a tab per discipline over the same plan.

## Inputs

- The proposal (decision 0013): `removed`, `added`, `rooms`, in page fractions. Any edit kind works; the rules
  read only these three.
- The plan page as geometry (`plan_tools.plan_page`): rooms, wall mass, doors, metres.
- The project's IFC files. The one the sheet was read from gives the frame; every file with distribution
  elements gives a lane (or two, when it carries two service disciplines).

## Laying the models over the sheet (SF-1, SF-16)

- The frame is a least-squares fit from the centres of the model's spaces to the centres of the rooms the sheet
  draws them as (`drawing.model_objects`: GlobalId to room id). It needs three rooms that are not in one line.
- It is refused, and every lane says why, when the worst room misses by more than 5 cm or when a metre of the
  model is not a metre on the sheet (more than 2% off): the sheet is then not this model, or its scale is wrong.
- The storey is the one most drawn spaces are on. Its heights are its own elevation and the next storey's.
  Elements between those heights meet this page's walls; what hangs under the slab does not (it is reached
  through the graph when it matters).
- A service model is followed only when it has a storey at the same height (5 cm).
- A model's lane is what its classes say it mostly is (`discipline_from_census`), so a heating model's pipes are
  heating. A model with two service disciplines (each over 20%) is split element by element.

## Relations (all computed)

| Relation | Test |
| --- | --- |
| terminal **on** a strip | a connection port or its own point within 0.15 m; an air terminal only when it is in the strip (most hang from the ceiling) |
| piece **inside** a strip | both ports (or its point) within the strip, 2 cm tolerance |
| run **ends in** a strip | one port inside, one outside |
| run **through** a strip | its centre line crosses the strip, both ports outside |
| **riser** | an upright run (under 5 cm long on the plan) at least 1 m tall, standing in the strip |
| terminal's **room** | the room holding its point, else the nearest within 0.4 m |

Pieces in or ending in a strip are grouped by how they connect there. A group **only passes through** when it
leaves the strip towards two rooms and has no more run inside than twice the wall's thickness (at least 0.5 m).
So a duct modelled as two pieces and a damper meeting inside the wall is a passage, and pipework running along
inside an installation wall is not.

## Rules

A removed wall strip:

- **SF-2 re-seat.** A terminal on the strip goes to the nearest free place on a kept wall face of the merged
  room: clear of doors (0.15 m) and of other wall terminals (0.5 m), each placed one taking its place. The action
  gives the distance moved and, per system, a right-angle estimate of the new connection from the nearest kept
  piece of that system. Status `follows`. No free face: `needs_decision`.
- **SF-3 drains.** A terminal on a system that drains by gravity (waste, rain) is offered the same place, but the
  status is `needs_decision`: the fall and venting of a new waste branch are not checked.
- **SF-4 in the wall.** Pieces inside the strip go with it (`needs_decision`: they have to be rebuilt elsewhere),
  per system with their count and metres. Then, per system, every terminal that was connected to the system's
  largest part and no longer is, is `cut_off`, named by kind and room.
- **SF-5 through.** Runs that pass through stay (`stays`), now open to the merged room.
- **SF-6 riser.** An upright run in the strip is `needs_decision`. When the column it belongs to passes the
  storey's heights, the action says it goes on to another storey.
- **SF-7 fire damper.** A fire damper in or at the strip: `needs_decision`, "probably a fire compartment
  boundary, which this check cannot confirm". It is said once: a damper is not listed again among the runs
  that pass through.
- **SF-8 heights.** Elements outside the storey's heights are not tested.
- **SF-9 tally.** The merged room's terminals by kind and by the room they came from (`stays`).

An added partition:

- **SF-11.** Each run it crosses needs an opening (`follows`, per system with sizes). A run along it or a
  terminal under it is `needs_decision`.

A new room (a room of the proposal that did not exist before), per lane that has terminals on the storey:

- **SF-19 has and keeps.** One `stays` action: the new room's terminals by kind, and what the room it was cut
  from keeps. A terminal belongs to the new room when it was in the old room and the new room's outline is the
  nearer of the two.
- **SF-19 lacks.** The new room's type is read from its name as the law check reads it (`wc`, `kitchen`, ...;
  anything else is `other`, so offices and meeting rooms are one type). It is measured against this floor's
  rooms of that type as they are before the edit: a kind of terminal that at least 80% of them have and the new
  room has none of is `needs_decision`, code `missing`, worded "3 of the 3 rooms of its type on this floor (wc)
  have one". Fewer than two rooms of the type: no comparison. Whether the room needs it is for a person.
- **SF-19 connection estimate.** With each lack: the nearest run of a system those rooms' terminals are on. Inside
  the new room: "already runs through the room". Otherwise a right-angle line from the run to the room's nearest
  wall face, drawn dashed, with its length and the walls it passes; on a system that drains, the sentence that
  fall and venting are not checked.
- The overlay also shows the terminals inside a new room, however far from the new walls.

Always:

- **SF-10.** All four lanes are listed. `no_model`: the project has none. `not_aligned`: the plan was not drawn
  from a model, the frame was refused, or the model lacks the storey. Each with its reason in the lane's line.
- **SF-12.** The overlay's marks are the runs and terminals within 3 m of the edit plus everything an action
  names, in page fractions, each with a ref (`P`, `V`, `H`, `E` and a number) that actions point at.
- Fixed unknowns when anything was checked: no 3D check of services against each other; new connections are
  estimates, sizes, flows and waste falls are not checked.
- Nothing is called approved, blocked or coordinated.

Not built yet: choosing between re-seat options in conversation; electrical circuits. The comparison of a new
room is with the rooms of one sheet, not of the whole building.

## API (additive to v1)

`Proposal.services: ServicesFollow | null` (null when `SERVICES_FOLLOW=off`).

```ts
type ServicesFollow = {
  storey: string | null
  disciplines: DisciplineFollow[]      // always plumbing, ventilation, heating, electrical
  unknowns: string[]
  credits: string[]                    // the service models' licence credits
}
type DisciplineFollow = {
  discipline: string
  status: "checked" | "no_model" | "not_aligned"
  source: string | null                // the model's name in the project
  reason: string | null                // why not checked
  elements: number                     // of the model between the storey's heights
  line: string                         // the lane in one sentence, server-written
  summary: { follows: number, stays: number, needs_decision: number, cut_off: number, new_run_m: number }
  marks: { ref: string, global_id: string, kind: string, label: string, line: [number, number][], at: [number, number] | null }[]
  actions: {
    id: string
    status: "follows" | "stays" | "needs_decision" | "cut_off"
    code: "reseat" | "in_wall" | "cut_off" | "through" | "riser" | "fire_damper" | "tally" | "opening" | "under"
        | "missing"
    label: string                      // the whole consequence in plain words, numbers included
    refs: string[]                     // the marks it is about
    system: string | null
    moved_to: [number, number] | null  // a re-seated terminal's new place
    paths: [number, number][][]        // proposed connections, drawn dashed
  }[]
  picture: FollowPicture | null        // a lane a services picture checked (Pictures below); else null
}
type Pairing = {                       // why the discipline sheet is taken to be the plan's floor (W1)
  drawing_id: string
  page: number
  paired_by: "same_page" | "metadata" | "geometry" | "user"
  reason: string                       // plain words, server-written
  score: number | null                 // 0..1; null for same_page and user
}
type FollowPicture = {                 // all places in THIS sheet's page fractions
  drawing_id: string
  page: number
  pairing: Pairing
  removed: [number, number][][]        // the removed walls' strips
  added: [number, number][][]          // the new partitions' strips
  marks: { ref: string, line: [number, number][], at: [number, number] | null }[]  // refs as in `marks`
}
```

The plan tool's result gains `services` for the model: `{storey, text, disciplines: [{discipline, status, model,
line, summary, actions: [{status, what}], more_actions}], unknowns}`. No refs or places. `text` is the checked
lanes' lines and the unchecked lanes' reasons as one paragraph; the rules planner appends it to its answer.
A lane lists its first 12 actions; when it has more, its `line` ends "Only the first 12 of its N findings are
listed here." (SF-17), so a cut list is not read as the whole of it. The proposal keeps them all.

## What 0013 keeps

- One proposal per turn: the follow-up adds none.
- The law check runs first and reads the proposal's own rooms; the follow-up changes none of them.
- Every number the model may say is in the tool result, in a lane's line or an action's words.
- Accept and Reject act on the chat's copy; `services` travels with it unchanged.
- With the setting off, or `services` null, the edit card is what it was.

## The graph (`app/core/services/graph.py`)

`ServiceGraph(elements)`: `get(guid)`, `systems()`, `members(system)`, `neighbours(guid, system?)`,
`part(guid, system?, without?)`, `largest(system, without?)`, `path(start, end, system?)`, `terminals(guids)`.
Ids in, tuples and frozensets out; no geometry and no file. Per system on purpose: a fixture bridges its systems,
so "still connected" needs the system named. `app/adapters/ifc_services.py` builds the elements;
`ServiceFiles` keeps the last 8 read models by content hash.

Reading (SF-18): a model is read once per app process, about a second and 150-200 MB each. So that the first
proposal of a project does not wait for that, every chat turn with the setting on asks `ServiceFiles.warm` to
read the project's models in a background thread; a model already asked for is not asked again, and one is read
at a time. At most 8 model files of a project are followed, the sheet's own model first: a ninth would push the
first out again on every proposal. The rest are named in `unknowns` ("2 more model files of this project were
not read: at most 8 are followed.").

## Tests

- `tests/test_services_follow.py` (SF-1..SF-13, SF-19): each rule on a hand-built page and ten elements, the frame fit
  and its refusals, the graph.
- `tests/test_ifc_services.py` (SF-14): the reader on IFC files built in the test.
- `tests/test_service_tools.py` (SF-16..SF-18): the project wiring on a scripted project, the cut note, the
  read-ahead and the cap.
- `tests/api/test_api_services_follow.py` (SF-15): off by default; on, a project without models; the rules
  planner's text.

## Measured on a real building

DigitalHub v2 (RWTH Aachen, MIT; architecture, sanitary, ventilation, heating as four IFC4 files), ground floor,
through the real ingest and plan tools in one process, 2026-11-14:

- ingest of the seven files 3.5 s; the first followed edit 4.8 s (reads four models), each later one 0.1 s; the
  process peaked at 541 MB.
- 562 plumbing, 625 ventilation and 764 heating elements between the storey's heights.
- Of the 43 inside walls the plan tools list, 32 can be proposed today. Of those, 4 carry a fire damper (the
  shaft walls), 2 have an air terminal in the wall to re-seat, and 14 have runs passing through.
- A new room in the open workspace: its partition crosses one heating flow and one return pipe (DN15).

## Pictures (services drawn on a picture, not modelled)

Owner: Tudor's side (`app/core/services/picture_follow.py`, the `pictures` call in `adapters/service_tools.py`);
review eu-big. Request: Bogdan, #281 c6884888469.

When the plan was not drawn from a building model and the project has a services picture of that floor (another
sheet, or services marks on the plan's own sheet), the edit is followed on the picture's marks: the spots of its
fact sheet (`app/core/picture_facts.py`, one spot per symbol or run piece, page fractions). A picture shows where
things are drawn, not how they connect or at what height, so nothing is re-seated, traced or cut off.

`ServiceFollower.pictures` gives a drawing's services fact sheet by drawing id (none by default). On a plan whose
route is not `bim`, each lane a picture gives (checked or not aligned) replaces that lane's "not checked"; a lane no
picture gives stays as the model path left it. The marks' `global_id` is empty: a picture has no model ids.

| On the page | Removed wall | Added partition |
| --- | --- | --- |
| a symbol within 0.15 m of the strip | `reseat`, `needs_decision`: it has to move; where to and how to reconnect are not shown on a picture | `under`, `needs_decision`: on the new wall's line |
| a run with more than max(2 × the wall's thickness, 0.5 m) inside the strip | `in_wall`, `needs_decision`: it goes with the wall | `under`, `needs_decision`: it runs along the new wall |
| any other run touching the strip | `through`, `stays`: now open to the merged room | `opening`, `follows`: each crossing needs an opening |
| anything else | not listed; shown as a mark within 3 m of the edit | the same |

Every run's action ends "what it feeds and whether it can be rerouted are not shown on a picture".

**Laying a picture over the plan.** The plan's own page lies on itself. Another sheet lies over it only when the
floors do not differ (when both sheets name one), both have a scale, and at least 3 room names printed once on each
appear on both; the sheets are then laid over by the names' places in metres, and refused when the worst name
misses by more than 0.5 m. Otherwise the lane is `not_aligned` with the reason ("only 2 room names appear on both
sheets (3 are needed)", "the services picture has no scale", "the services picture is of another floor (…)").
A lane with no picture is `no_model`: "this project has no <lane> picture of this floor".

**Pairing a picture with the plan's floor** (`app/core/services/pairing.py`, `pair(plan, candidates, register)`;
pics-edit-follow W1). Pure, one result per candidate sheet in the candidates' order: a `Pairing` (`drawing_id`,
`page`, `paired_by`, `reason` in plain words, `score` 0..1, `to_plan` the sheet's page fractions on the plan's) or
the reason it is refused. Metadata first, cheapest first, then geometry:

- The plan's own page: `same_page`, identity, "the plan's own page".
- Floor hints, read from each sheet's title-block floor (`storey`), its sheet number and its file name (its ZIP
  folders only refuse: a set's folder such as "B1/" is on every floor's sheet, so floor words in folders that
  differ refuse, as "OG 1/" against "EG/", and equal ones agree on nothing): floor words (EG, Erdgeschoss, ground floor, GF → 0; OG 1, 1. OG, floor 1, level 1, 1st floor, first floor, L1 → 1;
  UG, KG, basement, B1, B01 → -1; level codes E00, E01 → 0, 1, read from the title's floor and from inside a file
  name, never as a sheet number nor as a file name's first word ("E01 Elektro.png" is the first electrical sheet); DG,
  attic, ullakko → attic; roof → roof, a floor of its own; floors listed or ranged in words, "Basement, First and
  Second Floor" → -1, 1, 2, "Second Thru Seventh Floors" → 2..7, "Floors 2-4" → 2, 3, 4) and the sheet number's
  part after its discipline letters
  (A-101 / H-101 → 101). A floor word both sides name agrees ("same floor: 'Floor 1' on both"), equal number parts
  agree ("sheet numbers A-101 / H-101"). Floor words that differ refuse ("another floor: 'Floor 2' against
  'Floor 1'"), also when another floor word both name agrees (a building folder "B1/" shared by every floor of the
  set): each naming a floor the other doesn't is a difference. Number parts that differ refuse only when no floor
  word agrees. A year is no sheet number ("KOY_2019" is the project's).
- Then the sheet is laid over the plan by `register(plan, sheet)`: an affine map with the words of how
  ("laid over by 3 room names"), or why not. The default is the room-name shift above; the wall-line fit
  (rotation and scale, Madalina's side) plugs in here.
- Metadata agrees and it is laid over: `metadata`, score 0.9, both reasons. Metadata agrees, not laid over, both
  sheets have a scale and the same size within 2 %: `metadata`, score 0.7, laid over page to page. Metadata agrees
  and neither: refused, "same floor (…), but it cannot be laid over the plan: <why>". No hint either way, but a sheet's name says a floor that no rule reads ("Upper Floors", "Typical Floor",
  "Mezzanine Floor"): refused, "the plan names a floor that is not read ('Upper Floors'): no floor to pair on" (or
  "the services picture names …"), since geometry alone would pick a floor the words may contradict. No hint either way and laid
  over: `geometry`, score 0.6. No hint and not laid over: refused with the register's reason.
- One set only: when both upload paths sit in a top-level folder and the folders differ, the sheet is refused
  ("another set: folder 'B' against 'A'"), unless both folders are named by discipline (Architektur, HVAC, LVI,
  Elektro, ...: one delivery); a file at the top of the upload says nothing either way. Years refuse nothing: on
  real sets a floor's services sheets are often drawn years after or before its plan (USCG building 110: plan as
  built 1965, heating 1958, electrical 1981; 4 right pairings lost to a years rule, pics-answer 2026-11-15).
- Laid over by walls (`by_walls`, around `register` in `app/core/services/register.py`): the plan's wall lines are
  the centre lines of its drawn wall mass in metres (each pair of parallel faces 3–60 cm apart, outer walls
  included); the sheet's come from the sheet-walls reader in its own pixels with its page size. The map is
  `register`'s rotation, scale and shift turned into page fractions, and its words are `register`'s ("walls match:
  41 of 47 within 0.2 m after rotation 0.3 deg"); when the sheet has its own scale (a scale bar) and the walls' fitted
  one differs by more than 5 %, the words name both and say the walls were used. The follower tries room names first, then walls; a refusal of
  both gives both reasons. Without a sheet-walls reader only room names are tried.
- Several sheets paired for one discipline: the highest score wins (the plan's own page first, then the candidates'
  order); its reason names the others; each other is refused "another <discipline> picture was taken: <name>".
  When the best is `geometry` and other sheets of that discipline are laid over by geometry alike, none naming a
  floor, all of them are refused ("2 heating pictures fit this plan alike and none names its floor (a.png, b.png):
  which one is this floor is not known"): the floors of a building print the same room names, so upload order
  would pick the floor.

**Unknowns** (when any lane was checked): a services picture shows where things are drawn, not how they connect
(what a run feeds and whether it can be rerouted); a picture shows no heights (what is on a wall's line may run in
the floor or under the ceiling); the symbols and runs are read by vision, so one the readers missed is not there.

**Shortcuts** (each marked in the code):
- A shift only: two sheets of one floor are taken to share their orientation; a rotation is not fitted.
- A run piece's spot is a box, so the piece is taken along the box's long side; a diagonal piece is approximate.
- Floors are compared only when both sheets name one. A vector plan has no title read, so a services picture of
  another floor whose room names repeat could be laid over it.

Acceptance criteria (tests in `tests/test_services_picture_follow.py` and `tests/test_service_tools_pictures.py`):

- **SFP-1** Two radiators on a removed wall, a pipe crossing it, one radiator and one pipe elsewhere: one `reseat`
  (`needs_decision`, both radiators, "2 radiators", the legend label), one `through` (`stays`, the label and its
  size, the "not shown on a picture" words); nothing else; the three other lanes `no_model`; the unknowns given
  (`test_two_radiators_on_the_removed_wall_a_pipe_crossing_it_and_the_rest_clear`).
- **SFP-2** 3 m of pipe inside a removed wall: `in_wall`, `needs_decision`, "3.0 m"
  (`test_a_run_along_inside_the_removed_wall_goes_with_it`).
- **SFP-3** An added partition: the pipe crossing it `opening` (`follows`), the radiators on its line `under`
  (`needs_decision`) (`test_an_added_partition_needs_an_opening_where_a_pipe_crosses_it`).
- **SFP-4** Nothing on the walls: the lane is checked with no action and says so
  (`test_nothing_on_the_walls_says_so`).
- **SFP-5** Another sheet of the floor, 1 m off on a 12 m page, with 3 shared room names and both scales: laid over,
  the marks back on the plan's page
  (`test_another_sheet_of_the_floor_is_laid_over_by_three_room_names_and_the_scales`).
- **SFP-6** Two shared names, no scale, or another floor: `not_aligned` with that reason
  (`test_another_sheet_is_not_laid_over_without_three_room_names_a_scale_or_the_same_floor`).
- **SFP-7** A picture project's wall removal through `ServiceFollower.run` gets the picture's heating lane, and the
  model's text names it (`test_a_wall_removed_on_a_picture_plan_gets_the_picture_lane_of_its_services_marks`).
- **SFP-8** Without a services picture the follow-up is as before
  (`test_without_a_services_picture_the_follow_up_is_as_before`).

Pairing (tests in `tests/test_services_pairing.py`):

- **SFP-9** The plan's own page pairs `same_page` with the identity, score None
  (`test_the_plans_own_page_pairs_same_page`).
- **SFP-10** "A-101 Floor 1 plan.pdf" and "set/H-101 Floor 1 heating.png" with 3 shared room names: `metadata`,
  0.9, the reason names floor 1, the sheet numbers and the room names (`test_same_floor_and_sheet_number_and_rooms`).
- **SFP-11** "H-102 Floor 2 heating.png" against the floor 1 plan is refused as another floor even when its room
  names fit; "EG" against "OG 1" in the title blocks likewise (`test_another_floor_is_refused_whatever_the_rooms`).
- **SFP-12** Same floor, no shared room names, same sheet size in metres: `metadata`, 0.7, page to page; a
  different size: refused with "same floor" and the register's reason
  (`test_same_floor_without_rooms_is_laid_page_to_page_only_on_the_same_sheet_size`).
- **SFP-13** No floor hint on either sheet, 3 shared room names: `geometry`, 0.6; 2 shared names: refused "only 2
  room names appear on both sheets (3 are needed)" (`test_no_hint_falls_back_to_geometry`).
- **SFP-14** Two heating sheets paired: the better wins and names the other; the other is refused "another heating
  picture was taken: …" (`test_the_best_of_two_heating_sheets_wins_and_names_the_other`).
- **SFP-15** The register is a parameter: a stub register's map and words come back in the pairing
  (`test_the_register_plugs_in`).
- **SFP-16** `ServiceFollower` follows only on the pictures `pair` keeps: a heating picture of another floor in the
  project leaves the lane `not_aligned` with the floor reason
  (`test_a_heating_picture_of_another_floor_is_not_followed`).
- **SFP-17** "A/plan.pdf" and "B/heating.png" are refused as another set; "plan.pdf" and "B/heating.png" are not
  (`test_sheets_of_two_folders_are_two_sets`).
- **SFP-18** A sheet drawn turned a quarter at 50 px a metre, its walls in pixels: `by_walls` gives the map that puts its
  corners back on the plan's page fractions and `register`'s words; with no room names the follower's register
  (room names, then walls) pairs it `geometry`; both refusing gives both reasons; a sheet scale 20 % off the walls' is named
  (`test_walls_lay_a_turned_half_size_sheet_over_the_plan`).
- **SFP-19** The wall mass of a 0.2 m walled box gives its four centre lines (`test_the_plans_wall_lines_are_centre_lines`).
- **SFP-20** A picture whose drawing has no scale is sized by the scale its picture lane read
  (`PictureFactSheet.scale`, #511: `width_px × m_per_px` by `height_px × m_per_px`): same floor and size, laid page to
  page and checked; without it, refused "… the services picture has no scale" unless the walls lay it over
  (`test_a_picture_without_a_drawing_scale_is_sized_by_its_readers_scale`).
- **SFP-21** "B1/A-101 Floor 1 plan.pdf" against "B1/H-102 Floor 2 heating.png": refused "another floor: 'Floor 2'
  against 'Floor 1'", with or without room names; a sheet adding no floor word of its own pairs
  (`test_floor_words_that_differ_refuse_even_when_one_is_shared`).
- **SFP-22** "E01 Elektro.png" (electrical) and an E01 sheet number name no floor; "…-e00-okrd" inside a file name
  and "E01_OKRD" as the title's floor still do (`test_an_electrical_sheet_number_is_not_a_level_code`).
- **SFP-23** A plan naming no floor and two heating sheets laid over alike by room names: both refused, the reason
  names both; a sheet naming the plan's floor still wins over one by geometry
  (`test_two_floors_that_fit_alike_and_name_no_floor_are_both_refused`).
- **SFP-24** "Architektur/…" and "Heizung/…" are one set (`test_discipline_folders_are_one_set`); a basement plan
  of 1965 and its heating sheet of 1958 pair (`test_sheets_drawn_years_apart_still_pair`).
- **SFP-25** "KOY_2019 plan.pdf" and "KOY_2019 heating.png" share no sheet number: with no rooms they are refused
  with the register's reason, not laid page to page (`test_a_project_year_is_not_a_sheet_number`).
- **SFP-26** "Second Floor Plan" against "Heating Layout First Floor Plan" is refused "another floor: 'First Floor'
  against 'Second Floor'"; against a second floor heating layout it pairs `metadata`
  (`test_written_floor_ordinals_name_a_floor`).
- **SFP-27** "B1/H-heating.png" against "B1/A-101 Floor 1 plan.pdf" names no floor (the folder is not read): `geometry`
  with room names, refused without (`test_a_floor_word_in_a_folder_is_not_the_sheet_s_floor`); a DigitalHub
  electrical "…_plan-03-e01-okrd.png" against the "…-e00-okrd" plan is refused "another floor: 'e01' against 'e00'"
  (`test_a_level_code_inside_an_electrical_sheet_s_name_is_its_level`).
- **SFP-28** "Projekt/OG 1/Grundriss.pdf" against "Projekt/EG/Heizung.png" is refused "another floor: 'EG' against
  'OG 1'"; against "Projekt/OG 1/Heizung.png" it pairs by `geometry`, not by the folder
  (`test_floor_words_in_folders_refuse_when_they_differ`).
- **SFP-29** "Upper Floors Plan" against a first floor heating sheet is refused, the plan naming a floor that is not
  read; "Typical Floor" on the services picture likewise; "Floor Plan" alone names no floor and pairs by `geometry`
  (`test_a_floor_the_name_says_but_pairing_cannot_read_refuses_instead_of_geometry`).
- **SFP-30** Lists, ranges and plurals are read: "Second Thru Seventh Floors" 2..7, "First and Second Floors Plans"
  1, 2, "Basement, First and Second Floor" -1, 1, 2, "Second and Attic Floor" 2, attic, "Floors 2-4" 2..4
  (`test_floor_lists_ranges_and_plurals_are_read`).
- **SFP-31** The confirmation run's 10 wrong pairings (USCG Governors Island) are refused: building 855's floors 2-7
  plan against its first floor electrical and roof plumbing, building 928's roof plan against first and second floor
  HVAC, building 333's roof plan against its electrical attic, "another floor: 'Attic' against 'Roof'"
  (`test_the_confirmation_runs_wrong_pairings_are_refused`).

**The picture's own geometry (W2, `.agents` brief pics-edit-follow).** A lane a picture checked also carries
`picture`: the discipline sheet it was read from (`drawing_id`, `page`), the `pairing` that took that sheet to be the
plan's floor (W1: `paired_by` same_page, metadata, geometry or user; `reason` in plain words; `score`), and the edit
drawn in **that sheet's** page fractions: the removed walls' strips and the new partitions' strips (each a polygon,
the plan's strips mapped back through the inverse of the sheet-to-plan transform), and each of the lane's marks that
the sheet draws, by the same `ref`, at its place on the sheet (a symbol's centre, a run piece's line). The lane's
`marks` and `actions` stay in the plan's fractions, as before. When several sheets give one lane, `picture` is the
first sheet laid over (W1 names the others in the reason). A lane from a building model, or not checked, has no
`picture`. With `DISCIPLINE_PICTURES` off nothing gives a picture lane, so no lane has one.

The transform is an affine map of page fractions, `plan = (a·x + b·y + c, d·x + e·y + f)` for a sheet point (x, y):
the identity on the plan's own page, a scale and shift from the room names today, a rotation too when W1/register
fits one. It is not in the API.

- **SFPW-1** The plan's own page: `picture` is that page, `paired_by` `same_page`, the removed strip as on the plan,
  each mark at its spot's place (`test_the_plans_own_page_gives_its_picture_with_the_strip_and_marks_as_drawn`).
- **SFPW-2** Another sheet 1 m off on a 12 m page (SFP-5): the strip lands 1 m back on the sheet (1/12 of its
  width), the marks at their own spots, refs equal to the lane's marks
  (`test_another_sheet_gets_the_edit_in_its_own_fractions`).
- **SFPW-3** An added partition is in `added`, not `removed`, on the sheet (`test_an_added_partition_is_drawn_on_the_sheet`).
- **SFPW-4** A lane not aligned, or not checked, or from a model has no `picture`
  (`test_a_lane_not_laid_over_has_no_picture`).
- **SFPW-5** The affine map: inverse(apply(p)) is p for a shift, a scale and a rotation
  (`test_the_affine_map_inverts`).
- **SFPW-6** A pairing given by the caller (W1's `pair()`, in the sheets' order) is the one shown; a str refuses the
  lane (`test_a_pairing_given_by_the_caller_is_the_one_shown`). Through `ServiceFollower.run`: the picture lane has
  its `picture`, the model's tool result has none, and with no pictures (DISCIPLINE_PICTURES off) every lane's
  `picture` is null (`test_through_the_follower_the_picture_lane_has_its_picture_and_no_picture_none`).
