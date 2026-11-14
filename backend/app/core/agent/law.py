"""The building-rule parts of an edit turn's answer (spec plan-edit-law-check LC-8, LC-9c): words
a pre-check must not use, rules the text must name, and the sentences the server writes when the
model does not. Pure: the law check is the plan tool's result as the model read it (with ev ids)."""

import re
from typing import Any

Json = dict[str, Any]

# A pre-check of a few rules is never a verdict on the law (LC-8; "allowed" shows up innocently)
BANNED = re.compile(r"\b(legal|illegal|compliant|permitted)\b", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?])\s+")
CARD = "The proposed change is shown below."  # what is left when every sentence had to go


def banned(text: str) -> list[str]:
    return sorted({word.lower() for word in BANNED.findall(text)})


def without_banned(text: str) -> str:
    """`text` without its sentences that use a banned word."""
    kept = [sentence for sentence in SENTENCE.split(text) if not BANNED.search(sentence)]
    return " ".join(kept).strip() or CARD


def newly_failing(law: Json | None) -> list[Json]:
    """The law check's findings the change newly breaks."""
    findings: list[Json] = (law or {}).get("findings") or []
    return [f for f in findings if f.get("change") == "newly_fails"]


def uncited(law: Json | None, text: str) -> list[Json]:
    """The newly failing findings, when the text cites none of them; [] when it cites one."""
    failing = newly_failing(law)
    cited = set(re.findall(r"ev_\d+", text))
    return [] if any(f.get("ev") in cited for f in failing) else failing


def appended(text: str, failing: int, pack_name: str) -> str:
    """The server's sentence for rules the text did not name (LC-8)."""
    rules = "rule" if failing == 1 else "rules"
    return (
        f"{text} This change would not meet {failing} {rules} of {pack_name}: see Building rules."
    )
