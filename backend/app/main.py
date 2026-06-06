from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.routers import projects

app = FastAPI(title="NetPlan API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origins],
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


app.include_router(projects.router, prefix="/api/v1")


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}