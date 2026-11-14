"""Chats on disk (spec AC-23): `<projects_dir>/<project id>/chats/<chat id>.json`, written whole
on every turn. The assistant messages are kept verbatim (Gemini's thought signatures)."""

import json
import re
import secrets
import threading
from pathlib import Path

from app.adapters.paths import inside
from app.adapters.whole_file import write_whole
from app.core.agent.model import Chat, ChatTurn
from app.core.errors import NotFoundError
from app.core.plan_edit.model import Proposal

CHAT_ID = re.compile(r"[0-9a-f]{12}")


class JsonChatStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def new(self) -> Chat:
        return Chat(secrets.token_hex(6))

    def get(self, project_id: str, chat_id: str) -> Chat:
        path = self._path(project_id, chat_id)
        if not path.is_file():
            raise NotFoundError(f"project {project_id} has no chat {chat_id!r}")
        found = json.loads(path.read_text(encoding="utf-8"))
        return Chat(
            chat_id,
            messages=found["messages"],
            starts=found["starts"],
            turns=[ChatTurn.model_validate(turn) for turn in found["turns"]],
            proposals={k: Proposal.model_validate(p) for k, p in found["proposals"].items()},
            results=found["results"],
            minted=found["minted"],
            evidence=found.get("evidence", {}),  # chats written before item 1 have none
            asked=found.get("asked", []),
        )

    def put(self, project_id: str, chat: Chat) -> None:
        body = {
            "chat_id": chat.chat_id,
            "messages": chat.messages,
            "starts": chat.starts,
            "turns": [turn.model_dump(mode="json") for turn in chat.turns],
            "proposals": {k: p.model_dump(mode="json") for k, p in chat.proposals.items()},
            "results": chat.results,
            "minted": chat.minted,
            "evidence": chat.evidence,
            "asked": chat.asked,
        }
        write_whole(self._path(project_id, chat.chat_id), json.dumps(body, ensure_ascii=False))

    def lock(self, chat_id: str) -> threading.Lock:
        """The lock one turn of the chat holds: one turn at a time per chat (AC-22)."""
        with self._guard:
            return self._locks.setdefault(chat_id, threading.Lock())

    def _path(self, project_id: str, chat_id: str) -> Path:
        if not CHAT_ID.fullmatch(chat_id):
            raise NotFoundError(f"project {project_id} has no chat {chat_id!r}")
        return inside(self._root, project_id) / "chats" / f"{chat_id}.json"
