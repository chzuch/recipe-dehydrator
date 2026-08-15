# 视频脱水机 (video-dehydrator)

把 B站做饭视频「脱水」成能照着做的图文菜谱卡：粘贴视频链接 → 得到结构化菜谱（食材/工具/分步图文/买菜清单）。

> 范围与验收标准见 [SCOPE.md](SCOPE.md)；编码规范与 Agent 约束见 [CLAUDE.md](CLAUDE.md)。两者是项目事实来源。

## 功能

- 粘贴 B站链接（BV 号或完整 URL）→ 抓字幕 → LLM 按时间轴切分步骤 → 结构化菜谱卡
- 步骤配图（每个步骤时间区间中点抽帧，可在请求中关闭）
- 买菜清单（勾选家中已有，剩余即购物列表）
- 历史卡片本地存储（SQLite）、回看、编辑（编辑自动沉淀为 few-shot 样本）
- LLM provider 可切换：DeepSeek（默认）/ Qwen / Kimi

## 快速开始

```bash
# 1. 安装依赖（uv）
uv sync

# 2. 配置 LLM API key
cp .env.example .env
# 编辑 .env，至少填写 DEEPSEEK_API_KEY（或 QWEN_API_KEY / KIMI_API_KEY 并改 LLM_PROVIDER）

# 3. 启动
uv run uvicorn app.main:app --reload --port 8000

# 4. 打开 http://127.0.0.1:8000 ，粘贴视频链接，点「脱水」
```

> 无 .env（或未填 key）时启动即失败（fail fast），这是刻意的——避免运行到一半才发现没有 key。

## 开发

```bash
uv run pytest          # 全量测试（54 个；LLM 全部用 fake，不消耗真实 API）
uv run ruff check .    # lint
uv run ruff format .   # 格式化
uv run mypy app tests  # 类型检查（strict）
```

## API 摘要

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/dehydrate` | `{"url": "...", "with_frames": true}` → `{card_id, recipe}` |
| GET | `/api/cards` | 历史卡片列表 |
| GET | `/api/cards/{id}` | 单张卡片 |
| PUT | `/api/cards/{id}` | 编辑卡片（body 为 recipe JSON） |
| DELETE | `/api/cards/{id}` | 删除卡片 |
| GET | `/api/frames/{name}` | 步骤截图 |

## 架构

分层架构（api → application → domain ← infrastructure），依赖方向单向；domain 零外部依赖。
细节见 SCOPE.md §9。LLM 输出一律先过 L3 一致性校验（domain/rules.py）再入库。
