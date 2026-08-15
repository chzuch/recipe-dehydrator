"""API 集成测试：TestClient + 注入 fake 服务（不触网、不触真实 LLM）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.api.routes import Services
from app.application.cards import CardsUseCase
from app.application.dehydrate import DehydrateUseCase
from app.domain.exceptions import LLMError
from app.factory import create_app
from fastapi.testclient import TestClient

from tests.fakes import (
    FakeCardStore,
    FakeFetcher,
    FakeFrameExtractor,
    FakeLLMClient,
    FakeVideoInfo,
)
from tests.integration.test_dehydrate_pipeline import LINES, SAMPLE_RECIPE


class _FailingLLM(FakeLLMClient):
    async def complete_json(self, system: str, prompt: str) -> dict[str, Any]:
        raise LLMError("模拟限流失败")


def _make_client(
    llm: FakeLLMClient | None = None,
    fetcher: FakeFetcher | None = None,
) -> TestClient:
    fetcher = fetcher or FakeFetcher(video=FakeVideoInfo(url="BV1xx", title="t", duration_sec=20.0), lines=LINES)
    store = FakeCardStore()
    frames = FakeFrameExtractor()
    usecase = DehydrateUseCase(
        fetcher=fetcher,
        llm=llm or FakeLLMClient([SAMPLE_RECIPE]),
        frames=frames,
        store=store,
        frames_dir="data/frames",
        with_frames=False,
    )
    cards = CardsUseCase(store=store, samples_dir=Path("data/samples"))
    services = Services(dehydrate=usecase, cards=cards, frames_dir=Path("data/frames"))
    return TestClient(create_app(services=services))


class TestDehydrateApi:
    def test_dehydrate_returns_card(self) -> None:
        client = _make_client()
        resp = client.post("/api/dehydrate", json={"url": "BV1xx"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["card_id"].startswith("fake-")
        assert data["recipe"]["title"] == "红烧牛肉"

    def test_dehydrate_missing_url_rejected(self) -> None:
        client = _make_client()
        assert client.post("/api/dehydrate", json={}).status_code == 422

    def test_dehydrate_llm_error_maps_to_502(self) -> None:
        client = _make_client(_FailingLLM([]))
        resp = client.post("/api/dehydrate", json={"url": "BV1xx"})
        assert resp.status_code == 502
        assert "限流" in resp.json()["detail"]

    def test_dehydrate_subtitle_missing_maps_to_422(self) -> None:
        empty_fetcher = FakeFetcher(video=FakeVideoInfo(url="BV1xx", title="t", duration_sec=20.0), lines=[])
        client = _make_client(fetcher=empty_fetcher)
        resp = client.post("/api/dehydrate", json={"url": "BV1xx"})
        assert resp.status_code == 422


class TestCardsApi:
    def test_crud_roundtrip(self) -> None:
        client = _make_client()
        created = client.post("/api/dehydrate", json={"url": "BV1xx"}).json()
        card_id = created["card_id"]

        listed = client.get("/api/cards").json()
        assert any(c["id"] == card_id for c in listed)

        recipe = created["recipe"]
        recipe["title"] = "改良版红烧牛肉"
        updated = client.put(f"/api/cards/{card_id}", json=recipe)
        assert updated.status_code == 200
        assert updated.json()["recipe"]["title"] == "改良版红烧牛肉"

        fetched = client.get(f"/api/cards/{card_id}").json()
        assert fetched["recipe"]["title"] == "改良版红烧牛肉"

        assert client.delete(f"/api/cards/{card_id}").status_code == 204
        assert client.get(f"/api/cards/{card_id}").status_code == 404

    def test_update_missing_card_404(self) -> None:
        client = _make_client()
        resp = client.put("/api/cards/nope", json=SAMPLE_RECIPE)
        assert resp.status_code == 404

    def test_frame_path_traversal_blocked(self) -> None:
        client = _make_client()
        assert client.get("/api/frames/..%2F..%2Fetc%2Fpasswd").status_code == 404
