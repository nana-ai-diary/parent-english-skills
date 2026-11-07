# Parent-English Skills — Agent Instructions

本仓库包含 **6 个 AI Agent 技能**，用于「地道亲子英语」系列的内容生产与交付。

This repo contains 6 AI agent skills for a parent-child English content channel.

前 5 个是能力 skill（各管一件事），第 6 个是编排 skill（管顺序、闸门与状态）。
The first 5 are capability skills; the 6th is an orchestrator that sequences them.

## Available Skills

### 1. yt-scene-finder — YouTube 素材搜索

**触发**: 给出场景名（洗澡 / 做饭 / 医生用具…）要求找 YouTube 亲子素材。
**Trigger**: Finding YouTube source videos for a given parenting scene.

**文件**: `skills/yt-scene-finder/SKILL.md`

**核心能力**:
- 多维度搜索（yt-dlp + WebSearch）
- 排除动画 / 广告 / 教程，保留真人亲子互动
- 输出 10 个推荐 + 对话密度与可提炼句子评估

**依赖**: yt-dlp

---

### 2. bilingual-subtitles — 双语字幕烧制

**触发**: 给视频加双语字幕、字幕叠加、带遮罩的文字。
**Trigger**: Burning bilingual subtitles onto a video.

**文件**: `skills/bilingual-subtitles/SKILL.md`

**核心能力**:
- ffmpeg drawtext + drawbox，EN 62px 金色 / CN 60px 白色粗体
- whisper 词级时间轴校准；转录一律 `vad_filter=False`（VAD 会吞短句）
- 长英文按词换行 + 遮罩高度自适应；有底部硬字幕时用不透明遮罩
- **默认必拼「关注我」片尾**；SRT 不与成片同名同目录（避免双重字幕）

**依赖**: ffmpeg, faster-whisper

---

### 3. parent-english-html — HTML 场景学习页

**触发**: 把视频做成 HTML 学习页 / 加一课 / 全系列重建。
**Trigger**: Building self-hosted lesson pages from videos.

**文件**: `skills/parent-english-html/SKILL.md`（含 `scripts/` 40+ 工具与 `references/`）

**核心能力**:
- 一个总目录 + 每课一个子页；页面固定 Part 1–7，题目严格限定 Part1–Part4
- 自托管 720p 压缩视频 + Opus-in-Ogg 分段精听音频（原声 / 慢速）
- 词汇、场景句、练习、避开中式英语、文化贴士、打印 PDF
- `series.json` 是系列唯一清单；`by`（YouTube 频道）派生页头 / 页脚来源，**每课必写来源**
- 一切走脚本，不手搓 HTML；版式改动只改外壳 + 渲染函数

**依赖**: ffmpeg, faster-whisper, Pillow

---

### 4. parent-english-netdisk — 双网盘交付

**触发**: 上传第 N 课到网盘 / 传夸克或百度 / 同步网盘资料。
**Trigger**: Uploading a lesson's MP4, MP3 and PDF to Quark and Baidu net disks.

**文件**: `skills/parent-english-netdisk/SKILL.md`, `scripts/upload_lesson.py`

**核心能力**:
- 一条命令**同时**传夸克 + 百度（百度走本机 bdpan CLI，与连接器是两条独立通道）
- 目标文件夹按「序号.」前缀智能匹配复用，绝不重复建目录
- 默认 dry-run，`--apply` 才真实上传
- **百度「假 FAIL」**：列表 API 偶发 `errno=-7`；判据看上传响应的 `✓ 已新建上传` / fsid，
  不看汇总行的 FAIL 字样

**依赖**: quark-nd-mcp（补丁版二进制）、bdpan CLI、网盘凭据（只存本机）

---

### 5. video-english-xhs — 社交配文

**触发**: 从视频提取英语学习内容、生成小红书 / 抖音帖子、整理学习笔记。
**Trigger**: Generating social posts and study notes from a video.

**文件**: `skills/video-english-xhs/SKILL.md`

**核心能力**:
- 转录后选 8 句左右实用英文 + 中文翻译，**不改写英文原文**
- 配文结构：标题 / Hook / 正文 / 点评 / CTA / 置顶评论
- 可选生成飞书学习笔记

**依赖**: ffmpeg, faster-whisper, lark-cli, Pillow

**选句规则**: 优先简单短句、互动指令、鼓励表达；覆盖准备 / 操作 / 互动 / 收尾。

---

### 6. parent-english-pipeline — 9 步编排层

**触发**: 做第 N 课 / 继续第 N 课 / 字幕没问题 / 传网盘 / 这课可以发了吗 / 来源补一下。
**Trigger**: Running or resuming the whole lesson pipeline.

**文件**: `skills/parent-english-pipeline/SKILL.md`, `config.yaml`, `scripts/pe.py` 等, `pe.cmd`

**核心能力**:
- 固定纯 ASCII 项目根 + 一课一档 `lessons/NN-slug/lesson.json`（单一事实源）
- 9 阶段状态机：`new → fetch → cut → subs → qa → approve(subs) → build → upload → verify → approve(final) → publish`
- 幂等续跑：已有产物且 `done` 就跳过，`--force` 才重跑；改字幕只重跑 QA 及之后
- QA 闸门：字幕宽度 / 折行 / 时间轴 / 片尾时长 / 转录覆盖率 / 抽帧拼图
- 下载时 `--write-info-json` 自动采集来源；终验检查 HTML 来源标注，漏写判 FAIL
- 上传排在终验之前；`final` 闸门只拦发帖

**依赖**: Python 3.10+, PyYAML, Pillow, faster-whisper, ffmpeg, yt-dlp

---

## Setup

Run the install script. It detects the client directory automatically:

```bash
# macOS/Linux
bash install.sh

# Windows
install.bat
```

- `~/.workbuddy` exists → installs to `~/.workbuddy/skills/` (WorkBuddy)
- else `~/.qoderworkcn` exists → installs to `~/.qoderworkcn/skills/` (QoderWork)
- otherwise defaults to `~/.workbuddy/skills/`
- set `SKILL_TARGET` to override explicitly

Or install dependencies manually:

```bash
pip install -r requirements.txt
ffmpeg -version
```

## Path Configuration

Two config files, both filled in locally:

1. Root `config.example.yaml` → copy to `config.yaml` (preset video, font, YouTube cookies).
2. `skills/parent-english-pipeline/config.yaml` → replace every `<...>` placeholder with your real paths.

Netdisk credentials stay on the local machine and must never be committed.

## Workflow

```
yt-scene-finder           找素材
  → 下载 + 剪辑（约 2 分钟，必拼片尾）
  → bilingual-subtitles   双语字幕 + 人工逐句校对
  → parent-english-html   课程页 / 分段音频 / PDF
  → video-english-xhs     配文
  → parent-english-netdisk 夸克 + 百度三件套
  → 终验（HTML / PDF / 上传文件 / 来源）
  → 人工确认后发布
```

## External side effects / 外部副作用

- Upload, deploy and post are **opt-in**: dry-run by default, `--apply` or an explicit approval required.
- `approve` gates must read the PASS conclusion of `qa_report.md` / `verify_report.md`, not just a status field.
- **Do not fake success**: if an expected artefact is missing, mark the stage `blocked` or `failed` with a precise to-do.
- Network drives and the web use **two different media tracks**: compressed 720p + Opus for the site,
  uncompressed subtitled MP4 + full MP3 for net disks. Never mix them.
- This public copy must stay sanitised: no real hostnames, absolute user paths, appIds, content roots,
  proxies or credentials.
