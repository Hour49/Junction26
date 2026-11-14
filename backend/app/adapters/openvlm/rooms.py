"""Rooms of a raster plan read by an open model on our EU server (the G4 room reader's twin).

`OpenVlmRoomModel` is a `RoomModel`, so `GeminiRoomReader` does the rest exactly as for Gemini:
arm G4's prompt, the page encoding (long side 2048), the reply parsing (salvage of cut replies,
loop and repeat drops, bathrooms once per label) and the disk cache keyed by the decoded page,
the prompt version and the model name. Thinking is off and decoding greedy.

`native_boxes=True` (the default) asks for box_2d in Qwen's own order [xmin, ymin, xmax, ymax]
and turns every box_2d in the reply back into G4's [ymin, xmin, ymax, xmax] before G4's parser
reads it. With G4's y-first wording Qwen's boxes are often off, and region's main-flat mask then
drops real rooms (val, Qwen3.8-27B: region mask -0.6 pp with y-first, +0.5 pp with native boxes,
bedrooms +6.2; .agents/exp/eu.md arm E2-rooms-p1-regpred). The cache name carries "-xy".

`OpenVlmRoomExtractor` is the `Extractor`. When the server fails, the sheet's rooms are not read
(`read` is empty, the note says why): nothing falls back to Gemini or another reader.
"""

import io
import re

from PIL import Image

from app.adapters.openvlm.client import OpenVlmClient, OpenVlmError, image_part
from app.adapters.raster_ocr.gemini import GeminiError, GeminiRoomReader
from app.core.drawing.model import Room, Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles

MAX_TOKENS = 8192  # a page has ~10-40 rooms of ~25 tokens; more is a generation loop
Y_FIRST = "[ymin, xmin, ymax, xmax]"
X_FIRST = "[xmin, ymin, xmax, ymax]"
BOX = re.compile(r'("box_2d"\s*:\s*\[)\s*([^,\]]+),\s*([^,\]]+),\s*([^,\]]+),\s*([^,\]]+)\]')


def y_first(text: str) -> str:
    """Every `"box_2d": [x1, y1, x2, y2]` of a reply as `[y1, x1, y2, x2]`, the rest unchanged."""
    return BOX.sub(lambda m: f"{m[1]}{m[3]}, {m[2]}, {m[5]}, {m[4]}]", text)


class OpenVlmRoomModel:
    def __init__(
        self, client: OpenVlmClient, max_tokens: int = MAX_TOKENS, native_boxes: bool = True
    ) -> None:
        self._client = client
        self._max_tokens = max_tokens
        self._native = native_boxes

    @property
    def name(self) -> str:
        return f"eu-{self._client.model}" + ("-xy" if self._native else "")

    def __repr__(self) -> str:
        return f"OpenVlmRoomModel({self._client.model})"

    def ask(self, png: bytes, prompt: str) -> str:
        """The reply text; raises `GeminiError` (the `RoomModel` port's error) on any failure."""
        if self._native:
            if Y_FIRST not in prompt:
                raise GeminiError("the room prompt no longer names the box order")
            prompt = prompt.replace(Y_FIRST, X_FIRST)
        body = {
            "messages": [
                {"role": "user", "content": [image_part(png), {"type": "text", "text": prompt}]}
            ],
            "max_tokens": self._max_tokens,
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            reply = self._client.chat(body)
        except OpenVlmError as error:
            raise GeminiError(f"eu {self._client.model}: {error}") from None
        text = (reply["choices"][0].get("message") or {}).get("content") or ""
        if not str(text).strip():
            reason = reply["choices"][0].get("finish_reason", "")
            raise GeminiError(f"eu {self._client.model}: empty answer ({reason})")
        return y_first(str(text)) if self._native else str(text)


class OpenVlmRoomExtractor:
    """The EU room reader behind the `Extractor` port; it looks for rooms only."""

    def __init__(self, files: DrawingFiles, reader: GeminiRoomReader) -> None:
        self._files = files
        self._reader = reader

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        data = self._files.read(source.path)
        with Image.open(io.BytesIO(data)) as image:
            try:
                found = self._reader.read(image)
            except GeminiError as error:
                return Extracted(
                    method="printed_label",
                    scale=Scale(status="no_scale"),
                    read=(),
                    notes=(f"eu: rooms not read: {error}",),
                )
        rooms = tuple(
            Room(
                id=f"r{index}",
                type=kind,
                label=label or None,
                page=1,
                box=box,
                outdoor=kind in ("balcony", "outdoor"),
                attrs={"reader": "eu"},
            )
            for index, (kind, label, box) in enumerate(found.rooms, start=1)
        )
        return Extracted(
            method="printed_label",
            scale=Scale(status="no_scale"),
            rooms=rooms,
            read=("room",),
            notes=(f"eu: {found.note}",),
        )
