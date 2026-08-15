# 视频脱水机 v0.1 · 范围定义（SCOPE）

> 本文件是项目的唯一事实来源（source of truth）。每轮迭代前先对这份文件，防止范围漂移。
> 状态：已与用户逐条确认 · 2025 年定稿

---

## 1. 目的（为什么做）

- **主目的**：让做饭新手不用刷视频——给一个 B站视频链接，拿到一张能照着做完的图文菜谱卡
- **副目的**：练手 LLM 结构化抽取与时间轴切分工程；验证「视频脱水」模式，为二期「新闻情报局」打底

**一句话定位**：摘要是"内容说明"，脱水是"把信息从视频里还原成可直接使用的形态"。

---

## 2. 使用形式

- **本地小网页**：后端 FastAPI + 简单前端页面
  - 粘贴 B站链接 → 出菜谱卡
  - 历史卡片列表，可回看、可编辑
- 纯本地自用，不部署上线，不做账号系统

---

## 3. MVP 功能清单（v0.1）

### 3.1 输入
- 一个 B站视频链接（支持 BV 号 / 完整 URL）

### 3.2 抓取（视频元数据 + 字幕）
- 视频标题、UP主、封面
- 字幕：优先官方字幕；无字幕视频直接提示「不支持」（不做 ASR，见边界）
- 视频本体：下载 360p 低清版本，仅用于抽帧；用完即删，只保留截图

### 3.3 抽取（核心）
- 字幕预处理：按时间戳合并断句、去寒暄/广告/求三连、去重
- **时间轴切分**（不是"抽取步骤"，详见第 4 节）：把字幕时间线切成连续步骤段
- LLM 输出结构化 JSON：菜名 / 食材（含用量）/ 工具 / 步骤（含时间区间、动作、达成状态、易错点）/ 小贴士

### 3.4 输出
- 图文菜谱卡页面：步骤配图（每个步骤时间段中点抽帧，可开关，默认开）
- 食材自动汇总成「买菜清单」（可勾选家中已有，剩余即购物列表）

### 3.5 存储
- 历史卡片本地持久化（SQLite），可回看、可编辑
- 编辑后的修正自动沉淀为 few-shot 样本（供后续 prompt 增强）

---

## 4. 抽取策略（核心设计）

**核心原则：让 LLM「切分时间线」，而不是「抽取步骤」。**

切分有唯一性约束（连续、全覆盖），犯错空间远小于开放抽取；且切出的时间区间直接复用于抽帧截图，一个设计解决两个需求。

### L1 字幕预处理（进 LLM 之前，代码层）
- 按时间戳把断句合并回完整句子
- 规则 + LLM 双重过滤：寒暄开场、求三连、广告口播
- 合并重复强调句

### L2 时间轴切分（LLM 主任务）
- 主指令：把字幕按时间轴切成连续 N 段，每段 = 一个步骤，输出每段的时间范围、动作用语、达成状态
- 动作信号词锚点：
  - 衔接词（步骤边界）：下一步 / 接下来 / 然后 / 最后 / 起锅烧油
  - 动作动词：切、焯、腌、炒、炖、蒸、收汁…
  - 达成状态（必须写进步骤描述）：煮到变色 / 冒小泡 / 炖 10 分钟 / 筷子能扎透
- 提供 1–2 组真实字幕 → 正确切分的 few-shot 示例

### L3 一致性校验（LLM 输出之后，代码层）
- 食材闭环：每个食材必须出现在某步骤中，漏的标黄提醒
- 时间自洽：各步骤时长之和 ≈ 视频总时长，偏差大则告警（切漏或把闲话算进去了）
- 顺序合理：食材首次出现时间 ≤ 使用时间

### L4 人机回环
- 卡片可编辑；人工修正自动存为 few-shot 样本
- 攒够样本后追加进 prompt（v0.1 只做积累，不做重训）

### 兜底认知
- LLM 抽取永不 100% 准 → 验收标准是 8/10 而非 10/10，且页面必须可编辑
- 目标：把人工从「看 20 分钟视频」降到「改两处文字」

---

## 5. 明确不做（边界）

- ❌ 语音识别（ASR）：无字幕视频直接提示不支持，二期再说
- ❌ 新闻 / 财经模板：二期「个人情报局」，不在本次范围
- ❌ 多平台：只支持 B站；抖音 / YouTube 以后再说
- ❌ 账号系统、移动端、部署上线、多人协作
- ❌ 多模态选帧：不自动选"最佳画面"，只取时间段中点；手动换图二期再说
- ❌ 不做任意时间点浏览帧，只做每个步骤一帧
- ❌ 不追求还原大厨水准：标准是"新手照着做不翻车"

---

## 6. 技术栈与依赖

- Python 3.14 + uv 管理依赖
- 后端：FastAPI + SQLite
- 前端：**TypeScript + esbuild**（轻量构建：esbuild 单二进制毫秒编译，区别于 webpack 全家桶）+ 浏览器原生 ES Modules
  - 修订记录：v0.1 原定「单个 HTML 页面（原生 JS，不引入构建链）」，因 v0.2 前端承担菜谱库 + 三模式（见 `docs/frontend-design.md`），单文件不可维护，2026-08 修订为 TS + esbuild
  - 类型纪律与后端对齐：前端 `tsc --noEmit` 与后端 mypy strict 同等级别
  - `types.ts` 手动维护与后端 Pydantic schema 对齐
- 抓取：yt-dlp（字幕 + 视频）
- 抽帧/GIF：ffmpeg
- LLM：DeepSeek（默认）为主，provider 可切换 Qwen / Kimi（可配置）
  - 三家 API key 由用户提供，配置存本地 `.env`
- 测试：pytest（unit + integration；LLM 一律用 fake 实现，测试不消耗真实 API）
- 质量门禁四件套：`pytest` + `ruff check` + `mypy`（strict）+ `tsc --noEmit`

### 环境现状（已核查）
- Python 3.14.6 ✅ / ffmpeg 6.1.1 ✅ / uv ✅
- yt-dlp 未装 → 作为项目依赖用 uv 安装

---

## 7. 验收标准（Definition of Done）

1. 拿 **10 个真实 B站做饭视频**测试，**≥8 个**产出"照着能做完这道菜"的卡片
2. 纯文字卡单次脱水 **≤ 30 秒**（含抓字幕）；带图卡 **≤ 90 秒**
3. 页面支持：贴链接出卡、买菜清单勾选、历史回看、卡片编辑
4. **真实用一次**：用它做一顿饭，记录哪里卡壳（这一步比代码重要）

---

## 8. 二期展望（只记录，不实现）

- 新闻情报局：同一脱水管线换成"新闻事件 schema"，做增量关联
- Qwen-VL 多模态选帧 + 画面 OCR 补信息（解决"配料比例打在屏幕上"类字幕缺失）
- 无声视频画面花字 OCR（RapidOCR → 伪字幕 → 复用现有管线，已确认需求后排）
- 多平台支持（抖音/YouTube）+ 对应播放器
- 低置信度卡片标记（评分 <70 前端提示）

## 8.5 v0.2 前端迭代路线（设计已定稿：`docs/frontend-design.md`）

- **F0** 技术债清理：前端拆分（TS + ES Modules 多文件）、domain/rules 拆分、tests/fixtures 集中
- **F1** 菜谱库页（网格卡片 + 搜索 + 分类 + 置顶/打卡；默认首页）
- **F2** 内嵌播放器（B站 iframe + t 参数跳转到步骤秒数）
- **F3** 三模式详情页（浏览/做菜一步一屏/买菜全屏）+ 移动端响应式
- **F4** PWA 离线 + 手势 + 常亮 + 暗色

部署形态：电脑当服务器（局域网），手机/平板浏览器访问 + PWA 添加到主屏。

---

## 9. 项目结构与架构（分层架构 / Layered Architecture）

采用主流分层架构，依赖方向单向：**api（表现层）→ application（应用层）→ domain（领域层）← infrastructure（基础设施层）**。
- domain 定义实体、规则与端口接口（ports），不依赖任何外部库/框架
- infrastructure 实现 domain 的 ports（yt-dlp / ffmpeg / LLM / SQLite 都是"可替换的外部能力"）
- 依赖注入在 `app/main.py` 组合根完成，不引入 DI 框架

```
video-dehydrator/
├── SCOPE.md                  # 范围定义（事实来源 #1）
├── CLAUDE.md                 # 编码规范与 Agent 开发约束（事实来源 #2）
├── README.md                 # 使用说明
├── pyproject.toml            # uv 项目（依赖 + ruff / pytest / mypy 配置）
├── .env.example              # LLM API key 模板（.env 不入库）
├── .gitignore
├── data/                     # 运行产物：SQLite、截图、few-shot 样本（gitignore）
├── tests/
│   ├── conftest.py           # 共享 fixture
│   ├── fakes.py              # 测试替身：FakeLLMClient 等（测试不消耗真实 API）
│   ├── unit/                 # 纯逻辑单测：字幕预处理、校验规则、prompt 组装、存储
│   └── integration/          # 链路测试：fake LLM + 真实字幕样例跑通脱水管线
└── app/
    ├── main.py               # 组合根：装配依赖、启动 FastAPI
    ├── config.py             # 配置加载（pydantic-settings，读 .env）
    ├── api/                  # 表现层：HTTP 路由 + 请求/响应 Pydantic schema
    │   ├── __init__.py
    │   ├── routes.py
    │   └── schemas.py
    ├── application/          # 应用层：用例编排（不含业务规则细节）
    │   ├── __init__.py
    │   ├── dehydrate.py      # 用例：视频链接 → 菜谱卡（编排全链路）
    │   └── cards.py          # 用例：卡片查询 / 编辑 / 样本沉淀
    ├── domain/               # 领域层：纯业务模型与规则，零外部依赖
    │   ├── __init__.py
    │   ├── models.py         # 实体：Recipe / Step / Ingredient（Pydantic）
    │   ├── rules.py          # L3 校验规则：食材闭环、时间自洽、顺序合理
    │   └── ports.py          # 端口抽象：Fetcher / LLMClient / FrameExtractor / CardStore
    └── infrastructure/       # 基础设施层：外部适配器，实现 domain.ports
        ├── __init__.py
        ├── subtitle.py           # 字幕格式解析（B站 json / vtt）
        ├── bilibili_fetcher.py   # yt-dlp 实现 Fetcher（字幕 + 视频下载）
        ├── llm_providers.py      # DeepSeek / Qwen / Kimi 策略类实现 LLMClient
        ├── ffmpeg_frames.py      # ffmpeg 实现 FrameExtractor
        └── sqlite_store.py       # SQLite 实现 CardStore
```

**分层职责与禁忌**：

| 层 | 职责 | 禁止 |
|---|---|---|
| api | HTTP 契约、参数校验、序列化 | 业务逻辑、直接调用外部 SDK |
| application | 用例编排、跨端口协调、事务边界 | 外部 SDK 细节、领域规则实现 |
| domain | 实体、规则、端口接口 | 任何 stdlib 以外的 import |
| infrastructure | 外部能力适配（yt-dlp/ffmpeg/LLM/SQLite） | 业务决策 |

> 详细编码规范（命名、测试、lint、变更纪律）见 `CLAUDE.md`，两者冲突时以 CLAUDE.md 的变更纪律为准、以 SCOPE.md 的范围为准。
