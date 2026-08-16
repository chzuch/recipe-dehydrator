<div align="center">

# 🍳 recipe-dehydrator · 菜谱脱水机

把 B站做饭视频「脱水」成能照着做的图文菜谱卡，沉淀为你的个人菜谱库。
*Turn Bilibili cooking videos into follow-along recipe cards — your personal cookbook.*

![Python](https://img.shields.io/badge/Python-3.14-blue) ![TypeScript](https://img.shields.io/badge/TypeScript-ES2022-3178c6) ![MIT](https://img.shields.io/badge/License-MIT-green)

</div>

---

## ✨ 功能特性 / Features

| 中文 | English |
|---|---|
| 🎬 视频链接 → 图文菜谱卡（食材/工具/分步/达成状态/易错点） | Video link → structured recipe card (ingredients, tools, steps, done-when, tips) |
| 🍳 **做菜模式**：一步一屏、大字、手势翻页、进度条、屏幕常亮 | **Cook mode**: one step per screen, gestures, progress, wake-lock |
| 🛒 **买菜模式**：全屏清单、大勾选、调味料折叠 | **Shop mode**: full-screen list, big checkboxes |
| 📖 **菜谱库**：网格卡片、搜索、分类、置顶、打卡 | **Recipe library**: grid cards, search, pin, "cooked" tracking |
| 📺 页内播放器：点步骤 ▶ 跳到原视频对应秒，不跳外链 | In-page player: jump to exact second, no external navigation |
| 🔄 质量校验：LLM 输出经 L3 校验（时间/食材闭环/顺序） | Quality gate: LLM output validated (time/ingredient/order) |
| 📱 移动端适配 + PWA 离线 + 暗色模式 | Mobile-first, PWA offline, dark mode |

**内容守门 / Content guard**: BGM 歌词视频、多菜合集、非烹饪内容自动拒绝（拒绝 BGM lyrics, multi-dish compilations, non-cooking content）

---

## 🚀 快速开始 / Quick Start

> **前置要求 / Prerequisites**: Python 3.14, Node ≥ 20, [uv](https://docs.astral.sh/uv/), ffmpeg

```bash
# 1. 安装依赖 / Install deps
uv sync
npm ci
npm run build        # 构建前端 / build frontend

# 2. 配置 LLM API key（必填，DeepSeek 默认 / Qwen / Kimi 可选）
cp .env.example .env
# 编辑 .env，至少填 DEEPSEEK_API_KEY

# 3. 配置 B站登录 cookie（获取 AI 字幕必需，可选但强烈建议）
#    浏览器登录 bilibili.com → 用 "Get cookies.txt LOCALLY" 扩展导出 → 存为 ./cookies.txt
#    未配置时：无字幕视频会提示「无字幕」

# 4. 启动 / Start
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
# 浏览器打开 http://127.0.0.1:8000
```

**手机/平板访问 / Access from mobile**: 同一局域网内，手机浏览器打开 `http://<电脑IP>:8000`，可"添加到主屏"像 App 一样用。

**WSL2 用户网络说明**: 默认 NAT 模式下 Windows 本机可用 `http://<WSL-IP>:8000`（`hostname -I` 查看）访问；手机访问需 `netsh portproxy`（管理员）或 `.wslconfig` 启用 `networkingMode=mirrored`（WSL 与 Windows 共享网络栈，手机直连 Windows IP 即可，推荐）。

---

## 🧠 工作原理 / How it works

```
B站视频链接
  → yt-dlp 抓字幕（需要登录 cookie 获取 AI 字幕）
  → L1 预处理：解析/过滤闲话/BGM歌词/合并断句
  → 预检：单菜？烹饪内容？（多菜/非烹饪拒绝）
  → LLM 时间轴切分：步骤 + 阶段 + 达成状态（prompt 版本化）
  → L3 一致性校验：时间连续/食材闭环/顺序合理（失败重试）
  → 抽帧（关键句对齐）+ 动作 GIF（可选）
  → 评分器客观打分（100 分制，无需人工标注）
  → 存入个人菜谱库（SQLite）
```

**设计文档** / Docs: [前端设计](docs/frontend-design.md) · [范围与验收](docs/SCOPE.md) · [编码规范](CLAUDE.md)

---

## 🛠 技术栈 / Tech Stack

- **后端**: Python 3.14 · FastAPI · SQLite · yt-dlp · ffmpeg · Pydantic v2
- **前端**: TypeScript · esbuild（轻量构建，无框架）· 原生 ES Modules
- **LLM**: DeepSeek（默认）/ Qwen / Kimi（OpenAI 兼容协议，可切换）
- **质量门禁**: pytest + ruff + mypy strict + tsc --noEmit（CI 自动跑）

---

## 🔒 隐私与合规 / Privacy & Compliance

- **LLM API key 与 B站 cookie 自备**，只存本地 `.env` / `cookies.txt`（gitignore 排除，不入库）
- **数据全部本地**：卡片存 SQLite，截图/GIF 存本地文件，不上传任何服务
- **视频下载仅供个人学习/自用**：请尊重视频版权，勿用于商业传播
- 本项目不托管、不提供任何下载服务，仅提供本地工具

---

## 🧪 开发 / Development

```bash
uv run pytest            # 后端测试（101 个，LLM 用 fake 不消耗 API）
uv run ruff check .      # lint
uv run mypy app tests    # 类型检查（strict）
npm run typecheck        # 前端类型检查
npm run build            # 前端构建
```

---

## 📜 许可 / License

[MIT](LICENSE) © recipe-dehydrator contributors

---

## ⚠️ 免责声明 / Disclaimer

本项目是个人学习与自用工具，与 Bilibili、DeepSeek、Qwen、Kimi 等无任何关联。用户需自行承担使用责任，遵守所使用平台的服务条款与当地法律。
*This is a personal learning tool, not affiliated with Bilibili or any LLM provider. Users are responsible for complying with platform ToS and local laws.*
