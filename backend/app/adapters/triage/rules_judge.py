"""TRIAGE_JUDGE=rules: the relevance judge with no model, from the file's class alone.

The baseline fixed before any model (.agents/briefs/triage/triage-models.md section 3): a
picture that is not a drawing is unrelated, another kind of drawing (an elevation, a section, a
site plan) is related. It never reads what the picture shows, and its `why` says so. A model
judge replaces it behind the same setting only if it beats it by the kill rule; this one stays as
the fallback when the model is off or unavailable, and the `judge` field always names which ran.
"""

from app.core.ingest.model import (
    Description,
    ProjectContext,
    Relevance,
    TriageClass,
    Unavailable,
)

JUDGE = "rule on the kind of picture, no model"
NOT_DRAWING_WHY = (
    "A picture that is not a drawing; such files are judged unrelated by a rule on what kind of "
    "picture they are, without reading what they show."
)
OTHER_DRAWING_WHY = (
    "Another kind of drawing (an elevation, section, site plan, detail or cover); such files are "
    "judged related by a rule on what kind of picture they are, without reading what they show."
)


class RulesJudge:
    def judge(
        self, kind: TriageClass, description: Description, context: ProjectContext
    ) -> Relevance | Unavailable:
        match kind:
            case "not_drawing":
                return Relevance(verdict="unrelated", why=NOT_DRAWING_WHY, judge=JUDGE)
            case "other_drawing":
                return Relevance(verdict="related", why=OTHER_DRAWING_WHY, judge=JUDGE)
            case "floor_plan":
                return Unavailable(note="a floor plan is read, not judged")
