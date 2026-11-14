"""The project chat agent (decision 0013, docs/API.md "Chat"): one turn per POST, the chat kept on
the server, plan edits as proposals a person accepts or rejects. Sync routes: the model client
blocks, so FastAPI runs them in its thread pool."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, StringConstraints

from app.adapters.agent_tools import project_toolbox
from app.adapters.chat_store import JsonChatStore
from app.api.checks import RulePacksDep, find_pack
from app.api.deps import IngestDep, Models3dDep, ProjectId, SettingsDep
from app.api.project_ask import ProjectAnswer, with_models_3d
from app.api.views import View, drawings_of
from app.composition import chat_caps, chat_model, spend_guard
from app.core.agent import model
from app.core.agent.loop import run_turn
from app.core.agent.prompt import COUNTRY, NO_COUNTRY
from app.core.checks.model import RulePack
from app.core.errors import InvalidInputError, NotFoundError, UnknownPackError
from app.core.plan_edit.model import Proposal, Selection
from app.core.review.review import NotAllowedError
from app.core.spend import SpendGuard

router = APIRouter(prefix="/api/projects")

MESSAGE_CHARS = 2000


class ChatTurn(model.ChatTurn):
    """A turn as the API returns it: `answers` typed as POST /api/projects/{id}/ask's answers."""

    # the same JSON core keeps as plain objects, typed here for the contract
    answers: tuple[ProjectAnswer, ...] = ()  # pyright: ignore[reportIncompatibleVariableOverride]


class ChatRequest(View):
    chat_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{12}$")
    # blank after stripping is a 422, not a turn (QA robust-6)
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MESSAGE_CHARS)
    ]
    selection: list[Selection] = Field(default_factory=list[Selection], max_length=8)
    # The header's country picker (LC-6): the rule pack plan edits are checked against, an id
    # from GET /api/info rule_packs; none: edits are not checked. Per turn, not stored
    pack: str | None = Field(default=None, min_length=1, max_length=32)


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
    packs: RulePacksDep,
    models_3d: Models3dDep,
) -> ChatTurn:
    pack = None if body.pack is None else _pack(packs, body.pack)
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
        tools = project_toolbox(request.app, project_id, body.selection, current.proposals, pack)
        names = {entry.drawing_id: entry.name for entry in drawings_of(status)}
        # the rules planner is free: the Gemini budget never stops it (QA robust-3)
        guard = SpendGuard() if settings.chat_model == "rules" else spend_guard(settings)
        caps = chat_caps(settings)
        turn = run_turn(current, body.message, body.selection, model, tools, caps, guard,
                        names=names, context=_country(request.app, pack))  # fmt: skip
        chats.put(project_id, current)
        shown = ChatTurn.model_validate(turn.model_dump(mode="json"))
        answers = tuple(with_models_3d(answer, status, models_3d) for answer in shown.answers)
        return shown.model_copy(update={"answers": answers})
    finally:
        lock.release()


def _country(app: Any, pack: RulePack | None) -> str:
    """The turn's country lines for the model (LC-6, LC-14, AC-9): the chosen pack and its
    laws' contents, or that none is chosen."""
    if pack is None:
        return NO_COUNTRY
    lines = COUNTRY.format(name=pack.name, pack=pack.id)
    laws = getattr(app.state, "laws", None)
    try:
        from app.adapters.law_tools import law_prompt
    except ImportError:
        return lines
    return lines if laws is None else f"{lines}\n{law_prompt(laws, pack.id)}"


def _pack(packs: tuple[RulePack, ...], pack_id: str) -> RulePack:
    """The pack the checks API knows by this id; an unknown one is a bad body (422)."""
    try:
        return find_pack(packs, pack_id)
    except UnknownPackError as error:
        raise InvalidInputError(str(error)) from None


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
