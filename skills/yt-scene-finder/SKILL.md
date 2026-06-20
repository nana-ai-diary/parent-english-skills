---
name: yt-scene-finder
description: 搜索YouTube视频并筛选适合小红书亲子英语账号二创参考的素材。当用户提供一个场景名（如"洗澡""做饭""公园玩耍"）并要求找YouTube视频、找素材、找亲子视频时触发。输出10个推荐视频及详细评估。Search YouTube videos and filter suitable content for Xiaohongshu parent-child English channel re-creation. Triggered when user provides a scene name and asks to find YouTube videos, source material, or parent-child videos.
version: 1.0.0
---

# YouTube 亲子英语素材搜索

根据用户提供的场景名，搜索YouTube并筛选适合小红书"地道亲子英语"系列二创的视频素材。

## 触发场景

- 用户发送场景名 + 要求找视频/素材（如"帮我找洗澡场景的视频"、"公园玩耍 找素材"）
- 用户说"找YouTube视频"、"搜亲子视频"、"这个场景有什么素材"

## 搜索流程

### Step 1: 多维度搜索YouTube

收到场景名后，**并行执行**以下搜索以获取充足候选：

**搜索A — yt-dlp（主力，获取结构化元数据）：**

```bash
yt-dlp "ytsearch25:{场景名英文} kids parent toddler family" --flat-playlist --dump-json --cookies "C:\Users\32730\.agent-reach\cookies\youtube.txt" 2>nul
```

提取每个视频的：id, title, duration, view_count, channel, upload_date, description。

**搜索B — yt-dlp 补充搜索（换关键词角度）：**

```bash
yt-dlp "ytsearch15:{场景名英文} with my {toddler/baby/son/daughter} real life" --flat-playlist --dump-json --cookies "C:\Users\32730\.agent-reach\cookies\youtube.txt" 2>nul
```

**搜索C — WebSearch 补充（发现yt-dlp搜不到的长尾内容）：**

用 WebSearch 搜索 `site:youtube.com {场景名英文} toddler parent real life vlog` 获取更多候选。

### Step 2: 合并去重

将所有搜索结果按 video_id 去重，保留元数据最完整的版本。

### Step 3: 初筛（快速排除）

立即排除以下类型：
- duration < 30秒 或 > 30分钟
- title 含 "animation", "cartoon", "animated", "song", "nursery rhyme", "ad", "sponsored", "tutorial", "how to", "lesson", "course"
- channel 名含 "Kids TV", "Cocomelon", "Baby Shark", "Super Simple" 等纯动画/儿歌频道
- view_count < 1000（除非是优质小众内容）

### Step 4: 深度评估（对剩余候选逐个分析）

对通过初筛的视频，尝试获取字幕来评估内容质量：

```bash
yt-dlp --write-auto-sub --sub-lang en --skip-download --sub-format vtt -o "C:\Users\32730\.qoderworkcn\workspace\%(id)s" --cookies "C:\Users\32730\.agent-reach\cookies\youtube.txt" "https://www.youtube.com/watch?v={VIDEO_ID}" 2>nul
```

如果字幕可用，分析字幕内容判断：
- 是否有亲子对话（而非旁白独白）
- 对话密度是否足够（每3-5秒有可提炼的句子）
- 语言是否自然口语化

如果字幕不可用，基于标题、描述、时长、频道类型综合判断。

### Step 5: 精选10个并输出

从所有候选中选出最佳的10个，按推荐度排序输出。

## 筛选标准（严格执行）

| 标准 | 说明 | 权重 |
|------|------|------|
| 真实亲子场景 | 真人家长+孩子互动，非摆拍感太强 | 必须 |
| 前3秒可看懂动作 | 开头就有明确视觉动作（吃饭、洗澡、穿衣等） | 必须 |
| 自然互动 | 家长和孩子有对话/互动，不是各做各的 | 必须 |
| 每3-5秒有英文句子 | 对话密度足够，能提炼出实用句子 | 高 |
| 非纯讲解/动画/广告 | 排除教程类、动画类、广告类内容 | 必须 |
| 画面动作有连续流程 | 有完整流程（如从准备到完成），适合剪辑叙事 | 高 |
| 适合系列化 | 能归入"地道亲子英语｜具体场景"系列 | 中 |

## 输出格式

对每个推荐视频，严格按以下格式输出：

```
### {序号}. {视频标题}

**链接：** https://www.youtube.com/watch?v={VIDEO_ID}
**时长：** {分:秒} | **播放量：** {数字} | **频道：** {频道名}

**场景类型：** {如：洗澡时间 / 做饭帮忙 / 公园玩耍 / 睡前故事 / ...}

**为什么适合：**
{2-3句说明，具体指出视频中的哪些元素符合筛选标准}

**可提炼的英文句子（预估）：**
1. {基于字幕或视频描述推测的实用句子}
2. {句子2}
3. {句子3}
（至少给出3句预估）

**爆款潜力：** {高/中/低} — {一句话理由}
```

## 爆款潜力评估维度

- **高**：场景普遍性强（每个家庭都有）+ 动作视觉冲击 + 情感共鸣点（孩子搞笑反应/温馨互动）+ 3分钟内
- **中**：场景常见但缺少特别亮点，或场景好但视频偏长需要大量剪辑
- **低**：场景小众，或互动平淡，或画面质量差

## 注意事项

- 搜索关键词用英文，因为英文亲子视频素材更丰富
- 如果某场景搜索结果不足10个合格视频，如实告知用户，不凑数
- 优先推荐有英文字幕（auto-generated或手动）的视频
- yt-dlp cookies 路径：`C:\Users\32730\.agent-reach\cookies\youtube.txt`
- 字幕下载临时目录：`C:\Users\32730\.qoderworkcn\workspace\`，分析完可清理
