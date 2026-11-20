from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.api.audits import router as audits
from backend.app.api.routes import router
from backend.app.clients.github_client import GitHubClient
from backend.app.config import GITHUB_TOKEN
from backend.app.services.ai_service import Auditor
from backend.app.utils.errors import GitHubError


@asynccontextmanager
async def lifespan(app: FastAPI):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "GitInsight-Portfolio-Analytics",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    async with httpx.AsyncClient(
        base_url="https://api.github.com", headers=headers, timeout=10
    ) as http:
        app.state.github = GitHubClient(http)
        app.state.auditor = Auditor()
        yield


app = FastAPI(title="GitInsight AI", version="2.0.0", lifespan=lifespan)
app.include_router(router)
app.include_router(audits)


@app.exception_handler(GitHubError)
async def github_error(request: Request, exc: GitHubError):
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else {}
    return JSONResponse({"detail": exc.message}, status_code=exc.status, headers=headers)


class Health(BaseModel):
    status: str


@app.get("/health", summary="Check that the API process is available")
def health() -> Health:
    return Health(status="ok")
