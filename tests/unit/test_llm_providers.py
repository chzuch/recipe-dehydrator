"""app.infrastructure.llm_providers 纯逻辑单元测试。"""

from __future__ import annotations

import pytest
from app.domain.exceptions import LLMError
from app.infrastructure.llm_providers import parse_json_content


class TestParseJsonContent:
    def test_strict_json(self) -> None:
        assert parse_json_content('{"a": 1}') == {"a": 1}

    def test_extract_from_markdown_fence(self) -> None:
        content = '```json\n{"steps": [{"index": 1}]}\n```'
        assert parse_json_content(content) == {"steps": [{"index": 1}]}

    def test_extract_first_brace_object(self) -> None:
        content = '好的，这是结果：{"title": "红烧肉"} 请查收'
        assert parse_json_content(content) == {"title": "红烧肉"}

    def test_unparseable_raises_llm_error(self) -> None:
        with pytest.raises(LLMError):
            parse_json_content("完全没有 JSON 的内容")

    def test_top_level_list_not_accepted(self) -> None:
        with pytest.raises(LLMError):
            parse_json_content("[1, 2, 3]")
