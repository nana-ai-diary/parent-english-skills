# 亲子英语 AI Skills / Parent-English AI Skills

为「地道亲子英语」系列打造的 **6 个 AI Agent 技能**，覆盖从 YouTube 素材发现、双语字幕、HTML 课程站、双网盘交付到社交配文的完整工作流。

AI agent skills for a parent-child English channel: 6 skills covering source discovery, subtitling, lesson-site generation, delivery and publishing.

> 本仓库是**公开副本**：域名、本机路径、内容根、appId、代理、凭据一律用 `<...>` 占位符。
> 安装后必须替换成你自己的值；真实值只留本机，不要提交。

---

## Skills 一览 / Overview

| # | Skill | 用途 / Purpose | 依赖 / Dependencies |
|---|-------|---------------|---------------------|
| 1 | **yt-scene-finder** | 按场景搜索 YouTube 亲子视频，输出 10 个推荐 + 评估 | yt-dlp |
| 2 | **bilingual-subtitles** | ffmpeg 烧制中英双语硬字幕（遮罩 + drawtext），默认拼「关注我」片尾 | ffmpeg, faster-whisper |
| 3 | **parent-english-html** | 自托管 HTML 场景学习页：总目录 + 每课子页、分段精听音频、词汇、句子、练习、打印 PDF | ffmpeg, faster-whisper, Pillow |
| 4 | **parent-english-netdisk** | 把定稿 MP4 / 整视频 MP3 / PDF **同时**传夸克 + 百度网盘 | quark-nd-mcp, bdpan CLI |
| 5 | **video-english-xhs** | 提取核心词汇句型，生成小红书 / 抖音配文 + 飞书学习笔记 | ffmpeg, faster-whisper, lark-cli, Pillow |
| 6 | **parent-english-pipeline** | 9 步编排层：一课一档、状态机、QA 闸门、幂等续跑、来源自动采集、终验与发布清单 | Python 3.10+, PyYAML, 上述全部 |

前 5 个是**能力 skill**（各管一件事），第 6 个是**编排 skill**（只管顺序、闸门和状态，不重写能力）。
一个 skill 就是一份写给 AI 看的操作手册（`SKILL.md`）：触发词、输入、固定规范、步骤、红线。

---

## 一键安装 / Quick Install

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/nana-ai-diary/parent-english-skills/main/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/nana-ai-diary/parent-english-skills/main/install.bat -OutFile install.bat; .\install.bat
```

### 手动安装 / Manual Install

```bash
git clone https://github.com/nana-ai-diary/parent-english-skills.git
cd parent-english-skills

# macOS/Linux
bash install.sh

# Windows
install.bat
```

安装脚本会自动检测客户端目录，**两种都兼容**：

| 条件 | 安装到 |
|---|---|
| 存在 `~/.workbuddy` | `~/.workbuddy/skills/`（WorkBuddy） |
| 否则存在 `~/.qoderworkcn` | `~/.qoderworkcn/skills/`（QoderWork） |
| 都没有 | 默认 `~/.workbuddy/skills/` |
| 设置 `SKILL_TARGET` 环境变量 | 直接装到指定目录 |

脚本还会检查 ffmpeg / Python、安装 `requirements.txt` 依赖，并提示可选的 lark-cli。
The installer detects the client directory (WorkBuddy or QoderWork), copies all 6 skills, and checks dependencies.

---

## 配置 / Configuration

需要填**两处**配置，都在本机完成：

1. 根目录 `config.example.yaml` → 复制为 `config.yaml`：片尾视频、CJK 字体、YouTube cookie（前 3 个 skill 用）。
2. `skills/parent-english-pipeline/config.yaml`：**所有 `<...>` 占位符**都要换成本机实际值
   （`<PROJECT_ROOT>` / `<DELIVERY_DIR>` / `<PROXY>` / `<SHARED_SITE_HOST>` / `<CONTENT_ROOT>` / `<BDPAN_EXE>` 等），
   否则编排层跑不起来。

网盘凭据（夸克 Cookie、bdpan 登录态）只存本机，**绝不进任何 Git 仓库**。
Netdisk credentials stay local and must never be committed.

---

## 在其他 Agent 中使用 / Using with Other Agents

### Claude Code / OpenAI Codex

`AGENTS.md` 是项目指令文件，放到项目根目录即可被读取；也可以直接把 `skills/<name>/SKILL.md`
当作 system prompt / instructions 使用。

### 通用方法 / Generic

任何支持读取 Markdown 指令的 agent，都可以直接使用 `skills/` 目录下的 `SKILL.md`。
调用时在对话里带上 `@skill:<name>` 触发词最稳，避免被下游 skill 抢走意图。

---

## 依赖一览 / Full Dependency List

| 工具 / Tool | 用途 / Purpose | 安装 / Install |
|------------|---------------|----------------|
| ffmpeg ≥ 6.0 | 视频裁剪、字幕烧制、抽音轨、压缩 | `brew install ffmpeg` / `choco install ffmpeg` |
| Python ≥ 3.10 | 脚本运行环境 | [python.org](https://python.org) |
| faster-whisper | 语音转文字（词级时间戳） | `pip install faster-whisper` |
| yt-dlp | YouTube 搜索与下载 | `pip install yt-dlp` |
| Pillow | 封面截图、字幕宽度校验 | `pip install Pillow` |
| PyYAML | 编排层读取 `config.yaml` | `pip install PyYAML` |
| lark-cli | 飞书文档创建（可选） | `npm install -g @anthropic/lark-cli` |
| quark-nd-mcp / bdpan | 双网盘上传（可选，仅交付阶段） | 本机自行安装并配置凭据 |

---

## 工作流 / Workflow

```
找素材 (yt-scene-finder) → 下载 + 剪辑约 2 分钟（必拼片尾）
  → 双语字幕 (bilingual-subtitles) → 人工逐句校对
  → 课程页 + 分段音频 + PDF (parent-english-html)
  → 配文 (video-english-xhs)
  → 双网盘三件套 (parent-english-netdisk)
  → 终验：HTML / PDF / 上传文件 / 来源标注
  → 人工确认后发小红书 / 抖音
```

`parent-english-pipeline` 把上面固化成 9 个阶段 + 2 道人工闸门：

```
new → fetch → cut → subs → qa → approve(subs) → build → upload → verify → approve(final) → publish
```

三条铁律：**上传排在终验之前**（核对上传文件本来就要等文件先传完）、
**网页用压缩媒体而网盘用未压缩原版**（双轨别混）、**每课 HTML 必须写来源**。

---

## 公开副本脱敏 / Sanitisation

对外材料不得出现：本机绝对路径、共享站域名、appId、激活码内容根、代理地址、
用户目录名、Cookie 内容。推送前扫描一遍，推送后再用 API 拉回文件复扫一遍。
See `skills/parent-english-html/SKILL.md` Step 4 for the placeholder conventions.

---

## License

MIT
