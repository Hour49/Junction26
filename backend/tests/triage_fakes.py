"""Fakes of file triage's three ports (decision 0010), for the ingest and API tests and the
API fixtures: answers keyed by a file's bytes, and a judge that matches words."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.core import cost
from app.core.ingest.model import (
    Classified,
    Description,
    Probed,
    ProjectContext,
    Register,
    Relevance,
    TriageClass,
    Unavailable,
)
from app.core.ingest.triage import TriageSteps

METHOD = "fake classifier"


@dataclass
class FakeClassifier:
    """`answers`: the class per file's bytes; any other image is a floor plan (P 0.97).
    `registers`: per file's bytes, the register it reads, its class derived from it."""

    answers: Mapping[bytes, TriageClass]
    unavailable: bool = False
    registers: Mapping[bytes, Register] = field(default_factory=dict[bytes, Register])
    asked: list[str] = field(default_factory=list[str])  # the probe kinds it was asked about

    def classify(self, image: bytes, probed: Probed) -> Classified | Unavailable:
        self.asked.append(probed.kind)
        if self.unavailable:
            return Unavailable(note="the classifier is not reachable")
        register = self.registers.get(image)
        if register is not None:
            p_plan = 0.97 if register.has_floor_plan else 0.03
            return Classified.model_validate(
                {"p_plan": p_plan, "method": METHOD, "register": register}
            )
        found = self.answers.get(image, "floor_plan")
        p_plan = 0.97 if found == "floor_plan" else 0.03
        return Classified.model_validate({"class": found, "p_plan": p_plan, "method": METHOD})


@dataclass
class FakeDescriber:
    """`subjects`: per file's bytes, its subject and the words printed on it; any other file:
    the model refused. `buildings`: the files it says show a building. Each description costs
    `usd`."""

    subjects: Mapping[bytes, tuple[str, tuple[str, ...]]]
    usd: float = 0.0
    buildings: frozenset[bytes] = frozenset()

    def describe(self, image: bytes, classified: Classified) -> Description | Unavailable:
        if image not in self.subjects:
            return Unavailable(note="the model refused")
        cost.charge(self.usd)
        subject, seen = self.subjects[image]
        return Description(
            text=f"A picture of {subject}.",
            subject=subject,
            text_seen=seen,
            language="en" if seen else None,
            model="fake describer",
            cost_usd=self.usd,
            what_it_is="drawing",
            shows_building=image in self.buildings,
            visible_text="\n".join(seen),
            detail=f"A longer account of {subject}, for later use.",
        )


@dataclass
class WordJudge:
    """Related when a word printed on the file is in the project's plan text or file names,
    else unrelated. Each verdict costs `usd`; it names one plan id that is not the project's,
    which ingest must drop."""

    usd: float = 0.0
    contexts: list[ProjectContext] = field(default_factory=list[ProjectContext])

    reads_description = True

    def judge(
        self, kind: TriageClass, description: Description | None, context: ProjectContext
    ) -> Relevance | Unavailable:
        if description is None:
            return Unavailable(note="there is no description to judge")
        self.contexts.append(context)
        cost.charge(self.usd)
        known = " ".join((*context.plan_text, *context.file_names)).lower()
        matched = tuple(word for word in description.text_seen if word.lower() in known)
        if matched:
            return Relevance(
                verdict="related",
                why=f"Related: {', '.join(matched)} is on the project's plans.",
                matched_on=matched,
                plans=(*context.plans, "another-projects-drawing"),
                judge="word judge",
            )
        why = "Unrelated: no word on it is on the project's plans or in its file names."
        return Relevance(verdict="unrelated", why=why, judge="word judge")


def steps(
    classifier: FakeClassifier,
    describer: FakeDescriber | None = None,
    judge: WordJudge | None = None,
) -> TriageSteps:
    return TriageSteps(classifier=classifier, describer=describer, judge=judge, name="fakes")
