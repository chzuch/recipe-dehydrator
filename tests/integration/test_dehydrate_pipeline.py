"""集成测试：fake 组件跑通「字幕 → 切分 → 校验 → 卡片」管线。"""

from __future__ import annotations

from typing import Any

import pytest
from app.application.dehydrate import DehydrateUseCase
from app.domain.exceptions import SubtitleNotFoundError, ValidationFailedError
from app.domain.models import SubtitleLine

from tests.fakes import FakeCardStore, FakeFetcher, FakeFrameExtractor, FakeLLMClient, FakeVideoInfo

SAMPLE_RECIPE: dict[str, Any] = {
    "title": "红烧牛肉",
    "difficulty": "中等",
    "servings": "2人份",
    "total_time": "40分钟",
    "ingredients": [{"name": "牛腩肉", "amount": "500克", "note": None}],
    "tools": ["锅"],
    "steps": [
        {
            "index": 1,
            "title": "切牛肉",
            "description": "牛腩肉切成稍大的块",
            "done_when": None,
            "tip": "切稍大的块",
            "start_sec": 0.5,
            "end_sec": 5.0,
        },
        {
            "index": 2,
            "title": "焯水去腥",
            "description": "冷水下锅焯水",
            "done_when": "煮出浮沫",
            "tip": "冷水下锅",
            "start_sec": 5.0,
            "end_sec": 20.0,
        },
    ],
    "tips": [],
}

# 步骤 1、2 时间区间重叠（STEP_OVERLAP）的错误输出
OVERLAP_RECIPE = {
    **SAMPLE_RECIPE,
    "steps": [
        {**SAMPLE_RECIPE["steps"][0], "end_sec": 12.0},
        {**SAMPLE_RECIPE["steps"][1], "start_sec": 8.0},
    ],
}

LINES = [
    SubtitleLine(start=0.5, end=5.0, text="牛腩肉切成稍大的块"),
    SubtitleLine(start=5.0, end=20.0, text="冷水下锅焯水，煮出浮沫"),
]


def _make_usecase(
    llm: FakeLLMClient,
    lines: list[SubtitleLine] | None = None,
    with_frames: bool = True,
    video_path: str | None = "video.mp4",
) -> tuple[DehydrateUseCase, FakeCardStore, FakeFrameExtractor, FakeFetcher]:
    fetcher = FakeFetcher(
        video=FakeVideoInfo(url="BV1xx", title="红烧牛肉做法", duration_sec=20.0),
        lines=lines if lines is not None else LINES,
        video_path=video_path,
    )
    frames = FakeFrameExtractor()
    store = FakeCardStore()
    usecase = DehydrateUseCase(
        fetcher=fetcher,
        llm=llm,
        frames=frames,
        store=store,
        frames_dir="data/frames",
        with_frames=with_frames,
    )
    return usecase, store, frames, fetcher


class TestDehydratePipeline:
    @pytest.mark.asyncio
    async def test_success_returns_saved_card(self) -> None:
        usecase, store, _, _ = _make_usecase(FakeLLMClient([SAMPLE_RECIPE]))
        card_id, recipe = await usecase.run("BV1xx")
        assert card_id.startswith("fake-")
        assert await store.get(card_id) is not None
        assert recipe.source_url == "BV1xx"
        assert recipe.source_title == "红烧牛肉做法"
        assert recipe.warnings == []

    @pytest.mark.asyncio
    async def test_retry_on_validation_error(self) -> None:
        llm = FakeLLMClient([OVERLAP_RECIPE, SAMPLE_RECIPE])
        usecase, _, _, _ = _make_usecase(llm)
        _, recipe = await usecase.run("BV1xx")
        assert len(llm.calls) == 2
        assert recipe.steps[1].start_sec == 5.0

    @pytest.mark.asyncio
    async def test_raises_after_two_failures(self) -> None:
        llm = FakeLLMClient([OVERLAP_RECIPE, OVERLAP_RECIPE])
        usecase, _, _, _ = _make_usecase(llm)
        with pytest.raises(ValidationFailedError):
            await usecase.run("BV1xx")

    @pytest.mark.asyncio
    async def test_empty_subtitles_raises(self) -> None:
        usecase, _, _, _ = _make_usecase(FakeLLMClient([SAMPLE_RECIPE]), lines=[])
        with pytest.raises(SubtitleNotFoundError):
            await usecase.run("BV1xx")

    @pytest.mark.asyncio
    async def test_frames_attached_when_enabled(self) -> None:
        usecase, _, frames, _ = _make_usecase(FakeLLMClient([SAMPLE_RECIPE]))
        _, recipe = await usecase.run("BV1xx")
        assert recipe.steps[0].frame_path is not None
        assert len(frames.calls) == 1
        assert len(frames.calls[0][1]) == 2  # 每个步骤一个抽帧时间点

    @pytest.mark.asyncio
    async def test_no_frames_when_disabled(self) -> None:
        usecase, _, _, fetcher = _make_usecase(FakeLLMClient([SAMPLE_RECIPE]), with_frames=False, video_path=None)
        _, recipe = await usecase.run("BV1xx")
        assert all(s.frame_path is None for s in recipe.steps)
        # 未下载视频时 fetcher.cleanup 无副作用
        await fetcher.cleanup()

    @pytest.mark.asyncio
    async def test_unparseable_llm_output_retries(self) -> None:
        llm = FakeLLMClient(["不是JSON", SAMPLE_RECIPE])
        usecase, _, _, _ = _make_usecase(llm)
        _, recipe = await usecase.run("BV1xx")
        assert len(llm.calls) == 2
        assert recipe.title == "红烧牛肉"
