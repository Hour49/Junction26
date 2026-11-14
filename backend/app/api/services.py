"""GET /api/projects/{project_id}/drawings/{drawing_id}/services/{storey_id}.png: one storey of the
drawing's stored services model as a plan picture (services-model.md SV-29), always the source
state; a proposal's change is drawn over it (SV-30). 404 for an unknown project, drawing or
storey; 409 while the drawing has no services model."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.adapters.services_agent_tools import model_id
from app.adapters.services_picture import storey_png
from app.adapters.services_store import ServicesStore
from app.api.deps import DrawingId, IngestDep, ProjectId, SettingsDep
from app.core.errors import NotFoundError

router = APIRouter(prefix="/api/projects")


@router.get(
    "/{project_id}/drawings/{drawing_id}/services/{storey_id}.png",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}}, "description": "the storey's services, drawn"},
        404: {"description": "no such project, drawing or storey"},
        409: {"description": "the drawing has no services model yet"},
    },
)
def services_png(
    project_id: ProjectId,
    drawing_id: DrawingId,
    storey_id: str,
    ingest: IngestDep,
    settings: SettingsDep,
) -> Response:
    files = [f for f in ingest.status(project_id).files if model_id(f) == drawing_id]
    if not files:
        raise NotFoundError(f"no drawing {drawing_id} in project {project_id}")
    sha256 = files[0].sha256
    model = None if sha256 is None else ServicesStore(settings.services_cache_dir).load(sha256)
    if model is None:
        raise HTTPException(409, "this drawing has no services model yet")
    png = storey_png(model, storey_id)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})
