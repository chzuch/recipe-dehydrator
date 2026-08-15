"""集成测试：fake 组件跑通「字幕 → 切分 → 校验 → 卡片」管线。"""

from __future__ import annotations

import pytest
from app.application.dehydrate import DehydrateUseCase
from app.application.prompts import SYSTEM_SPLIT
from app.domain.exceptions import (
    MultiDishError,
    NoCookingContentError,
    SubtitleNotFoundError,
    ValidationFailedError,
)
from app.domain.models import SubtitleLine

from tests.fakes import FakeCardStore, FakeFetcher, FakeFrameExtractor, FakeLLMClient, FakeVideoInfo
from tests.fixtures import LINES, OVERLAP_RECIPE, SAMPLE_RECIPE


def _make_usecase(
    llm: FakeLLMClient,
    lines: list[SubtitleLine] | None = None,
    with_frames: bool = True,
    with_gif: bool = False,
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
        with_gif=with_gif,
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
        split_calls = [c for c in llm.calls if c[0] == SYSTEM_SPLIT]
        assert len(split_calls) == 2
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
    async def test_gif_off_by_default(self) -> None:
        """GIF 默认关闭：不生成、不下载视频（无额外开销）。"""
        usecase, _, frames, _ = _make_usecase(FakeLLMClient([SAMPLE_RECIPE]), with_frames=True)
        _, recipe = await usecase.run("BV1xx")
        assert all(s.gif_path is None for s in recipe.steps)
        assert frames.gif_calls == []

    @pytest.mark.asyncio
    async def test_gif_on_generates_per_step(self) -> None:
        """GIF 开启：≤8 步时每步都生成。"""
        usecase, _, frames, _ = _make_usecase(FakeLLMClient([SAMPLE_RECIPE]), with_gif=True)
        _, recipe = await usecase.run("BV1xx")
        assert all(s.gif_path is not None for s in recipe.steps)
        assert len(frames.gif_calls) == len(recipe.steps)

    @pytest.mark.asyncio
    async def test_unparseable_llm_output_retries(self) -> None:
        llm = FakeLLMClient(["不是JSON", SAMPLE_RECIPE])
        usecase, _, _, _ = _make_usecase(llm)
        _, recipe = await usecase.run("BV1xx")
        split_calls = [c for c in llm.calls if c[0] == SYSTEM_SPLIT]
        assert len(split_calls) == 2
        assert recipe.title == "红烧牛肉"

    @pytest.mark.asyncio
    async def test_empty_steps_raises_no_cooking_content(self) -> None:
        """LLM 判定字幕无烹饪内容（如全是 BGM 歌词）→ NoCookingContentError，不重试。"""
        llm = FakeLLMClient([{"title": "", "steps": [], "ingredients": [], "tools": [], "tips": []}])
        usecase, _, _, _ = _make_usecase(llm)
        with pytest.raises(NoCookingContentError):
            await usecase.run("BV1xx")
        split_calls = [c for c in llm.calls if c[0] == SYSTEM_SPLIT]
        assert len(split_calls) == 1  # 切分不重试

    @pytest.mark.asyncio
    async def test_duplicate_ingredients_merged_before_save(self) -> None:
        """LLM 把同名食材拆成多条 → 入库前合并（买菜清单爆炸的真实事故回归）。"""
        with_dups = {
            **SAMPLE_RECIPE,
            "ingredients": [
                {"name": "花生油", "amount": "50克", "note": None, "category": "调味料", "essential": True},
                {"name": "花生油", "amount": "700克", "note": None, "category": "调味料", "essential": True},
                {"name": "蚝油", "amount": "100克", "note": None, "category": "调味料", "essential": True},
            ],
        }
        usecase, store, _, _ = _make_usecase(FakeLLMClient([with_dups]))
        card_id, recipe = await usecase.run("BV1xx")

        assert [i.name for i in recipe.ingredients] == ["花生油", "蚝油"]
        assert recipe.ingredients[0].amount == "50克；700克"
        saved = await store.get(card_id)
        assert saved is not None and len(saved.ingredients) == 2

    @pytest.mark.asyncio
    async def test_multi_dish_video_rejected(self) -> None:
        """预检判定多菜合集 → MultiDishError，不切分（真实需求：28 分钟 6 菜合集）。"""
        multi = {
            "is_cooking": True,
            "dish_count": 6,
            "dishes": ["红烧牛肋条", "沙茶牛肉煲", "番茄牛腩"],
            "summary": "6 种牛肉做法合集",
        }
        usecase, _, _, _ = _make_usecase(FakeLLMClient([SAMPLE_RECIPE], precheck_response=multi))
        with pytest.raises(MultiDishError, match="6 道菜"):
            await usecase.run("BV1xx")

    @pytest.mark.asyncio
    async def test_non_cooking_video_rejected(self) -> None:
        """预检判定非烹饪内容（吃播/探店/纯音乐）→ NoCookingContentError。"""
        not_cooking = {"is_cooking": False, "dish_count": 0, "dishes": [], "summary": "吃播"}
        usecase, _, _, _ = _make_usecase(FakeLLMClient([SAMPLE_RECIPE], precheck_response=not_cooking))
        with pytest.raises(NoCookingContentError):
            await usecase.run("BV1xx")
