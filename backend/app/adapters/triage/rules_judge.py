"""TRIAGE_JUDGE=rules: the relevance judge with no model (decision 0010 section 8).

A described file is judged by the rule over its description's form (`triage.relevance_by_rule`):
related only when a word printed on it is among the project's facts. A file nothing described
(the describer is off or refused it) falls back to the rule on its class: a picture that is not a
drawing is unrelated, another kind of drawing (an elevation, a section, a site plan) is unsure,
for a person to say (#152, Tudor's fleet's review of section 8); that `why` says it did not read
the picture. The `judge` field names which rule ran.
"""

from app.core.ingest.triage import relevance_by_rule
from app.core.ingest.model import (
    Description,
    ProjectContext,
    Relevance,
    TriageClass,
    Unavailable,
)

JUDGE = "rule on the kind of picture, no model (no description to read)"
NOT_DRAWING_WHY = (
    "A picture that is not a drawing; such files are judged unrelated by a rule on what kind of "
    "picture they are, without reading what they show."
)
OTHER_DRAWING_WHY = (
    "Another kind of drawing (an elevation, section, site plan, detail or cover); whether it "
    "belongs to the project needs a person, since a rule on what kind of picture it is cannot "
    "tell without reading what it shows."
)


class RulesJudge:
    reads_description = False  # so it judges files nothing described too

    def judge(
        self, kind: TriageClass, description: Description | None, context: ProjectContext
    ) -> Relevance | Unavailable:
        if kind != "floor_plan" and description is not None:
            return relevance_by_rule(description, context)
        match kind:
            case "not_drawing":
                return Relevance(verdict="unrelated", why=NOT_DRAWING_WHY, judge=JUDGE)
            case "other_drawing":
                return Relevance(verdict="unsure", why=OTHER_DRAWING_WHY, judge=JUDGE)
            case "floor_plan":
                return Unavailable(note="a floor plan is read, not judged")
