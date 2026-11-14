"""TRIAGE_CLASSIFIER=rules: the triage classifier with no model, from the content probe's kind.

It sets aside exactly what ingest sets aside today: a camera photo not of a drawing (`photo`) and
an image the kind signal calls not a drawing (`unknown`). Every other image is unsure, and unsure
means floor plan, so it is read as today. It costs nothing and needs no key, so the offline demo
shows triage on the files it would set aside anyway: classified, with no description (no
description model is set up)."""

from app.core.ingest.model import Classified, Probed

METHOD = "rules: the content probe's kind, no model"
NOT_DRAWING = frozenset({"photo", "unknown"})


class RulesClassifier:
    def classify(self, image: bytes, probed: Probed) -> Classified:
        if probed.kind in NOT_DRAWING:
            found = {"class": "not_drawing", "p_plan": 0.0, "method": METHOD}
        else:  # unsure, so a floor plan: read as today
            found = {"class": "floor_plan", "p_plan": 0.5, "method": METHOD}
        return Classified.model_validate(found)
