"""The EU open-model adapter (app/adapters/openvlm/): client, choice probabilities from log
probabilities, and the Gemini ports it fills (RoomModel, Decider). Scripted transports only, no
network and no data/."""

import base64
import io
import json
import math
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.adapters.decisions.client import DecisionsError
from app.adapters.decisions.g1main import FAMILIES, G1MainReader
from app.adapters.decisions_kind import KINDS, KindReader, KindSignal, KindUnavailable
from app.adapters.openvlm.client import OpenVlmClient, OpenVlmError
from app.adapters.openvlm.decider import MAX_SIDE, OpenVlmDecider, options_of, read_joint, walk
from app.adapters.openvlm.rooms import OpenVlmRoomExtractor, OpenVlmRoomModel, y_first
from app.adapters.raster_ocr.gemini import GeminiRoomReader
from app.core.drawing.model import Page
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Sheet

KEY = "secret-eu-key"
FILE = DrawingFile(path="data/cubicasa5k/x.png", size=1, sha256="0" * 64, kind="png")
SHEET = Sheet(file=FILE, pages=(Page(page=1, width=40, height=30, unit="px"),))


def png(width: int = 40, height: int = 30) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


class Transport:
    """Scripted (status, payload) replies; an Exception payload is raised. Records what was sent."""

    def __init__(self, replies: list[tuple[int, Any]]) -> None:
        self.replies = replies
        self.sent: list[tuple[str, dict[str, Any], str]] = []

    def __call__(self, url: str, body: bytes, key: str, timeout: float) -> tuple[int, bytes]:
        self.sent.append((url, json.loads(body), key))
        status, payload = self.replies.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return status, json.dumps(payload).encode()


def client(transport: Any, sleeps: list[float] | None = None) -> OpenVlmClient:
    return OpenVlmClient(
        "http://127.0.0.1:18431/v1/", KEY, "Qwen/Q", 5.0, transport,
        sleep=(sleeps if sleeps is not None else []).append,
    )  # fmt: skip


def text_reply(text: str, finish: str = "stop") -> dict[str, Any]:
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10}}  # fmt: skip


# ---- client ------------------------------------------------------------------------------------


def test_the_key_goes_in_the_header_and_the_model_in_the_body() -> None:
    transport = Transport([(200, text_reply("hi"))])
    assert client(transport).chat({"messages": []})["choices"][0]["message"]["content"] == "hi"
    url, body, key = transport.sent[0]
    assert url == "http://127.0.0.1:18431/v1/chat/completions"
    assert key == KEY and body["model"] == "Qwen/Q" and KEY not in json.dumps(body)


def test_429_and_5xx_are_retried_with_backoff_and_400_is_not() -> None:
    sleeps: list[float] = []
    transport = Transport([(429, {}), (503, {}), (200, text_reply("ok"))])
    client(transport, sleeps).chat({})
    assert len(transport.sent) == 3 and sleeps == [1.0, 2.0]
    transport = Transport([(400, {"error": {"type": "BadRequestError", "message": KEY}})])
    with pytest.raises(OpenVlmError) as error:
        client(transport).chat({})
    assert str(error.value) == "HTTP 400 BadRequestError" and len(transport.sent) == 1


def test_a_server_that_stays_down_and_a_network_failure_are_errors() -> None:
    with pytest.raises(OpenVlmError, match="HTTP 502"):
        client(Transport([(502, {})] * 4)).chat({})
    with pytest.raises(OpenVlmError, match="no answer: TimeoutError"):
        client(Transport([(0, TimeoutError(KEY))])).chat({})


def test_no_key_or_url_refuses_to_start() -> None:
    with pytest.raises(InvalidInputError, match="EU_VLM_API_KEY"):
        OpenVlmClient("http://x/v1", "", "m", 1.0)
    with pytest.raises(InvalidInputError, match="EU_VLM_BASE_URL"):
        OpenVlmClient("", KEY, "m", 1.0)


# ---- choice probabilities ----------------------------------------------------------------------


def test_a_two_digit_count_multiplies_the_digit_probabilities() -> None:
    options = [str(k) for k in range(15)]
    table = {
        "": [("1", 0.6), ("3", 0.3), ("x", 0.1)],
        "1": [("2", 0.5), ("<|im_end|>", 0.25), ("0", 0.25)],
    }
    asked: list[str] = []

    def step(prefix: str) -> list[tuple[str, float]]:
        asked.append(prefix)
        return table[prefix]

    probs = walk(options, step)
    # "3", "10" and "12" cannot grow into a longer option (<= 14): they end without another
    # call; "x" reaches no option and its share is renormalised away
    assert asked == ["", "1"]
    assert math.isclose(probs["12"], 0.6 * 0.5 / 0.9)
    assert math.isclose(probs["1"], 0.6 * 0.25 / 0.9)
    assert math.isclose(probs["10"], 0.6 * 0.25 / 0.9)
    assert math.isclose(probs["3"], 0.3 / 0.9)
    assert math.isclose(sum(probs.values()), 1.0)


def test_a_prefix_below_the_floor_is_not_continued_and_no_option_is_an_error() -> None:
    probs = walk(["1", "10", "2"], lambda p: {"": [("1", 0.005), ("2", 0.995)]}[p])
    assert probs == {"1": 0.0, "10": 0.0, "2": 1.0}
    with pytest.raises(DecisionsError, match="no option"):
        walk(["1", "2"], lambda p: [("x", 1.0)])


def test_described_options_become_letters_and_counts_stay_numbers() -> None:
    letters, prompt = options_of({"type": "choice", "criteria": {"plan": "a plan", "photo": ""}})
    assert letters == ["A", "B"] and "A. a plan\nB. photo\n" in prompt
    numbers, prompt = options_of({"type": "choice", "criteria": {"0": "", "1": "", "2": ""}})
    assert numbers == ["0", "1", "2"] and prompt == "Answer with the number only (0 to 2)."


def logprob_reply(tokens: list[tuple[str, float]]) -> dict[str, Any]:
    top = [{"token": t, "logprob": math.log(p)} for t, p in tokens]
    step = {"token": tokens[0][0], "top_logprobs": top}
    return {"choices": [{"message": {"content": tokens[0][0]}, "logprobs": {"content": [step]}}],
            "usage": {"prompt_tokens": 7}}  # fmt: skip


class Server:
    """Answers every step of every question: the first token from `first` (by question text),
    end of answer after it."""

    def __init__(self, first: dict[str, list[tuple[str, float]]]) -> None:
        self.first = first
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, url: str, body: bytes, key: str, timeout: float) -> tuple[int, bytes]:
        sent = json.loads(body)
        self.bodies.append(sent)
        if sent["messages"][-1]["role"] == "assistant":
            return 200, json.dumps(logprob_reply([("<|im_end|>", 1.0)])).encode()
        text = sent["messages"][0]["content"][-1]["text"]
        tokens = next((v for k, v in self.first.items() if k in text), [("0", 1.0)])
        return 200, json.dumps(logprob_reply(tokens)).encode()


def test_g1main_runs_on_the_eu_decider_and_its_replies_are_cached(tmp_path: Path) -> None:
    server = Server({"How many saunas": [("1", 0.7), ("0", 0.3)], "toilet bowls": [("1", 1.0)]})
    decider = OpenVlmDecider(client(server))
    counts = G1MainReader(decider, tmp_path).read(png(3000, 1500))
    assert set(counts.families) == set(FAMILIES)
    assert math.isclose(counts.families["sauna"].p(1), 0.7) and counts.families["sauna"].top == 1
    assert counts.families["toilet"].top == 1 and counts.families["door"].top == 0
    first = server.bodies[0]
    assert first["max_tokens"] == 1 and first["top_logprobs"] == 20
    assert first["chat_template_kwargs"] == {"enable_thinking": False}
    sent = first["messages"][0]["content"][0]["image_url"]["url"].split(",", 1)[1]
    assert Image.open(io.BytesIO(base64.b64decode(sent))).size == (MAX_SIDE, MAX_SIDE // 2)
    follow = next(b for b in server.bodies if b["messages"][-1]["role"] == "assistant")
    assert follow["continue_final_message"] and not follow["add_generation_prompt"]
    asked = len(server.bodies)
    G1MainReader(decider, tmp_path).read(png(3000, 1500))
    assert len(server.bodies) == asked  # the second read is the cache
    assert "eu-Qwen_Q" in next(tmp_path.iterdir()).name


def test_the_kind_signal_runs_on_the_eu_decider_and_an_outage_is_declared() -> None:
    server = Server({"first page": [("D", 0.95), ("A", 0.05)]})  # D = photo_plan
    signal = KindReader(OpenVlmDecider(client(server)), None).read(png())
    assert isinstance(signal, KindSignal) and list(KINDS)[3] == "photo_plan"
    assert signal.photo and math.isclose(signal.p_plan, 0.05)
    down = KindReader(OpenVlmDecider(client(Transport([(500, {})] * 4))), None).read(png())
    assert isinstance(down, KindUnavailable)
    assert down.note == "kind signal not available: eu Qwen/Q: HTTP 500"


def test_joint_answers_are_read_at_each_lines_position() -> None:
    steps = [
        ("door", [("door", 1.0)]), (":", [(":", 1.0)]), (" ", [(" ", 1.0)]),
        ("1", [("1", 0.6), ("9", 0.3), ("x", 0.1)]),  # door: 12 greedy; 9 is one digit
        ("2", [("2", 0.5), ("\n", 0.5)]),
        ("\n", [("\n", 1.0)]), ("sauna", [("sauna", 1.0)]), (":", [(":", 1.0)]),
        (" 1", [(" 1", 0.8), (" 0", 0.2)]),
    ]  # fmt: skip
    probs = read_joint(steps, [("door", [str(k) for k in range(44)]), ("sauna", ["0", "1", "2"])])
    assert math.isclose(probs["door"]["12"], 0.3 / 0.9)
    assert math.isclose(probs["door"]["1"], 0.3 / 0.9)  # "1" then the line ends
    assert math.isclose(probs["door"]["9"], 0.3 / 0.9)
    assert probs["sauna"] == {"0": 0.2 / 1.0, "1": 0.8 / 1.0, "2": 0.0}
    with pytest.raises(DecisionsError, match="no line for wc"):
        read_joint(steps, [("wc", ["0", "1"])])


def test_the_joint_decider_asks_once_and_names_its_own_cache(tmp_path: Path) -> None:
    lines = "\n".join(f"g1_{key}: 1" for key, _, _ in FAMILIES.values())
    tokens = [t for line in lines.split("\n") for t in (line.split(" ")[0], " ", "1", "\n")]
    content = [{"token": t, "top_logprobs": [{"token": t, "logprob": 0.0}]} for t in tokens]
    reply = {"choices": [{"message": {"content": lines}, "logprobs": {"content": content}}],
             "usage": {"prompt_tokens": 9}}  # fmt: skip
    transport = Transport([(200, reply)])
    decider = OpenVlmDecider(client(transport), joint=True)
    counts = G1MainReader(decider, tmp_path).read(png())
    assert len(transport.sent) == 1 and decider.calls == 1
    assert all(dist.top == 1 for dist in counts.families.values())
    assert "-joint" in next(tmp_path.iterdir()).name


# ---- rooms -------------------------------------------------------------------------------------


class Files:
    def read(self, path: str) -> bytes:
        return png()


ROOMS = '[{"type": "bedroom", "label": "MH", "box_2d": [100, 200, 300, 400]}, {"type": "wc"}]'


def test_the_eu_room_reader_reuses_g4_parsing_and_marks_its_rooms(tmp_path: Path) -> None:
    transport = Transport([(200, text_reply(ROOMS))])
    reader = GeminiRoomReader(OpenVlmRoomModel(client(transport)), tmp_path)
    found = OpenVlmRoomExtractor(Files(), reader).extract(FILE, SHEET)
    assert [(r.type, r.label) for r in found.rooms] == [("bedroom", "MH"), ("wc", None)]
    # native box order: the reply's [100, 200, 300, 400] is x first
    assert found.rooms[0].box == (0.1, 0.2, 0.3, 0.4) and found.read == ("room",)
    assert found.rooms[0].attrs == {"reader": "eu"}
    assert found.notes[0].startswith("eu: eu-Qwen/Q-xy")
    body = transport.sent[0][1]
    assert body["temperature"] == 0 and body["chat_template_kwargs"] == {"enable_thinking": False}
    asked = body["messages"][0]["content"][1]["text"]
    assert "[xmin, ymin, xmax, ymax]" in asked and "[ymin, xmin, ymax, xmax]" not in asked


def test_g4_box_order_stays_available_and_boxes_are_turned_only_in_box_2d() -> None:
    transport = Transport([(200, text_reply(ROOMS))])
    reader = GeminiRoomReader(OpenVlmRoomModel(client(transport), native_boxes=False), None)
    found = OpenVlmRoomExtractor(Files(), reader).extract(FILE, SHEET)
    assert found.rooms[0].box == (0.2, 0.1, 0.4, 0.3)
    assert "[ymin, xmin, ymax, xmax]" in transport.sent[0][1]["messages"][0]["content"][1]["text"]
    text = '[{"label": "MH [1, 2, 3, 4]", "box_2d": [10, 20.5, 30, 40]}, {"box_2d":[1,2,3,4]}]'
    assert y_first(text) == (
        '[{"label": "MH [1, 2, 3, 4]", "box_2d": [20.5, 10, 40, 30]}, {"box_2d":[2, 1, 4, 3]}]'
    )


def test_a_failed_eu_call_leaves_rooms_unread_and_never_falls_back() -> None:
    transport = Transport([(401, {"error": {"type": "Unauthorized"}})])
    reader = GeminiRoomReader(OpenVlmRoomModel(client(transport)), None)
    found = OpenVlmRoomExtractor(Files(), reader).extract(FILE, SHEET)
    assert found.rooms == () and found.read == ()
    assert found.notes == ("eu: rooms not read: eu Qwen/Q: HTTP 401 Unauthorized",)
    empty = Transport([(200, text_reply("", finish="length"))])
    found = OpenVlmRoomExtractor(Files(), GeminiRoomReader(OpenVlmRoomModel(client(empty)), None))
    assert found.extract(FILE, SHEET).notes == (
        "eu: rooms not read: eu Qwen/Q: empty answer (length)",
    )
