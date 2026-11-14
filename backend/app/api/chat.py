"""The project chat agent (decision 0013, docs/API.md "Chat"): one turn per POST, the chat kept on
the server, plan edits as proposals a person accepts or rejects. Sync routes: the model client
blocks, so FastAPI runs them in its thread pool."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field

from app.adapters.agent_tools import project_toolbox
from app.adapters.chat_store import JsonChatStore
from app.api.deps import IngestDep, ProjectId, SettingsDep
from app.api.views import View, drawings_of
from app.composition import chat_caps, chat_model, spend_guard
from app.core.agent.loop import run_turn
from app.core.agent.model import ChatTurn
from app.core.errors import NotFoundError
from app.core.plan_edit.model import Proposal, Selection
from app.core.review.review import NotAllowedError

router = APIRouter(prefix="/api/projects")

MESSAGE_CHARS = 2000


class ChatRequest(View):
    chat_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{12}$")
    message: str = Field(min_length=1, max_length=MESSAGE_CHARS)
    selection: list[Selection] = Field(default_factory=list[Selection], max_length=8)


class Decision(View):
    action: Literal["accept", "reject"]


def get_chats(request: Request) -> JsonChatStore:
    return request.app.state.chats


ChatsDep = Annotated[JsonChatStore, Depends(get_chats)]


@router.post("/{project_id}/chat", responses={503: {"description": "CHAT_MODEL=off"}})
def chat(
    project_id: ProjectId,
    body: ChatRequest,
    request: Request,
    ingest: IngestDep,
    settings: SettingsDep,
    chats: ChatsDep,
) -> ChatTurn:
    model, why = chat_model(settings)
    if model is None:
        raise HTTPException(503, why)
    status = ingest.status(project_id)  # 404 for an unknown project
    if status.state != "done":
        raise NotAllowedError(f"project {project_id} is {status.state}; ask again when it is done")
    found = chats.get(project_id, body.chat_id) if body.chat_id else chats.new()
    lock = chats.lock(found.chat_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "a turn is still running")
    try:
        current = chats.get(project_id, found.chat_id) if body.chat_id else found
        tools = project_toolbox(request.app, project_id, body.selection, current.proposals)
        names = {entry.drawing_id: entry.name for entry in drawings_of(status)}
        guard = spend_guard(settings)
        caps = chat_caps(settings)
        turn = run_turn(current, body.message, body.selection, model, tools, caps, guard,
                        names=names)  # fmt: skip
        chats.put(project_id, current)
        return turn
    finally:
        lock.release()


@router.post("/{project_id}/chat/{chat_id}/proposals/{proposal_id}")
def decide(
    project_id: ProjectId,
    chat_id: str,
    proposal_id: str,
    body: Decision,
    chats: ChatsDep,
) -> Proposal:
    chats.get(project_id, chat_id)  # 404 before a lock is made for an unknown id
    with chats.lock(chat_id):
        found = chats.get(project_id, chat_id)
        proposal = found.proposals.get(proposal_id)
        if proposal is None:
            raise NotFoundError(f"chat {chat_id} has no proposal {proposal_id}")
        if proposal.state != "proposed":
            raise NotAllowedError(f"proposal {proposal_id} is already {proposal.state}")
        state = "accepted" if body.action == "accept" else "rejected"
        found.proposals[proposal_id] = decided = proposal.model_copy(update={"state": state})
        chats.put(project_id, found)
        return decided
