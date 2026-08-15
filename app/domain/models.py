"""领域实体：脱水管线的数据模型（Pydantic v2，零外部业务依赖）。

LLM 结构化输出与持久化共用这一组模型，保证 schema 单一来源。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SubtitleLine(BaseModel):
    """一条字幕（预处理后：断句已合并、闲话已过滤）。"""

    start: float = Field(ge=0, description="开始时间（秒）")
    end: float = Field(ge=0, description="结束时间（秒）")
    text: str = Field(min_length=1)


class Ingredient(BaseModel):
    """一种食材。"""

    name: str = Field(min_length=1, description="食材名，如「牛腩肉」")
    amount: str | None = Field(default=None, description="用量，如「500克」")
    note: str | None = Field(default=None, description="选购/处理备注，如「选肥瘦相间的」")
    category: Literal["主料", "配料", "调味料", "香料", "需提前自制"] = Field(
        description="食材分类；配料=湿的提味配头（葱姜蒜/鲜辣椒），香料=干料，调味料=成品（含淀粉/白糖）"
    )
    essential: bool = Field(description="是否必不可少（核心食材）；可选/锦上添花为 False")


class Step(BaseModel):
    """一个烹饪步骤，对应字幕时间轴的一段连续区间。"""

    index: int = Field(ge=1, description="步骤序号，从 1 起")
    title: str = Field(min_length=1, description="步骤标题，如「切牛肉」")
    phase: str = Field(min_length=1, description="所属阶段，如「备料」「熬制酱料」「炒制」「收尾」")
    description: str = Field(min_length=1, description="做了什么（动作用语）")
    done_when: str | None = Field(default=None, description="达成状态，如「炖 10 分钟」「煮到变色」")
    tip: str | None = Field(default=None, description="新手易错点")
    start_sec: float = Field(ge=0, description="字幕区间起点（秒）")
    end_sec: float = Field(ge=0, description="字幕区间终点（秒）")
    frame_path: str | None = Field(default=None, description="步骤截图路径（相对 data 目录）")
    gif_path: str | None = Field(default=None, description="动作演示 GIF 路径（仅动作类步骤生成）")

    @model_validator(mode="after")
    def _check_range(self) -> Step:
        if self.end_sec < self.start_sec:
            msg = f"step {self.index}: end_sec({self.end_sec}) < start_sec({self.start_sec})"
            raise ValueError(msg)
        return self


class Recipe(BaseModel):
    """脱水后的菜谱卡。"""

    title: str = Field(min_length=1, description="菜名")
    source_url: str | None = None
    source_title: str | None = Field(default=None, description="原始视频标题")
    uploader: str | None = None
    difficulty: Literal["简单", "中等", "困难"] | None = None
    servings: str | None = Field(default=None, description="份量，如「2人份」")
    total_time: str | None = Field(default=None, description="总耗时，如「40分钟」")
    ingredients: list[Ingredient] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list, description="L3 校验产生的告警，展示给用户")

    @model_validator(mode="after")
    def _check_steps_indexed(self) -> Recipe:
        indexes = [s.index for s in self.steps]
        if indexes != sorted(indexes):
            # 允许 LLM 乱序返回，这里按 index 归一排序，保证展示稳定
            self.steps = sorted(self.steps, key=lambda s: s.index)
        return self

    def shopping_list(self, have: set[str] | None = None) -> list[Ingredient]:
        """生成买菜清单：食材中未被勾选（家中已有）的项。"""
        have = have or set()
        return [i for i in self.ingredients if i.name not in have]
