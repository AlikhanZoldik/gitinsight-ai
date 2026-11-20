from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.app.models.audit import Preview, Report
from backend.app.models.schemas import RepoName, Username
from backend.app.services.repository_analyzer import snapshot
from backend.app.utils.errors import GitHubError

router = APIRouter(prefix="/api/v1/repositories/{owner}/{repo}")


class AuditRequest(BaseModel):
    commit: str


@router.get("/audit-preview")
@router.get("/portfolio-health")
async def preview(owner: Username, repo: RepoName, request: Request) -> Preview:
    info, _ = await snapshot(request.app.state.github, owner, repo)
    return info


@router.post("/audit")
async def audit(owner: Username, repo: RepoName, body: AuditRequest, request: Request) -> Report:
    info, files = await snapshot(request.app.state.github, owner, repo)
    if info.commit != body.commit:
        raise GitHubError(409, "Repository changed. Refresh the preview before reviewing.")
    return Report(snapshot=info, review=await request.app.state.auditor.review(info, files))
