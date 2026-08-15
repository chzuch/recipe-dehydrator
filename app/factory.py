"""应用工厂（无副作用）：装配依赖、注册路由与异常处理器、挂载前端。

放在独立模块，使测试 import 工厂时不会触发模块级 app 构造（避免无 .env 时炸掉）。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.config import Settings
from app.api.routes import Services, router
from app.application.cards import CardsUseCase
from app.application.dehydrate import DehydrateUseCase
from app.domain.exceptions import (
    DehydratorError,
    LLMError,
    SubtitleNotFoundError,
    ValidationFailedError,
    VideoNotFoundError,
)
from app.infrastructure.bilibili_fetcher import BilibiliFetcher
from app.infrastructure.ffmpeg_frames import FFmpegFrameExtractor
from app.infrastructure.llm_providers import create_llm_client
from app.infrastructure.sqlite_store import SQLiteCardStore

# 业务异常 → HTTP 状态映射
_EXCEPTION_STATUS: dict[type[DehydratorError], int] = {
    VideoNotFoundError: 404,
    SubtitleNotFoundError: 422,
    ValidationFailedError: 422,
    LLMError: 502,
}

STATIC_DIR = Path(__file__).parent / "static"


def build_services(settings: Settings) -> Services:
    """装配全部依赖（组合根）。"""
    env: dict[str, str | None] = {
        "DEEPSEEK_API_KEY": settings.deepseek_api_key,
        "DEEPSEEK_BASE_URL": settings.deepseek_base_url,
        "DEEPSEEK_MODEL": settings.deepseek_model,
        "QWEN_API_KEY": settings.qwen_api_key,
        "QWEN_BASE_URL": settings.qwen_base_url,
        "QWEN_MODEL": settings.qwen_model,
        "KIMI_API_KEY": settings.kimi_api_key,
        "KIMI_BASE_URL": settings.kimi_base_url,
        "KIMI_MODEL": settings.kimi_model,
    }
    llm = create_llm_client(settings.llm_provider, env)
    fetcher = BilibiliFetcher()
    frames = FFmpegFrameExtractor()
    store = SQLiteCardStore(settings.db_path)
    dehydrate = DehydrateUseCase(
        fetcher=fetcher,
        llm=llm,
        frames=frames,
        store=store,
        frames_dir=settings.frames_dir,
        with_frames=settings.with_frames,
    )
    cards = CardsUseCase(store=store, samples_dir=settings.samples_dir)
    return Services(dehydrate=dehydrate, cards=cards, frames_dir=settings.frames_dir)


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    """创建应用。services 参数供测试注入 fake 实现。"""
    settings = settings or Settings()
    app = FastAPI(title="视频脱水机", version="0.1.0")
    app.state.services = services or build_services(settings)

    app.include_router(router)

    @app.exception_handler(DehydratorError)
    async def _dehydrator_error_handler(_request: Request, exc: DehydratorError) -> JSONResponse:
        status = _EXCEPTION_STATUS.get(type(exc), 400)
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": "请求参数不合法"})

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html")

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app
