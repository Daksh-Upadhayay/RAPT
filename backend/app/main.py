import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.agents.drafter import get_drafter
from app.agents.recovery import resume_unfinished_runs
from app.core.config import settings
from app.core.db import SessionLocal
from app.routers import (
    agents,
    auth,
    customers,
    knowledge_base,
    metrics,
    orders,
    reviews,
    tickets,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In the background, so a long backlog doesn't delay startup
    task = asyncio.create_task(resume_unfinished_runs(SessionLocal, get_drafter())) if settings.resume_unfinished_runs_on_startup else None
    yield
    if task is not None and not task.done():
        task.cancel()


app = FastAPI(title="RAPT Backend", lifespan=lifespan)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "x-rapt-csrf"


@app.middleware("http")
async def require_csrf_header(request: Request, call_next):
    """The session is a cookie, so a request that changes something must also carry a
    custom header. Another site's page can't add one to a cross-site request without a
    CORS preflight, and this API allows no cross-origin requests."""
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        return JSONResponse({"detail": "Missing the X-RAPT-CSRF header."}, status_code=403)
    return await call_next(request)


app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(orders.router)
app.include_router(customers.router)
app.include_router(knowledge_base.router)
app.include_router(agents.router)
app.include_router(reviews.router)
app.include_router(metrics.router)
