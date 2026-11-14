"""`OpenVlmDecider`: the Gemini Decisions port (`Decider`) answered by an open model on vLLM.

A Decisions request holds input blocks (images, text) and closed `choice` questions; the reply
gives every option's probability. Here each question is one prompt, and the option
probabilities come from the model's next-token log probabilities (top 20), not from sampling:

- Count questions (options "0".."K", no descriptions) are answered as a number. A count with
  more than one digit is read token by token: the walk continues an answer prefix ("1") while it
  can still grow into a longer option ("12") and holds at least MIN_MASS of the probability, and a
  prefix that is an option ends where the next token is not a digit. Qwen's tokenizer writes one
  digit per token, so P(12) = P("1") P("2" | "1") P(end | "12").
- Other questions list the options as letters A, B, ... (with their descriptions) and read the
  letter's probability.

Probability no option reaches (other tokens, prefixes under MIN_MASS) is dropped and the rest
renormalised. Pages are sent with the long side at most MAX_SIDE (never enlarged), like the room
reader's.

`joint=True` asks all of a request's questions in one prompt, one reply line each
("<key>: <answer>"), and reads every answer's probabilities from the log probabilities at its
position in that one greedy reply: one image prefill per page instead of one per step (the
hybrid Qwen models get little from vLLM's prefix cache). A two-digit count is followed only
along the reply's own first digit (P(12) = P("1") P("2" | "1")); another first digit counts as
that one-digit answer. Approximate where the walk is exact; the A/B says what it costs.
"""

import base64
import io
import math
from typing import Any, cast

from PIL import Image

from app.adapters.decisions.client import DecisionsError
from app.adapters.openvlm.client import Json, OpenVlmClient, OpenVlmError, image_part

MAX_SIDE = 2048
MIN_MASS = 0.01  # a prefix with less probability than this is not continued
TOP = 20  # top log probabilities per step (vLLM --max-logprobs must allow it)
MAX_CALLS = 60  # per question: a walk that needs more is an error, not a guess
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def page_png(data: bytes) -> bytes:
    """The image as sent: RGB PNG, long side at most MAX_SIDE (Lanczos down, never up)."""
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except OSError as error:
        raise DecisionsError(f"the input is not an image: {error}") from None
    scale = MAX_SIDE / max(image.size)
    if scale < 1:
        size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(size, Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def options_of(question: dict[str, Any]) -> tuple[list[str], str]:
    """(the answer strings in the criteria's order, the instruction that lists them)."""
    criteria = cast(dict[str, str], question.get("criteria") or {})
    if question.get("type") != "choice" or not criteria:
        raise DecisionsError("only choice questions with criteria are supported")
    keys = list(criteria)
    if all(k.isdigit() for k in keys) and not any(criteria.values()):
        return keys, f"Answer with the number only ({keys[0]} to {keys[-1]})."
    if len(keys) > len(LETTERS):
        raise DecisionsError("too many options")
    listed = "\n".join(f"{LETTERS[i]}. {criteria[k] or k}" for i, k in enumerate(keys))
    return list(LETTERS[: len(keys)]), f"Options:\n{listed}\nAnswer with the letter only."


def walk(options: list[str], step: Any) -> dict[str, float]:
    """Each option's probability. `step(prefix)` gives [(token, probability)] for the token after
    the answer prefix (the first token for ""). See the module docstring."""
    found = dict.fromkeys(options, 0.0)
    frontier: list[tuple[str, float]] = [("", 1.0)]
    calls = 0
    while frontier:
        prefix, mass = frontier.pop()
        calls += 1
        if calls > MAX_CALLS:
            raise DecisionsError(f"more than {MAX_CALLS} calls for one question")
        for token, p in step(prefix):
            text = token if prefix else token.lstrip()
            grown = prefix + text
            share = mass * p
            if text and any(o.startswith(grown) for o in options):
                longer = any(o != grown and o.startswith(grown) for o in options)
                if grown in found and not longer:
                    found[grown] += share  # nothing longer to become: it ends here
                elif share >= MIN_MASS:
                    frontier.append((grown, share))
            elif prefix in found:
                found[prefix] += share  # the answer stops at the prefix
    total = sum(found.values())
    if total <= 0:
        raise DecisionsError("no option among the model's likely answers")
    return {o: v / total for o, v in found.items()}


JOINT = (
    "Answer every question below about the image, in order, one line per question in the form "
    "`<question name>: <answer>`, and nothing else."
)


def read_joint(
    steps: list[tuple[str, list[tuple[str, float]]]], specs: list[tuple[str, list[str]]]
) -> dict[str, dict[str, float]]:
    """Each question's option probabilities from one reply. `steps` is the reply as (token, top
    tokens with probabilities) per position; `specs` is (question key, option strings) in the
    order asked. See the module docstring."""
    starts, at = [], 0
    for token, _ in steps:
        starts.append(at)
        at += len(token)
    text = "".join(token for token, _ in steps)
    out: dict[str, dict[str, float]] = {}
    cursor = 0
    for key, options in specs:
        colon = text.find(f"{key}:", cursor)
        if colon < 0:
            raise DecisionsError(f"the joint answer has no line for {key}")
        cursor = colon + len(key) + 1
        i = next((n for n, s in enumerate(starts) if s >= cursor and steps[n][0].strip()), None)
        if i is None:
            raise DecisionsError(f"the joint answer has no value for {key}")
        found = dict.fromkeys(options, 0.0)
        greedy = steps[i][0].strip()
        for token, p in steps[i][1]:
            first = token.strip()
            if not first or not any(o.startswith(first) for o in options):
                continue
            longer = any(o != first and o.startswith(first) for o in options)
            if first == greedy and longer and i + 1 < len(steps):
                for token2, p2 in steps[i + 1][1]:
                    grown = first + token2
                    if grown in found:
                        found[grown] += p * p2
                    elif first in found:
                        found[first] += p * p2  # the answer stops after the first token
            elif first in found:
                found[first] += p
        total = sum(found.values())
        if total <= 0:
            raise DecisionsError(f"no option among the model's likely answers for {key}")
        out[key] = {o: v / total for o, v in found.items()}
    return out


class OpenVlmDecider:
    def __init__(self, client: OpenVlmClient, joint: bool = False) -> None:
        self._client = client
        self._joint = joint
        self.calls = 0
        self.prompt_tokens = 0

    @property
    def model(self) -> str:
        return f"eu-{self._client.model}" + ("-joint" if self._joint else "")

    def __repr__(self) -> str:
        return f"OpenVlmDecider({self._client.model})"

    def decide(self, body: Json) -> Json:
        parts = [self._part(block) for block in body.get("input") or []]
        if not parts:
            raise DecisionsError("the request has no input")
        answers: Json = {}
        if self._joint:
            return self._decide_joint(parts, body.get("questions") or {})
        for key, question in (body.get("questions") or {}).items():
            strings, instruction = options_of(question)
            text = f"{question.get('instructions', '')}\n{instruction}"
            probs = walk(strings, lambda prefix, text=text: self._step(parts, text, prefix))
            keys = list(question["criteria"])
            answers[key] = {"probabilities": dict(zip(keys, probs.values(), strict=True))}
        return {"answers": answers, "usage": {"total_input_tokens": self.prompt_tokens}}

    def _decide_joint(self, parts: list[Json], questions: dict[str, Any]) -> Json:
        lines, specs = [], []
        for key, question in questions.items():
            strings, instruction = options_of(question)
            lines.append(f"{key}: {question.get('instructions', '')} {instruction}")
            specs.append((key, strings))
        text = JOINT + "\n\n" + "\n".join(lines)
        body: Json = {
            "messages": [{"role": "user", "content": [*parts, {"type": "text", "text": text}]}],
            "max_tokens": 16 * len(specs) + 16,
            "temperature": 0,
            "logprobs": True,
            "top_logprobs": TOP,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        reply = self._chat(body)
        try:
            content = reply["choices"][0]["logprobs"]["content"]
            steps = [
                (str(c["token"]), [(str(t["token"]), math.exp(float(t["logprob"])))
                                   for t in c["top_logprobs"]])
                for c in content
            ]  # fmt: skip
        except (KeyError, IndexError, TypeError, ValueError):
            raise DecisionsError("the answer has no log probabilities") from None
        probs = read_joint(steps, specs)
        answers = {
            key: {
                "probabilities": dict(zip(question["criteria"], probs[key].values(), strict=True))
            }
            for key, question in questions.items()
        }
        return {"answers": answers, "usage": {"total_input_tokens": self.prompt_tokens}}

    def _chat(self, body: Json) -> Json:
        try:
            reply = self._client.chat(body)
        except OpenVlmError as error:
            raise DecisionsError(f"eu {self._client.model}: {error}") from None
        self.calls += 1
        self.prompt_tokens += int((reply.get("usage") or {}).get("prompt_tokens") or 0)
        return reply

    @staticmethod
    def _part(block: Json) -> Json:
        if block.get("type") == "image":
            return image_part(page_png(base64.b64decode(block["data"])))
        if block.get("type") == "text":
            return {"type": "text", "text": str(block.get("text", ""))}
        raise DecisionsError(f"unsupported input block {block.get('type')!r}")

    def _step(self, parts: list[Json], text: str, prefix: str) -> list[tuple[str, float]]:
        messages: list[Json] = [
            {"role": "user", "content": [*parts, {"type": "text", "text": text}]}
        ]
        body: Json = {
            "messages": messages,
            "max_tokens": 1,
            "temperature": 0,
            "logprobs": True,
            "top_logprobs": TOP,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if prefix:
            messages.append({"role": "assistant", "content": prefix})
            body |= {"add_generation_prompt": False, "continue_final_message": True}
        reply = self._chat(body)
        try:
            top = reply["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
            return [(str(t["token"]), math.exp(float(t["logprob"]))) for t in top]
        except (KeyError, IndexError, TypeError, ValueError):
            raise DecisionsError("the answer has no log probabilities") from None
