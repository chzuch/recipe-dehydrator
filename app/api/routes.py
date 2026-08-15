"""HTTP 路由：全部业务逻辑在用例层，本层只做契约与序列化（CLAUDE.md §1）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.api.schemas import DehydrateRequest
from app.application.cards import CardsUseCase
from app.application.dehydrate import DehydrateUseCase
from app.domain.models import Recipe


class Services:
    """用例容器（组合根装配，routes 经 app.state 访问）。"""

    def __init__(self, dehydrate: DehydrateUseCase, cards: CardsUseCase, frames_dir: Path) -> None:
        self.dehydrate = dehydrate
        self.cards = cards
        self.frames_dir = frames_dir


router = APIRouter()


def _services(request: Request) -> Services:
    services = request.app.state.services
    if not isinstance(services, Services):
        msg = "应用服务未装配"
        raise RuntimeError(msg)
    return services


@router.post("/api/dehydrate")
async def api_dehydrate(req: DehydrateRequest, request: Request) -> dict[str, Any]:
    card_id, recipe = await _services(request).dehydrate.run(
        req.url, with_frames=req.with_frames, with_gif=req.with_gif
    )
    return {"card_id": card_id, "recipe": recipe}


@router.get("/api/cards")
async def api_list_cards(request: Request) -> list[dict[str, Any]]:
    return [{"id": card_id, "recipe": recipe} for card_id, recipe in await _services(request).cards.list_cards()]


@router.get("/api/cards/{card_id}")
async def api_get_card(card_id: str, request: Request) -> dict[str, Any]:
    recipe = await _services(request).cards.get_card(card_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail=f"卡片不存在: {card_id}")
    return {"id": card_id, "recipe": recipe}


@router.put("/api/cards/{card_id}")
async def api_update_card(card_id: str, recipe: Recipe, request: Request) -> dict[str, Any]:
    try:
        updated = await _services(request).cards.update_card(card_id, recipe)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": card_id, "recipe": updated}


@router.delete("/api/cards/{card_id}", status_code=204)
async def api_delete_card(card_id: str, request: Request) -> None:
    await _services(request).cards.delete_card(card_id)


@router.get("/api/frames/{frame_name}")
async def api_get_frame(frame_name: str, request: Request) -> FileResponse:
    frames_dir = _services(request).frames_dir
    candidate = (frames_dir / frame_name).resolve()
    if not candidate.is_relative_to(frames_dir.resolve()) or not candidate.is_file():
        raise HTTPException(status_code=404, detail="截图不存在")
    media_type = "image/gif" if candidate.suffix == ".gif" else "image/jpeg"
    return FileResponse(candidate, media_type=media_type)
