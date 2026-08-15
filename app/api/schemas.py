"""HTTP 请求/响应 schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DehydrateRequest(BaseModel):
    url: str = Field(min_length=1, description="B站视频链接（BV 号或完整 URL）")
    with_frames: bool = True


class DehydrateResponse(BaseModel):
    card_id: str
