# Parent-English Skills — Agent Instructions

本仓库包含 3 个 AI Agent 技能，用于小红书"地道亲子英语"系列内容创作。

This repo contains 3 AI agent skills for a Xiaohongshu parent-child English content channel.

## Available Skills

### 1. bilingual-subtitles — 双语字幕烧制

**触发**: 当需要给视频加双语字幕、字幕叠加、带背景的文字时使用。
**Trigger**: When adding bilingual subtitles, subtitle overlays, or text captions with background to video.

**文件**: `skills/bilingual-subtitles/SKILL.md`

**核心能力**:
- 用 ffmpeg drawtext+drawbox 烧制中英双语硬字幕
- 半透明黑色遮罩背景，英文黄色/中文白色
- whisper word-level 时间轴校准
- 拼接片尾预设视频

**依赖**: ffmpeg, faster-whisper

---

### 2. video-english-xhs — 视频英语 → 社交配文

**触发**: 当用户发送视频并要求提取英语学习内容、生成抖音/小红书帖子、整理视频英语笔记时。
**Trigger**: When user sends a video and asks to extract English learning content, generate Xiaohongshu/Douyin posts, or create study notes.

**文件**: `skills/video-english-xhs/SKILL.md`

**核心能力**:
- 转录视频（faster-whisper）
- 从转录中选 8 句实用英文 + 中文翻译
- 生成小红书配文（标题、Hook、正文、点评、CTA、置顶评论）
- 自动创建飞书文档（完整学习笔记：词汇、句型、练习、场景拓展）

**依赖**: ffmpeg, faster-whisper, lark-cli, Pillow

**选句规则**（重要）:
- 从视频转录原文中选 8 句左右
- 不做任何修改，不"优化"英文表达
- 优先选：简单短句、互动指令、鼓励表达、日常口语
- 场景覆盖：尽量覆盖准备、操作、互动、收尾不同环节

---

### 3. yt-scene-finder — YouTube 素材搜索

**触发**: 当用户提供场景名（如"洗澡""做饭""公园玩耍"）并要求找 YouTube 视频/素材时。
**Trigger**: When user provides a scene name and asks to find YouTube videos or source material.

**文件**: `skills/yt-scene-finder/SKILL.md`

**核心能力**:
- 多维度搜索 YouTube（yt-dlp + WebSearch）
- 自动筛选：排除动画/广告/教程，保留真人亲子互动
- 深度评估：字幕分析、对话密度、可提炼句子预估
- 输出 10 个推荐视频 + 详细评估

**依赖**: yt-dlp

---

## Setup

Before using these skills, run the install script:

```bash
# macOS/Linux
bash install.sh

# Windows
install.bat
```

Or install dependencies manually:

```bash
pip install faster-whisper Pillow yt-dlp
# Check ffmpeg is installed
ffmpeg -version
# Optional: lark-cli for Feishu docs
npm install -g @anthropic/lark-cli
```

## Path Configuration

Skills reference configurable paths (preset video, fonts, cookies). Edit `config.yaml` after install. See `config.example.yaml` for all available settings.

## Workflow

```
yt-scene-finder → bilingual-subtitles → video-english-xhs
  (find source)      (burn subtitles)     (generate posts + docs)
```
