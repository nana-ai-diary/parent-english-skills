---
name: parent-english-html
description: 把一个/一批亲子英语（育儿场景）视频做成自托管的 HTML 场景学习页 —— 一个总目录 + 每课一个子页，内含自托管视频、分段精听音频（原声 + 慢速）、词汇表、场景常用句、练习、避免中式英语、文化贴士。当用户给视频要求「做成 html 学习页 / 场景学习页 / 套用模版做一个页面 / 加一课 / 全系列重建」时使用。Build self-hosted parenting-English lesson pages (video + segmented listening audio + vocab + quizzes) from raw videos.
version: 1.8.2
---

# 亲子英语视频 → HTML 场景学习页

把用户自己剪的育儿视频，做成中文家长能直接用的英语学习页。
**一切走脚本，不要手搓 HTML** —— 版式改动只需改外壳 + 渲染函数，全系列秒级重生成。

## 交付形态（固定，别改）

```
<项目>/
├── tools/            ← 本 skill 的 scripts/ 原样复制到这里
├── work_prep/NN/     ← 转写、字幕拼图（中间产物）
├── work_ocr/NN.jsonl ← OCR 烧录字幕（**英文文本的事实源**）
├── work_seg/NN.json  ← 分段草稿
└── outputs/亲子英语/  ← 本地构建源（**发布目标见 Step 4，固定共享站，别新建域名**）
    ├── index.html            ← 总目录（读 series.json 渲染卡片 + 进度条）
    ├── covers/NN.jpg         ← 目录卡片封面
    └── 05-brush-teeth/       ← 一课 = 一个 ASCII slug 子目录
        ├── index.html
        ├── audio/  full.mp3 + seg01.mp3 + seg01_slow.mp3 + …
        ├── img/    poster.jpg
        └── video/  brush-teeth.mp4     ← 自托管 720p crf30，禁止外链
```

页面固定七个 Part（标题就叫这些，别再改回「词汇表 / 场景常用句」）：
① `Part 1｜听原声` ② `Part 2｜逐句精听`（分 3 天）③ `Part 3｜学词汇`（A–D 分带）
④ `Part 4｜学句子`（最重要）⑤ `Part 5｜练一练` ⑥ `Part 6｜避开中式英语`
⑦ `Part 7｜文化贴士`（选学；**可选，没有就整节不渲染**）。
开工卡里只有 **两张路线卡：懒人路线（第一个）+ 系统学习**，共用那句
`[3天场景开口法]：每天2句 · 3天一个场景…`。
Part 3 的 **A 档默认展开，B/C/D 档默认折叠**（`.band.tog` + `<table class="vt folded">`，
点标题条展开），免得一上来就是压力。

**总目录**（`build_catalog.py`）固定形态：标题「场景口语成长计划」→ 蓝色「怎么用」卡 →
**「我的学习」卡**（左 = **星星罐**，右 = 标题行 + 3 个统计卡 `🎬 已学习场景` / `💬 已掌握句子` /
`📅 已学习`，「今日打卡」是右上角的 `.mtoday` 药丸）→ 搜索框 + 四组筛选
（`分类` / `年龄段` / `难度` / **`进度`**）→ 卡片网格。
**星星罐**（`jarSVG()`）：每完成一个场景 = 1 颗彩星落进罐子；罐子容量 `JAR_CAP=30`（5 列 × 6 行）封顶，
满了只点亮光晕、不再多画 —— **这就是「课程加到几十上百课也不会画不完」的解法**，
别改回按内容量线性增长的花/草之类。
**视觉规格（第一版做过整齐网格的金星星，被用户否了，别再回去）**：奶油玻璃罐（`jarGlass` 渐变 + 白描边 +
左侧反光）+ **棕色盖**；星星**大小 / 颜色 / 角度 / 位置全部随机、互相压着堆在罐底**，
6 色 `['#f9c74f','#78c6e8','#79d6a4','#f9a8c9','#b3a1e6','#f8a05c']`；
随机必须走**按索引的稳定伪随机** `jarRnd(i,salt)=frac(sin(i*127.1+salt*311.7)*43758.5453)`，
这样新增一颗星不会打乱已有布局（**别用 `Math.random()`**）；
再加 6 个 `✦` 闪光（CSS `twinkle` 无限循环）和罐底一根金色迷你进度条。
**进度筛选**：`全部 / ⏳ 进行中 / ○ 未开始 / ✓ 已完成`，判定走 `progressState(slug)`
（无记录 = 未开始；`complete` = 已完成；有 listen/scene 进度 = 进行中），
卡片封面右上角同步显示 `✓ 已完成` / `⏳ 进行中` 徽章。

## Step 0 · 准备

```bash
cp -r <skill>/scripts/*.py <skill>/scripts/shell.html <skill>/scripts/data <项目>/tools/
mkdir -p <项目>/work_prep <项目>/work_ocr <项目>/work_seg "<项目>/outputs/亲子英语"
```

编辑 `tools/series.json`：`video_dir` / `image_dir` 指向素材目录。
`series.json` 是**系列唯一清单**（`n/src/by/slug/zh/en/video/image/cat/age/diff`），
改分类、改标题、改来源只动它 → 重跑 `build_catalog.py`，不用重渲染每一课。
`by` = 素材的 YouTube 频道（有 @ 就带 @，如 `@babylist`；没有就不带，如
`Confucius Institute Adelaide`），目录卡片和每课页头/页脚都由它派生。

## Step 1 · 新增一课

> **⚠️ 媒体规格从第一版就要对（2026-11-06 补，别等发布前再返工）**
> 新增任何一课，`audio/` **直接生成 Opus-in-Ogg**，不要先出 mp3 再转：
> `ffmpeg -y -i <src> -vn -c:a libopus -b:a 32k -ac 1 segNN.ogg`
> （慢速版在 `-i` 后加 `-af atempo=0.8`）；lesson JSON 里 `part1.full` 与每个 seg 的
> `audio` / `slow` 一律写 `.ogg`，生成的 HTML 不得出现 `.mp3` 引用。
> `video/*.mp4` 必须 **720p 且 ≤20MB**：`tools/compress_videos.py` 目标 18.5MB、
> AAC 64k、libx264 按片长反算视频码率，超 20MB 再 ×0.8 重压。
> 2–3 分钟的 1080p 双语字幕成片约 38MB（如 49 舞者），直接进站会把整包顶过 413。
> 实测：47 警察 21.87MB 超标 → 17.90MB；49 舞者 37.83MB → 18.20MB；48 老师 13.99MB 已达标。
> 音频 27 个文件 mp3 4.35MB → ogg 1.98MB。详见下方「压缩与打包」。
> **根因提醒**：上一轮 49 课退回到 mp3 + 1080p，就是因为没先加载本 skill 的手写 HTML。

```bash
# ① 登记 + 生成骨架（会写 series.json 与 tools/lessons/<slug>.json）
python tools/bootstrap_lesson.py add --no 35 --slug 35-feeding-cat \
    --zh 喂猫 --en "Feeding the Cat" --video "37.喂猫.mp4" --cat 生活起居 --diff 2 \
    --by "@SomeChannel"     # 素材的 YouTube 频道 → source / disclaim_src 自动带上
#    无烧录字幕、想完全手写内容的课，加 --manual：
#    python tools/bootstrap_lesson.py add --no 47 --slug 47-police-officer \
#        --zh 警察 --en "Police Officer" --video "警察.mp4" --cat 学习认知 \
#        --age "2–6 岁" --diff 2 --manual
#    → lesson JSON 标 "manual":true，且 tools/p2/47.json 写 {"manual":true}；
#      rebuild_all 会跳过 reseg+apply_p2（不跑 OCR 对齐），直接用你写好的
#      part2/cuts 去 build_media + build_lesson。

# ② 转写（small + beam1 + temp0 + vad）+ 生成字幕拼图 sheet.jpg / tipstrip.jpg
python tools/prep.py 35
#    转写段落数明显偏少（语音 < 时长的 60%）时换 retr.py 重跑（去 VAD + initial_prompt）

# ③ OCR 烧录字幕（英文文本的事实源）
python tools/ocr_subs.py 35
#    没有烧录字幕的视频（如自剪素材）会自动回退到转写稿：
#    ocr_subs.py 检测到字幕行过少时，读取 work_prep/<n>/transcript.json
#    （或 `python tools/ocr_subs.py 35 --transcript <path>` 显式指定），
#    把转写段当事实源写出 work_ocr/<n>.{jsonl,txt}，后续 fill 照常可用。

# ④ 词级时间戳（切点精修要用；whisper word_timestamps=True，约 20 秒/课）
python tools/wordtime.py 35
#    ⚠️ 生成完**必须**自检覆盖率（下面这行会报哪几课不合格）：
python tools/vadcheck.py 35 --write     # 逐课比「默认 VAD / 关 VAD」的对齐覆盖率，取高的写回

# ⑤ 用 OCR 行把 part2 的 en 填成 9 段初稿（同时给出 cuts 初值）
python tools/bootstrap_lesson.py fill --no 35
```

**⑤b 定分段（这一步偷不得懒）。** `fill` 只把 OCR 行**九等分**，得到的是机械分段，
绝不是能发布的版本。必须自己按语义重写 `tools/lessons/<slug>.json` 的 `part2`：

- 段数**不固定**（本系列 6–10 段，通常 9 段 = 3 天 × 3 段），每段 5–20 秒；
  按「一个完整小动作 / 一个话题」切，别把半句话切到下一段。
- 每段的 `en` 是**对齐用的目标文本**（`apply_p2` 会拿它去 OCR 行序列上做单调 DP，
  再把 en 换成 OCR 校正文），所以写得越接近 OCR 原文，DP 越准。
- `en` 里直接写高亮 span（`<span class='k y|g|b|c' title='中文释义'>词</span>`），
  span 里的词**必须能在 OCR 正文里原样找到**（大小写、标点都要一致），否则会静默丢高亮。
- `cn` 是**整段的自然译文**（不是摘要），而且**必须按 span 的先后顺序出现 title 词**——
  `hl_cn` 是从左到右找的，顺序反了就挂不上（`verify_deep.py` 会报覆盖率）。
- `ti` 是段标题（一行短句）。
- 参考做法：写一个 `tools/_fillNN.py` 一次性脚本拼 JSON（比手改 JSON 稳，也留了档）。

**封面。** 有配图海报的课走 `make_covers.py`（自动裁掉「宝妈必看」粉条）。
**没有海报的课**（纯视频素材）要在 `make_covers.py` 的 `VIDEO_FRAME` 里登记
`{"NN": (取帧秒, 字幕条上沿比例)}`，再 `python tools/make_covers.py --only NN` 单独生成：

- 取帧选**主体清楚、能裁成 3:2** 的那一秒（成品展示 / 户外镜头最好）；
- 字幕条上沿比例看 1080p 素材约 **0.85**（1 帧 1 秒 OCR 出来的字幕落在 y≈0.87 以下），
  比值给大了封面底下会压一条中英字幕，很难看；
- 老课 `--only` 之外的课不会被碰，改完记得 `build_catalog.py`。

**来源频道（`by`）** 是唯一权威字段，`source` / `disclaim_src` 都由它派生，别手改：

```bash
python tools/apply_src.py            # dry：只报会改什么
python tools/apply_src.py --write    # 真写（幂等；series.json 已有的 by 优先）
python tools/apply_src.py --check    # 校验 series.json 的 by ↔ 每课 source/disclaim 一致
```

批量补登老课：把 `apply_src.py` 顶部的 `CHANNELS` 表填好（`{"02": "@babylist", …}`），
`--write` 一次灌完。改完来源**只需重建页面**（`build_lesson.py` + `build_catalog.py`），
音频、视频、封面都不用动。

**`wordtime.py` 最容易被 VAD 坑。** 室内低声说话 / 边玩边喊的课（躲猫猫、游乐场、
坐车），faster-whisper 默认的 Silero VAD 会把语音当成噪声**滤掉 85%–98%**，
`words.json` 只剩几个词 —— 于是 `cutfit` 静默跳过，切点退回 OCR 原值，每段末尾
都多带后一句几个词。判据看**「整课文本 ↔ 转录」的对齐覆盖率**，低于 60% 就是被滤了：

```bash
python tools/cuttail.py | tail -3     # 汇总里若「干净」比例很低，先查覆盖率
```

补救：`python tools/vadcheck.py <课号> --write`（对同一段音频跑「默认 VAD / 关 VAD」
两套，取对齐覆盖率高的那套写回）。关 VAD 时补 `no_speech_threshold=0.6
logprob_threshold=-1.0`。**覆盖率 ≥ 80% 才算合格。**

**写内容前先看图**：`work_prep/NN/sheet.jpg`（字幕条）、`tipstrip.jpg`（画面下方的 Tip 卡片）、
`transcript.txt`。视频自带的烧录中文是机翻，**一律自己重译**。
视频里的粉色 Tip 卡片 → 做成段落里的「💡 关键信息」。

把 `tools/lessons/<slug>.json` 的 part3–part7 写好，再进 Step 2。
（`part3` 4 个 band / `part4` 4 组句 / `part5` 8 题 / `part6` rows 是**三元数组**。）

## Step 2 · 跑流水线

```bash
python tools/rebuild_all.py 35          # reseg → apply_p2 → build_media → build_lesson
python tools/rebuild_all.py             # 全系列
python tools/rebuild_all.py --cuts-only # 只改了切点时：不重编码视频，只重切分段音频
```

链路：`reseg.py`（OCR→分段）→ `apply_p2.py`（对齐 + 写回 en/cuts，内含长句拆句
`rsplit.py` 与切点精修 `cutfit.py`）→ `build_media.py`（音频/封面/720p）→
`build_lesson.py`（渲染 7 个 Part）→ `build_catalog.py`（目录）。

**顺序有依赖**：`apply_p2` 会重写 en/cuts；手写中文用 `apply_cn.py`，必须在它之后跑。

### 只改了外壳 / 渲染函数时（版式、标题、打卡口径、文案…）

**不要**跑 `rebuild_all.py`（它会重新编码视频）。逐课重渲染页面即可，秒级完成：

```bash
# 逐课重渲染（tools/lessons/*.json 全跑一遍）
for f in tools/lessons/*.json; do python tools/build_lesson.py "$f"; done
python tools/reskin01.py     # ① 遗留手工页：没有 lesson.json 的课要走它对齐外壳
python tools/build_catalog.py
```

`reskin01.py` 只做三件事：**套最新外壳**（折叠 CSS/JS、路线列数、进度上报自动跟齐）、
**七章标题改名**、**Part 3 的 B/C/D 折叠**；正文（hero / 各 Part 内容 / 词表数据）原样保留，
可重复跑。它是给「早期手搓页」兜底的，新项目用不到；复用到别的课要改脚本顶部的路径常量。

```bash
python tools/dump_p2.py 35        # 看某课的 en 初稿
python tools/dump_cn.py 35        # 看 英文 / 高亮释义 / 中文
python tools/apply_cn.py 35 --write   # 用手写 tools/cn/35.json 覆盖中文
```

## Step 3 · 校验（改完必跑）

```bash
python tools/check_series.py      # 资源存在 / 锚点有 id / 标签配平 / 七个 Part 齐全
python tools/verify_review.py     # 34 篇回归，只看 <b> 里的 Day 例句
python tools/verify_deep.py       # 每个 segNN.mp3 实际时长 ≈ cuts 的 (b-a)，偏差 >0.4s 报警；中文高亮覆盖率
python tools/check_punct.py       # 段末缺句末标点 / 句中冒大写
python tools/dump_goals.py        # Day 目标长度分布 / >16 词 / 断尾
python tools/rsplit.py --remain   # 还剩多少 ≥18 词的长句
python tools/cuttail.py           # **切点主判据**：拿整片词级时间量「头尾各多带几个词」
python tools/segcheck.py          # 辅判据：把每个分段音频重新听一遍（粗筛，会幻觉）
python tools/apply_src.py --check # 来源频道：series.json 的 by ↔ 每课 source/disclaim 是否一致
```

### 切点：两个判据，用对场景

| 工具 | 数据源 | 用途 |
|---|---|---|
| `cuttail.py` | `work_prep/NN/words.json`（整片词级时间） | **定量**。输出 `尾多N / 头多N / 被切短`，可 `--list` 列问题、`--base` 看精修前 |
| `segcheck.py` | 把 `segNN.mp3` 单独重听一遍 | **粗筛**。片段短、无上下文，尾部静音上 whisper 会**幻觉**（凭空冒出 "always remember to check out our website…"），所以只能看趋势，不能逐字当真 |

改切点的标准流程：

```bash
python tools/cuttail.py --base            # ① 精修前基线（读 work_seg/NN.precut.json）
python tools/refit_cuts.py --write        # ② 用当前 words.json 重算并写回 lesson JSON
python tools/rebuild_audio.py             # ③ 只重切分段音频，不碰视频/封面
python tools/cuttail.py --list            # ④ 复查，目标：干净 100%、无「被切短」
```

`refit_cuts.py` 只改 `cuts`，**一个字都不动** —— 文本已经校对过，重跑整条
`apply_p2` 反而有回归风险。它和 `apply_p2` 里内置的 `cutfit.refine()` 用同一套
规则、同一个基准（`work_seg/NN.precut.json`），所以两条路结果一致、可复现。

判据阈值：`尾多0` = `b ≤ 末词说完 + 0.35s`；`被切短` = `末词说完 > b + 0.20s`
（音频把最后一个词截了）。**「被切短」和「尾多带」都要修**，前者更烦人。

## 压缩与打包（发布前必做，规避整站 413）

> 标题虽写「发布前」，但**新增单课时就得按 ogg + ≤20MB 产出**（见 Step 1 开头）；
> 不要把 mp3 / 1080p 视频留到发布前才处理。发布前这段只负责全站体检与打包。

整站是**覆盖式静态发布**，且目录很容易破发布体积上限（实测触发 HTTP **413**）。
本项目控包靠「音频转 Opus」，**不是重压视频**：

**① 音频转 Opus/ogg（控包核心）**
分段 mp3 转 `Opus-in-Ogg`（`libopus -b:a 32k -ac 1`）：对语音近透明，单声道 32k 比原 64k 再砍一半体积。
python http.server 会把 `.ogg` 映射为 `audio/ogg`，全平台可播。
配套动作：
- 把各课 HTML 里的 `segNN.mp3` / `segNN_slow.mp3` 引用改成 `.ogg`（批量替换脚本 `replace_html_mp3.py`）；
- 打包脚本 `pack_site.py` 的 `copytree` 加 `ignore=shutil.ignore_patterns('*.mp3')`，
  **让包内永远只进 ogg、忽略所有 mp3**（源 mp3 残留在磁盘也不进包，无需真删）。

**② 整站 413 实战**：视频已压到 720p `-crf 30`（约 4–5.5 MB/篇）仍超上限 →
全部分段音频转 Opus 后，整站从 **852 MB → 646 MB** 才通过发布
（目录 >300MB 时正解是把 audio/video 迁对象存储，本项目用转 Opus 控包够用）。

**③ full.mp3 = 整视频「音频」交付物（用户术语约定）**
用户明确：「做这个视频的 HTML、PDF 和**音频**」里的"音频" = **整视频 MP3**（即 `audio/full.mp3` 形态），不是分段 ogg。
抽取命令（由源视频抽整轨，不做裁剪）：
```bash
ffmpeg -y -i <src>.mp4 -vn -c:a libmp3lame -b:a 128k -ar 44100 <课目录>/audio/full.mp3
```
整站页面播放的是分段 ogg；**full.mp3 不进整站页面**，作为网盘/售卖资料单独交付。

**④ 旧 mp3 清理的沙箱守卫**：脚本里 `os.remove` / `shutil.rmtree` 批量删 >50 个文件会触发
`SAFE_DELETE_BULK_CONFIRM_REQUIRED` 被 SIGTERM 静默杀掉。规避：靠 ① 的 pack_site `ignore`
让 mp3 不进包，或把残留 mp3 改名移出目录（而非硬删）。不要写 `rm -rf` / 大批量 `os.remove` 循环。

**⑤ 全套 PDF 是网盘资料，不进整站**：由 `tools/make_pdf.py <slug>` 把各课 `lesson.json` 渲染为
`outputs/亲子英语/全套PDF/<视频基名>.pdf`（如 `42.消防车2.pdf`、`万圣节.pdf`）。
PDF 是给用户的下载/售卖资料，**不属于整站发布源**，整站包也不含 `全套PDF/`。
（目录页封面裂图=源 `covers/` 缺该课 jpg：`make_covers.py --only NN` 用 `VIDEO_FRAME` 取干净帧补；
`series.json` 的 `video` 字段若带 `_双语字幕` 后缀会匹配失败，要从已压缩的 outputs 视频取帧。）

## Step 4 · 发布（⚠️ 固定走共享站，别新建域名）

### 两条铁律（务必遵守）
1. **发布目标唯一固定**：所有课只进共享站。用户说的「HTML 要放到这里」指的是**课程总目录页完整地址**：
   `https://<SHARED_SITE_HOST>/s/<CONTENT_ROOT>/index.html`
   （根 `/` 是激活码门禁页，不是课程页；内容根 `s/<CONTENT_ROOT>/` 由 `gate.json` 的 `content_root` 决定）。
   **禁止**新建 HTML 站点、**禁止**发到其他域名 / 沙箱。这个地址经常被忘，每课收口时先对一遍。
2. **先问后发**：课做完、AI 自查通过、且用户看过表示「没啥问题」之后，
   **只问一句：「要不要上线到 https://<SHARED_SITE_HOST>/？」**，
   拿到明确「要」才发。**不要**自动发布，**不要**发到别的链接。

### 为什么不能直接 deploy `outputs/亲子英语/`（血泪教训）
部署工具按「目录绝对路径」绑定 app：同一目录 → 同一 app（覆盖式、保留原链接）；
不同目录 → 新建一个 app（新域名）。共享站 `<SHARED_SITE_SLUG>` 的**真实绑定目录**是：

```
<GATE_PROJECT>/outputs/<SHARED_SITE_DIR>
appId: <APP_ID>  （显示名「新生儿起床口语」）
```

本地构建目录 `outputs/亲子英语/`（在**当前任务** workspace 下）是**另一条路径**，
直接 deploy 它会新建一个独立 app（曾误建 `lesson47-police`），永远碰不到共享站。
**所以：永远 deploy 上面的 `<SHARED_SITE_SLUG>` 目录，不要 deploy `outputs/亲子英语/`。**

> 若该绑定目录日后变了，读对应 `.genie` 文件（`*.wbapp_*.genie`）里的 `localDir` 字段确认
> （`<SHARED_SITE_SLUG>` 的 genie 中 `localDir` 即上面的路径；显示名「新生儿起床口语」）。

### ⚠️ 共享站是「带激活码门禁的付费站」，绝不能直接 robocopy
（2026-11-06 事故复盘：曾把无门禁构建源直接同步进发布根目录，
覆盖掉门禁页 + 留下裸奔副本 → 别人点课全 404、且有人免激活码就能看）

发布目录 `<GATE_PROJECT>/outputs/<SHARED_SITE_DIR>/` 的**正确结构**：

```
<SHARED_SITE_SLUG>/
├── index.html        ← 门禁页（gate.html，输入激活码）；不是课程目录页！
├── pe-admin.html     ← 激活码管理后台
├── pe-sdk.js         ← 云 SDK 本地副本
├── pe-guard.js       ← 访问守卫
├── s/index.html      ← 占位页（跳回 /），挡目录列表
└── s/<CONTENT_ROOT>/   ← 随机内容根（gate.json 的 content_root）
    ├── index.html    ← 48 课总目录（带守卫）
    ├── covers/ 全套PDF/ 全套音频/
    └── 01-xxx/ … 48-xxx/  ← 每课目录，每个 .html 都注入 <script src="/pe-guard.js">
```

门禁机制：门禁页输码 → 云端 `pe_activate` RPC 返回 `token` + `root` → 存入
localStorage `pe.tok/pe.dev/pe.root` → 跳 `/<root>/index.html`；守卫校验凭证、
且 `location.pathname` 必须位于 `/<root>/` 下，否则 `location.replace('/')` 弹回门禁页。
**根目录里任何课程页 / 目录页都是无守卫的裸奔内容，等于付费内容泄露。**

### 正确上线流程（加新课 / 改内容）
1. 在**构建源**做内容，注意构建源不是当前任务 workspace，而是打包器认的那个：
   ```
   <GATE_PROJECT>/outputs/亲子英语/   ← pack_site.py 的 SRC
   <GATE_PROJECT>/tools/pack_site.py   ← 门禁打包器
   <GATE_PROJECT>/tools/gate.json      ← content_root / 云配置
   ```
   当前任务 workspace 的 `outputs/亲子英语/` 做完课后，把**新增内容**（课目录、`index.html`
   总目录、`covers/NN.jpg`、`全套PDF/*.pdf`）同步进上面那个构建源；
   音频须为 `.ogg`（Opus 32k 单声道）且 HTML 引用 `.ogg`，与旧课一致。
   **保持构建源无守卫**，守卫由打包器统一注入。
2. 跑打包器（它负责搬进内容根、给每个 html 注入守卫、重写门禁页/后台/SDK/守卫）：
   ```bash
   cd <GATE_PROJECT>
   python tools/pack_site.py              # 输出到 .genie 的 localDir
   python tools/pack_site.py --verify     # 体检：守卫覆盖率、门禁页是否泄露内容根
   ```
3. deploy 绑定目录（覆盖共享站、保留原链接）：
   ```bash
   # workbuddy_sites_deploy
   directory = <GATE_PROJECT>/outputs/<SHARED_SITE_DIR>
   entryHtml = "index.html"
   domainPrefix = "<SHARED_SITE_SLUG>"
   userAskedToPublish = true
   ```
4. **线上验证**（别只信 `verified:true`）：根 `/` 必须是门禁页（含 `pe_activate`、
   `slug:'` 计数为 0、不含内容根路径）；内容根下目录 `slug:'` = 总课数；
   抽查课页含 `pe-guard.js`；根目录下**不能**有课页直链 200 出真实内容。

### 平台是「增量覆盖」，删文件必须写同名占位页
发布平台**不会删除** sandbox 里已有的旧文件。本地移走裸奔副本后，线上旧 URL 仍返回
200 且是旧内容（`Last-Modified` 不变）。因此清理时必须用**同名占位页覆盖**：
HTML 写 `<script>location.replace('/')</script>` 的跳转页，静态资源写短文本置空，
再重新 deploy。可复用 `<CURRENT_PROJECT>/tools/fix_site_gate.py`（`--apply`），
它已封装「备份 → 清裸奔 → 占位覆盖 → 恢复门禁 → 补 47/48 → 体检」全流程。

体积：整站约 684 MB，**413 阈值约 770 MB**，加课前先确认没超。

### 网盘 / 售卖资料（不进整站）
按「压缩与打包」③⑤，`full.mp3`（整视频「音频」）与 `全套PDF/`（各课 PDF）是网盘/售卖资料，
单独交付，不随整站发布（整站页面只含分段 ogg 音频）。夸克 / 百度上传走 `parent-english-netdisk` skill。

### 公开仓库副本必须脱敏
本 skill 会备份到 public 仓库，**不得写入**本机绝对路径、共享站域名 / `appId` /
激活码内容根（随机码）/ 云配置密钥 / 本地代理地址 / 用户目录名。Step 4 的这些环境值在公开副本里
统一替换为占位符：`<SHARED_SITE_HOST>` / `<SHARED_SITE_SLUG>` / `<SHARED_SITE_DIR>` /
`<GATE_PROJECT>` / `<CURRENT_PROJECT>` / `<APP_ID>` / `<CONTENT_ROOT>` / `%TEMP%`；
真实值只留在本机 skill、`.genie` marker 和 workspace 记忆里。
生成公开副本用本机工作区的 `tools/sanitize_public.py`（替换表带真实值，**只留本机、不进仓库**；
写完强制跑敏感词校验，有残留直接抛错禁止推送），
推送走 `github-api-sync` skill（本环境 `git push` 被阻断，改走 GitHub REST API）：
先 `--dry-run` → 正式提交 → 用 Contents API 拉回文件再扫一遍敏感词，确认远端无残留。
`scripts/series.json` 的 `video_dir` / `image_dir` 在公开副本里固定用 `~\Videos\...` 泛化路径，
**本地那份带绝对路径的版本不要推**。

## 关键规格

| 项 | 值 |
|---|---|
| 转写 | faster-whisper `small` + `beam_size=1` + `temperature=0` + `condition_on_previous_text=False`（+`vad_filter`）。`medium+beam5` 慢 80 倍且没必要 |
| 词级时间戳 | 同上 + `word_timestamps=True`（`wordtime.py`，约 20 秒/课）。**安静/嘈杂的课必须关 VAD**：`vad_filter=False` + `no_speech_threshold=0.6` + `log_prob_threshold=-1.0`；自检 `vadcheck.py`，对齐覆盖率 <60% 就是被滤残了 |
| 语音覆盖不足时 | 去掉 `vad_filter` + 加 `initial_prompt`（塞该课主题词），见 `retr.py` |
| OCR 裁剪 | `crop=iw:ih*0.30:0:ih*0.70` + 文本框纵向中心 `CY_MIN=0.33`（字幕在 y 0.83–0.99，Tip 卡在 y<0.79） |
| RapidOCR 参数 | 必须**扁平前缀**：`RapidOCR(det_limit_side_len=960, det_limit_type='max', …)`；写成 `Det.limit_type=` 无效 |
| full.mp3 | 44.1 kHz / **128 kbps** / 单声道（整视频「音频」交付物；用户术语约定：说"音频"即指整视频 MP3 = `audio/full.mp3`，抽轨命令见下「压缩与打包」节） |
| segNN.mp3 | 16 kHz / 64 kbps / 单声道；`segNN_slow.mp3` = 同上 + `atempo=0.8` |
| 视频 | 720p / `libx264 -crf 30 -preset medium -profile:v main` / `+faststart`（约 4–5.5 MB/篇） |
| 存储 key | 每课独立 `<缩写>.check` / `<缩写>.fav`（**不要共用**，词汇 id 会跨课撞车）+ 汇总 `xhs.progress.<slug>` |
| 进度口径 | `xhs.progress.<slug>` = `{listen,listenTotal,scene,sceneTotal,complete,ts}`。**只统计 Part 2 的 Day 打卡（精听进度）与 Part 4 的场景句打卡（已掌握句数），Part 3 单词打卡不计入**。`ts` 只在页面确有打勾动作时刷新（否则「打开页面」会被算成今天打过卡）。另写 `xhs.days = ['YYYY-MM-DD',…]` 供目录页算「已学习 X 天」，**`xhs.jar` = `{d,s}`** 记录星星罐已庆祝到的日期 / 星数（`d` 去重「今天第一次打卡」、`s` 去重「新收集一颗星」） |
| 场景完成 | `complete = (Day 全打完) 或 (场景句全打完)`（一字之差就换口径：`tools/shell.html` 的 `save()` 里那个 `\|\|`） |

## 内容规范

> ⚠️ **文案红线：不要写「系列内排名 / 唯一」式描述。** 系列还在更新，写「全套 34 集里唯一讲 XX 的一集」
> 「唯一一集有完整食谱的」「全套里最短最好上手的一集」「这套系列里最能直接用上的」都会过时，
> 也不该当卖点。**课内**表述可以留（「这一套动作」「整集反复强调」「这一集最值得带回家的一个点」）。
> 写完自查：`python tools/fix_blurbs.py --dry`（列/改不符合的），正则
> `全套|唯一一集|最短最好上手|系列里最|这套系列` + `最[^，。；、]{0,10}(篇|集|课)`。
> 顺带一提：**每个内容页的 `<head>` 都要带 `noindex,nofollow,noarchive`**（付费内容别被搜索引擎收录），
> 这个已经写进 `shell.html` 和 `build_catalog.py` 的模板里了。

- **英文文本的事实源是视频烧录字幕（OCR），不是转写**。转写拼写对但会漏听；OCR 会认错字但
  「有几个词」可信 → `reseg.repair()` 只**就地正名**，绝不增删词。OCR 真的漏了词时，
  用 `tools/p2/NN.json` 的 `segs.NN.en` 手写覆盖（例：05 课的 `electric toothbrush`）。
- **中文必须逐句对应英文**，并**沿用英文高亮 span 的 title 词**（否则同色高亮挂不上）。
  手写译文放 `tools/cn/NN.json`，`apply_cn.py NN --write` 写回。
- **长句**：`rsplit.py` 自动给 ≥18 词且没内部标点的句子补断句（DP 选点 + 高亮保护），
  规则判不出的写进它的 `FIX` 表（只插标点、只改大小写，**绝不增删词**）。
- **切点**走**词级时间戳 + 全局对齐**（`cutfit.py`），不要退回用 OCR 帧时间
  （1 秒一帧，系统性偏晚 → 每段末尾都会多带出后一句几个词）：
  ```
  a = 首词时刻 − PAD_HEAD(0.30)，且不早于「上一个词说完」
  b = min(末词时刻 + TAIL(0.12), 末词时刻 + 与下一个词的中点)
  ```
  尾部护栏看**语义证据**而不是写死秒数：本段**末尾的词有没有对上转录**。
  对上了就信 `t_end`（允许收尾，也允许**回补** —— OCR 有时把终点定得过早，
  页面文本比音频长，07 课整首字母歌只给了 3.5 秒音频）；对不上就按覆盖率
  给保守回收量（覆盖率 ≥0.80 收 3.0s / ≥0.60 收 1.9s / 更低收 1.3s）。
  回补的上界用**下一段精修后的 `a`** 卡住，不会串段。
  实在判不出的，写 `tools/cutsfix.json` 手写覆盖（例：24 课末段视频里说了
  两遍 "good job"，页面只有一遍，自动层不敢收尾）。
- **Day 目标**（今日要掌握）：自动打分（祈使句 +3.5 / 片段 −3.5 / 超 8 词每词 −1 …），
  连读旁白切不动 → 用 `tools/goals.json` 手写覆盖。
- **来源必须如实标注**。`series.json` 的 `by` 是唯一权威来源，页头 `srcbar`
  （`来源：YouTube @xxx`）、页脚版权声明（`版权归原作者（YouTube @xxx）所有`）、
  目录卡片的小字都由它派生 → 走 `apply_src.py`，别在 HTML / lesson JSON 里手改。
  ⚠️ **用户明确要求每课都要写来源，这是最容易漏的一项**：发布前必查页头 + 页脚，
  并跑 `python tools/apply_src.py --check`；`parent-english-pipeline` 的 `verify` 也把它列为必填项。
  频道名可由 `pe.py fetch` 的 `--write-info-json` 自动采集写入 `by`（`pe.py source <no>` 可补抓），
  不要靠记忆手填。
  用户分批给频道时，先在 `CHANNELS` 表里补全再 `--write`。
- **Part 6 第一栏必须是「中式英语的英文说法」**，不是中文。

## 高亮配对铁律（2026-10-23 实测，别再犯）

`build_lesson.py` 的 `hl_cn()` 把英文高亮词在中文里**同色加粗**，靠的是：英文
`<span class='k X' title='中文'>词</span>` 里的 `title` 必须在中文译文里**原样找得到**
（四级匹配：原样 → 去括号 → 按顿号/斜杠拆 → 最长公共子串兜底；都对不上就**整段不标**，记进 UNMATCHED）。
这条规则有几个极易踩、且用户会直接看到的坑：

1. **`title` 必须是中文译文里实际出现的字串，不能只是语义对应。** 写 `flight → 飞行` 但译文写的是
   「飞机」，配对失败 → 中文侧整段不标 → 看起来「高亮没对应上」。正确做法：`title` 直接写译文里那个词
   （`flight → 飞机`）。逐字对齐，别 paraphrase。改完跑一次配对校验（见下），**0 未配对**才算过关。
2. **两个英文词对应中文同一个词，只能合并成一个高亮。** 例：`cabin entry door` 都对应「客舱门」、
   `tight squeeze` 都对应「挤」——若拆成两个 `<span title='客舱门'>` + `<span title='舱门'>`，
   第二个会因位置重叠 / 找不到剩余命中而挂不上。正解：把两个英文词包进**同一个**
   `<span class='k y' title='客舱门'>cabin entry door</span>`。
3. **不要高亮过于简单的词**（`come on` / `let's go` / `what's this` / `yeah` / `baby` / `cat` / 好的 / 来 等）。
   用户明确反感「把读者当傻子、没话找话」式的高亮。只标**陌生词 / 固定搭配 / 词组 / 难点**
   （如 `on fire`≠`has fire`、`turn it on` 代词放中间、`just in case`）。每段 1–4 个点，紧凑 `**词**＝释义` 格式。
   **量化护栏**：`tools/lint_highlights.py`（warn-only）把 part2 里被高亮的词和「超简单禁用词表」(SIMPLE) 比对，
   命中即报警（如 `help` / `stop` / `call` / `city` / `lost` / `ride` / `safe` / 裸 `police` / `grandma` / `mom` / `dad` /
   `baby` 及基础动词、系词、冠词）。**发布前跑一遍，目标 0 命中**；短语（如 `police officer` / `police car`）不会误伤，
   因为比对只认整词、且表里无短语。命中就说明那段是凑数高亮，删掉该 span 即可（词仍保留在正文，只是不标重点）。
4. **词汇表别凑数**：删掉一眼就懂的行（如「猫＝cat」）；被点名要拓展的 band 要真正拓展
   （例：救援工具要列 `hose / axe / helmet / hydrant / extinguisher`，不能只写「消防车 / 消防员」）。
5. **分类（`cat`）以 `series.json` 为准**。目录页的筛选读的是 `series.json` 的 `cat`，不是 lesson JSON 的 `tags`。
   改分类只动 `series.json` 的 `cat` → 重跑 `build_catalog.py`，不要去手改 lesson JSON。

**配对校验脚本**（每次改完 part2 高亮都跑一遍，已沉淀为 `tools/verify_pairing.py`）：

```python
import json, importlib.util
spec = importlib.util.spec_from_file_location("bl", "tools/build_lesson.py")
bl = importlib.util.module_from_spec(spec); spec.loader.exec_module(bl)
for slug in ["42-fire-truck-2","43-plane-types","44-plane-exterior","45-plane-interior"]:
    d = json.load(open(f"tools/lessons/{slug}.json", encoding="utf-8"))
    bl.UNMATCHED = []
    for s in d["part2"]:
        if s.get("type") != "seg": continue
        bl.hl_cn(s["cn"], s["en"], slug, s.get("no",""))
    print(slug, "UNMATCHED:", bl.UNMATCHED or "0 ✓")
```

## 常见的坑

- **VAD 会把语音整段滤掉**。faster-whisper 默认开 `vad_filter=True`（Silero），
  室内低声说话 / 边玩边喊的课（躲猫猫、游乐场、坐车、换纸尿裤）会被滤掉
  85%–98% 的语音，`transcript.json` / `words.json` 只剩几个词。后果不只是转写难看：
  **切点精修会静默跳过**，每段音频末尾都多带后一句几个词。自检 → `tools/vadcheck.py <课号>`。
- **whisper 会在长静音上复读**：同一句话连出十几遍，且每个词的时间戳被压成同一个时刻。
  它会把全局对齐的锚点拖到最后一遍 → 最后一段的切点被拉到片尾。`cutfit.index()` 里的
  `_dedup_repeats()` 已经处理（n 元组重复 ≥3 次且该块 ≥60% 的词时长为 0 就剪掉）。
- **`segcheck.py` 会幻觉**，别把它的数字当绝对值；定量一律用 `cuttail.py`。
- **沙箱批量删除守卫**：脚本里出现 `shutil.rmtree`、或 bash 一行 `rm -f` 超过约 9 个文件会被
  SIGTERM 静默杀掉（「无输出、退出码非 0」）。用 python `os.remove` 循环、每批 ≤9 个。
- `cuts` 必须与 part2 的 seg 数量 **1:1**；段数变了要用 `rebuild_audio.py` 清掉多余的 seg 文件。
- **新增了 Part 7 文化贴士的课，要登记进 `verify_review.py` 的 `KEEP_P7` 白名单**
  （那张表是「允许有 Part 7」的名单，不登记会被判成「part7 存在=True（应为 False）」）。
  反过来，纯动作教学课没有真正的文化内容 → `tools/p2/NN.json` 里写 `{"drop_part7": true}` 整节去掉。
- **OCR 大小写/标点偶发错误**（句中的逗号被读成句号、段首大写被 ASR 带进来、
  单字母大小写搞反）→ 写进 `apply_p2.py` 的 `CAP_FIX` 表（键是课号，值是 `(原文, 改成)`）。
  它跑在 `join_run` 之后、`apply_marks` 之前，所以**加了补丁后高亮 span 的字面量要和补丁后的文本一致**，
  否则那一条高亮会静默消失。
- 视频/封面与 cuts **无关**（整条片子压的、封面只看 `poster_t`）→ 改切点只需重切音频，
  不用重编码 470 MB 视频，用 `--cuts-only`。
- 改了 `part2` 的英文写法后，**高亮 span 会跟着迁移**（`apply_marks` 按原文 find）；
  一旦增删词，span 就会丢，`apply_p2` 会打印 `⚠ 高亮词在新英文里找不到`。
- **手写资产**：`tools/cn/`、`tools/p2/`、`tools/goals.json`、`tools/cutsfix.json`、
  `tools/enpatch.py` 的 `PATCH` 表。重跑 `apply_p2` 后要确认它们仍被应用
  （`apply_cn.py` 必须在 `apply_p2` **之后**跑）。`enpatch.py` 只做「整串精确替换、
  必须命中 1 次」，用来修 `apply_p2` 不会碰的极个别瑕疵（`But Let's` → `But let's`、
  漏掉列表逗号、OCR 噪声词），**不许动 <span> 里的高亮词**。
- **改版式后验收目录页**：起一个本地静态服务（服务 `outputs/亲子英语/`）→ 无头 Chrome 截图。
  四个固定坑：① **服务必须用后台任务起**（`( ... &)` 起的会在 shell 退出时被带走 → Chrome 拿 502 →
  **截图静默不写文件**，而日志照样打印「文件名 + 大小」，那其实是上一次的旧图；
  **判据是看 PNG 的 mtime**）；② **临时副本一律 `_` 开头命名、放在 `outputs/亲子英语/` 下，验完立刻删** ——
  那是发布源，打包会整包打进去；③ headless Chrome 默认渲染**深色**，要验浅色就把
  `@media\(prefers-color-scheme:dark\)\{[\s\S]*?\n\}\n` 整块正则删掉再截图；
  ④ 交互类断言（点了 chip 之后剩几张卡）要**注入脚本把结果写进 `<div id="RESULT">`**，
   再 `--dump-dom` 后 grep —— 用 `<title>` / `setTimeout` 回读都不稳。
  开跑前 `taskkill /IM chrome.exe /F` 清残留实例、URL 挂 `?_=<ts>` 破缓存，否则会静默复用旧图。
  改完 JS 顺手抽出页面里的 `<script>` 丢给 `node --check` 做语法自检。
- Windows：Bash（Git Bash）常缺 coreutils，文件操作改用 PowerShell；Chrome headless 截图
  必须输出到 `%TEMP%\`。
