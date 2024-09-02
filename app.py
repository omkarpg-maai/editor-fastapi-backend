from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import calendar_events


def create_app() -> FastAPI:
    app = FastAPI(title="Editor Worker FastAPI Backend")

    app.include_router(calendar_events.router)

    # For local development
    origins = [
        "http://localhost:3000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Generic health route to sanity check the API
    @app.get("/health")
    async def health() -> str:
        return "ok"

    return app
