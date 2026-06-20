# 亲子英语 AI Skills / Parent-English AI Skills

为小红书"地道亲子英语"系列打造的 AI Agent 技能集，覆盖从素材搜索、字幕烧制到社交配文生成的完整工作流。

AI agent skills for a Xiaohongshu (Little Red Book) parent-child English channel, covering the full workflow from YouTube source discovery to bilingual subtitle burning and social media post generation.

---

## Skills 一览 / Overview

| Skill | 用途 / Purpose | 依赖 / Dependencies |
|-------|---------------|---------------------|
| **bilingual-subtitles** | 用 ffmpeg 烧制中英双语硬字幕（半透明遮罩 + drawtext），并拼接片尾预设视频 | ffmpeg, faster-whisper |
| **video-english-xhs** | 从视频提取核心英语词汇和句型，生成小红书/抖音配文 + 飞书学习笔记文档 | ffmpeg, faster-whisper, lark-cli, Pillow |
| **yt-scene-finder** | 搜索 YouTube 亲子视频，筛选适合二创的素材（输出10个推荐 + 评估） | yt-dlp |

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

安装脚本会自动完成：
- 复制 skills 到 `~/.qoderworkcn/skills/`（QoderWork 识别目录）
- 检查并安装 ffmpeg、Python 依赖（faster-whisper, Pillow, yt-dlp）
- 检查 lark-cli（可选，飞书文档功能需要）

The install script will:
- Copy skills to `~/.qoderworkcn/skills/` (QoderWork skill directory)
- Check/install ffmpeg, Python deps (faster-whisper, Pillow, yt-dlp)
- Check lark-cli (optional, needed for Feishu doc creation)

---

## 配置 / Configuration

安装后编辑 `config.yaml`（从 `config.example.yaml` 复制），设置你的实际路径：

```yaml
preset_video: "C:/Users/YOU/Videos/preset.mp4"    # 片尾预设视频
font_path: "C:/Windows/Fonts/msyh.ttc"             # CJK 字体
youtube_cookies: "~/.agent-reach/cookies/youtube.txt"  # YouTube cookie
```

After install, edit `config.yaml` (copied from `config.example.yaml`) with your actual paths.

---

## 在其他 Agent 中使用 / Using with Other Agents

### Claude Code

```bash
# 方式1：在本项目中直接使用（推荐）
git clone https://github.com/nana-ai-diary/parent-english-skills.git
cd parent-english-skills
bash install.sh
# Claude Code 会自动读取 AGENTS.md 中的 skill 说明

# 方式2：把 AGENTS.md 引入你的项目
curl -o .claude/AGENTS.md https://raw.githubusercontent.com/nana-ai-diary/parent-english-skills/main/AGENTS.md
```

### OpenAI Codex

Codex 使用 `AGENTS.md` 作为项目指令。将本仓库的 `AGENTS.md` 放入项目根目录即可。

Codex reads `AGENTS.md` as project instructions. Place it in your project root.

### 通用方法 / Generic

任何支持读取 Markdown 指令的 agent，都可以直接使用 `skills/` 目录下的 `SKILL.md` 文件作为 system prompt 或 instructions。

Any agent that reads Markdown instructions can use the `SKILL.md` files directly.

---

## 依赖一览 / Full Dependency List

| 工具 / Tool | 用途 / Purpose | 安装 / Install |
|------------|---------------|----------------|
| ffmpeg ≥ 6.0 | 视频处理、字幕烧制 | `brew install ffmpeg` / `choco install ffmpeg` |
| Python ≥ 3.10 | 脚本运行环境 | [python.org](https://python.org) |
| faster-whisper | 语音转文字（Whisper） | `pip install faster-whisper` |
| yt-dlp | YouTube 搜索和下载 | `pip install yt-dlp` |
| Pillow | 图片处理（封面截图等） | `pip install Pillow` |
| lark-cli | 飞书文档创建（可选） | `npm install -g @anthropic/lark-cli` 或 QoderWork 自带 |

---

## 工作流 / Workflow

```
YouTube 搜索 (yt-scene-finder)
    ↓ 找到合适的亲子视频
字幕烧制 (bilingual-subtitles)
    ↓ 生成双语字幕视频
配文生成 (video-english-xhs)
    ↓ 生成小红书/抖音配文 + 飞书学习笔记
发布 🎉
```

---

## License

MIT
