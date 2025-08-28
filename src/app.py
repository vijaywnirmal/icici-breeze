from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .utils.config import settings
from .routes.hello import router as hello_router
from .routes.login import router as login_router
from .routes.home import router as home_router
from .routes.stream import router as stream_router
from .routes.watchlist import router as watchlist_router
from .routes.watchlist_stream import router as watchlist_stream_router


# Load environment variables from .env at startup
load_dotenv()


app = FastAPI(title=settings.app_name)


# Enable CORS for simple static frontend usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include route modules
app.include_router(hello_router)
app.include_router(login_router)
app.include_router(home_router)
# websocket router added without prefix
app.include_router(stream_router)
app.include_router(watchlist_router)
app.include_router(watchlist_stream_router)


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.environment,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)



