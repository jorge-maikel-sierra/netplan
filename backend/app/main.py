from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import export, projects, nodes, edges, mst

app = FastAPI(title="NetPlan API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Ensure consistent error format: { error, code, detail }"""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        # Already in correct format
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )
    # Convert to standard format
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail if isinstance(exc.detail, str) else "HTTP_ERROR", "code": exc.status_code, "detail": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected errors"""
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "code": 500, "detail": "Internal server error"},
    )


# slowapi wiring: store the limiter on app.state so the @limiter.limit
# decorators can find it, and register the custom 429 handler so the
# response uses the project's error format.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


app.include_router(projects.router, prefix="/api/v1")
app.include_router(nodes.router, prefix="/api/v1")
app.include_router(edges.router, prefix="/api/v1")
app.include_router(mst.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}