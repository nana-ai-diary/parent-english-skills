---
name: parent-english-pipeline
description: 亲子英语单课流水线的编排层与状态机。把「找素材→下载（自动采集来源）→剪辑→双语字幕→字幕核对→HTML/MP3/PDF/文案→双网盘上传→终验→发帖」收敛成固定目录下的一课一档，提供 pe.py 命令、幂等续跑、字幕 QA 自动检查与人工闸门。当用户说「做第N课 / 加一课 / 第N课到哪了 / 继续第N课 / 字幕没问题 / 核对一下字幕 / 传网盘 / 这课可以发了吗 / 来源补一下 / HTML 放哪 / 改了字幕重跑」时使用。Orchestrate one parenting-English lesson end to end.
version: 1.1.0
---

# 亲子英语 · 单课编排层

**定位：编排 + 状态 + 校验，不重写下游 4 个 skill。** 具体创作（烧字幕、写 HTML 内容、写文案）
仍由 `bilingual-subtitles` / `parent-english-html` / `video-english-xhs` / `parent-english-netdisk` 执行，
本层负责：固定路径、记住进度、跑自动检查、卡住不该往下走的步骤。

## 固定事实（用户明确要求记住，别再忘 / 别再问）

| 项 | 值 |
|---|---|
| **HTML 发布地址** | `https://<SHARED_SITE_HOST>/s/<CONTENT_ROOT>/index.html` —— 用户说的「HTML 放这里」指**带激活码门禁的内容根下的总目录页**，不是根域名、不是新建站点。门禁打包器在 `config.yaml: gate_project`，上线仍「先问后发」。 |
| **定稿交付目录** | `<DELIVERY_DIR>/`，文件名固定 `<序号>.<主题>.mp4`（如 `47.警察.mp4` / `48.老师.mp4`）。`upload` 会把 `final.mp4` 交付到这里；已存在则**不覆盖人工定稿**。 |
| **HTML 站里的媒体** | **压缩版**：720p / `libx264 -crf 30` 视频 + Opus-in-Ogg 32k 单声道分段音频（`segNN.ogg`）。只进整站，不进网盘。 |
| **整站发布包的媒体压缩硬核查** | 针对 `config.yaml: gate_project` 下的 `outputs/亲子英语/<slug>/`（**整站打包源**），发布前必跑 `python tools/check_media.py <slug>`（`parent-english-html/scripts/check_media.py`）：该目录 HTML 不得引用 `.mp3`、所有音频须 `Opus` 单声道、视频须 H.264 / 720p 且 **单文件 ≤20MB**；发布前再跑 `--all` 全站体检（只读，未点名的课不许顺手修）。**逐文件 ffprobe 实测，生成过 ≠ 合格**；FAIL 不许进发布包。⚠ 这条管的是整站打包源，**不是**本层 `lessons/<slug>/html/`，别拿「不许 mp3」去卡单课页面的 `full.mp3`。 |
| **网盘里的媒体** | **未压缩原版**：定稿目录里带双语字幕 + 「关注我」片尾的翻译后 MP4，以及整视频音轨 `full.mp3`（128k / 44.1k / 单声道）+ PDF。**绝不能把 HTML 的压缩版传上网盘。** |
| **双网盘** | `upload_lesson.py --apply` 一条命令**同时传夸克 + 百度**。⚠ **百度 CLI 落在 `/apps/bdpan/油管亲子英语/<序号>.<主题>/` 应用沙箱，用户打开网盘看不到**；用户看的是 `/油管亲子英语/<序号>.<主题>/`。百度上传后**必须**再用 `baidu-netdisk` MCP 的 `file_copy` 搬过去 + `file_list` 回读，否则一律判 blocked。2026-11-08 用户实测：47–50 课日志全 3/3，根目录只到第 46 课。详见「百度上传成功判定」专节。 |
| **每课必须写来源** | HTML 页头 `srcbar` 写 `来源：YouTube @频道`，页脚写版权声明。`parent-english-html` 由 `series.json` 的 `by` 派生 → 本层 `fetch` 自动把 `by` 采好，`build` 提醒、`verify` 检查，漏写就终验 FAIL。 |
| **人工复核拼图必须置顶展示** | `qa` 产出的 `reports/frames_sheet.jpg` 是每课必看的人工闸门证据。用 `present_files` 交付时**排在第一位**（会自动打开预览）；一次只放「六件套」这 6 个、顺序固定，别塞中间产物（用户 2026-11-08 明确要求）。详见「交付展示：六件套」专节。 |
| **HTML 媒体必须压缩** | 本层单课页面 `lessons/<slug>/html/` 里的视频必须 **720p / H.264 / <= 20MB**（用户 2026-11-08 明确要求），音频必须是有损压缩：单课用 `full.mp3` 128k 单声道做时间码跳播，整站打包时再换 Opus 32k 分段。`pe.py build` / `verify` 的 HTML 体检用 ffprobe 实测 `html/` 下**所有**媒体（含未被引用的冗余文件），并检查媒体引用不得越出 `html/`（防 `../final.mp4`），超规格直接判 `blocked` / 终验 FAIL；阈值在 `config.yaml: html_video_max_mb / html_video_max_height / html_audio_max_kbps`，报告 `reports/media_audit.md`。**网盘三件套保留未压缩 `final.mp4`**，别把两者混用。 |
| **小红书文案字数硬闸门** | 标题每个 ≤20、正文 ≤1000（**Unicode 码点**，Python `len()` == 麦田 JS `[...s].length`），话题行不计入正文（麦田 `splitTopics` 拆分）。`pe.py xhs <no>` 单独体检；`build` 超限标 blocked、`verify` 判 FAIL、`publish` **直接拒绝出清单**。`maitian_prep.py` 也先过这道闸。口径必须与麦田 `lib/bundle.js` 一致，否则文案过不了下游。详见「文案字数闸门」专节。 |
| **发帖走麦田，最后一下人点** | 国内平台（小红书/抖音/B站/视频号）由麦田**只填写不发布**；用户明确选此方案（2026-11-17）。本机已装 `<MAITIAN_DIR>/`（中控 + 发布助手），`config.json` 里 `xhs/douyin` 在 `manual`。`maitian_prep.py <no> --cover <豆包3:4图>` 把一课组装成麦田工程（本地，**不启 Chrome、不上传、不填表**），再人工确认跑 `hub plan/run`。**绝不自作主张调 hub run / 点发布。** 详见「麦田发布链路」专节。 |
| **转录 / 复核零积分** | 一律本机 `faster-whisper`：`pe.py subs` 全链路只跑一次，疑点用本地 `small`/`medium` 或 `initial_prompt` 对数概率对局部窗口复核。**禁用 `AudioTranscribe` 等任何云端 / 付费 ASR**（用户 2026-11-14 重复提醒）。详见 `bilingual-subtitles` SKILL.md 顶部「零积分铁律」。 |
| **长静音 ≠ 无口播** | 整片转录出现 **>15s 连续空档**时，不许直接留白：必须对该区间切局部窗口，本机 medium 开/关 VAD 各跑一次，两边都确认无台词才放行。第 56 课实测 29.6s「静音」里漏了 6 句旁白（用户指出 1:09–1:32 无字幕）。`qa.py` 已加「疑似漏转」WARN；片尾 10–20s 的短反应也要以局部窗口词级为准（同课 `Whoa!` 提前 2s）。详见 `bilingual-subtitles` Pitfall 25。 |

> ⚠️ **百度日志不是成功证据**（2026-11-08 用户实测后定案）：`✓ 已新建上传 (fsid …)` /
> `OK [百度]` / `SKIP [百度]` / `FAIL [百度]` 一律只说明 `bdpan.exe` 把文件写进了
> `/apps/bdpan/` 应用沙箱。第 47–50 课日志全都是 3/3，用户可见的 `/油管亲子英语/`
> 却只更新到第 46 课。`pecore.summarize_upload()` 只统计「CLI 调用条数」，
> `verify_remote_check()` 才是唯一 gate。**别再把 fsid 当成功判据。**
>
> ⚠️ 百度「假 FAIL」只是日志异常（列表 API 偶发 `errno=-7`）：`FAIL [百度] … : 正在上传 …`
> 后面跟 `✓ 已新建上传 …` 时，`normalize_external_result()` 把它降级为 warning，
> 避免整步误判 failed；但这**仍不代表上传成功**，只是不因日志格式报错。

## 五条铁律

1. **不假成功**：某步没接通或产物不齐，状态只能是 `blocked` / `failed`，并打印精确待办。
   绝不在 `NOT_WIRED` 时标 `done`。子命令错误（含 MCP 的 `isError: true`）一律归一化成失败。
   **日志里的 `✓ 已新建上传` / `fsid` / `SKIP [百度]` 不算上传成功**，必须远端回读用户可见目录
   （写 `upload_bundle/remote_check.json`），否则 `upload` 标 `blocked`、`verify` 判 FAIL。
2. **外部副作用 opt-in**：`upload` 默认 dry-run（不写定稿目录、不联网盘），`--apply` 才交付 + 双传；
   `publish` 永远只出清单，不发帖；共享站上线仍走「先问后发」。
3. **QA 是闸门不是清单**：`approvals.subs` 为空时 `build` / `upload` 直接拒绝；
   `approvals.final` 为空、或终验报告不是 PASS 时，`publish` 直接拒绝。
   `approve` 会实读 `qa_report.md` / `verify_report.md` 确认 PASS，不靠状态、不靠口头确认。
4. **来源不许空**：`by` 为空或 HTML 里没有来源标注，终验判 FAIL。来源靠 `fetch` 自动采集，不靠人记。
5. **六件套优先展示**：产物一生成就跑 `deliver <no>` 拿固定顺序的 6 个路径，
   **一次 `present_files` 只放这 6 个**；QA 报告 / 手机截图 / 压缩视频 / manifest 等中间产物
   不许混进来，否则卡片被折叠成「查看所有产物 (N)」，用户得自己去翻。详见专节。

> 顺序说明：**上传排在终验之前**——「核对上传文件有没有问题」本来就要等文件先传完。
> 所以 `upload` 只卡字幕闸门与 build 完成，不依赖 final；final 只拦发帖。

## 日常怎么调用（说人话就行，不用记命令）

用户在 WorkBuddy 对话里说自然语言，本 skill 负责翻译成 `pe.py` 命令。
最稳的写法是带前缀 `@skill:parent-english-pipeline <话>`，避免被下游 4 个 skill 抢走意图。

| 用户说 | 对应动作 |
|---|---|
| 「做第49课，主题医生用具，链接 …」 | `new` → `fetch`（自动采来源）→ `cut --suggest`，**停下来等人选区间** |
| 「用第二个」/「12.0 到 134.0」 | `cut --keep` → `subs`（转录一次）→ 打印烧字幕待办 |
| 「字幕没问题」/「核对一下字幕」 | `qa` → 报告 + 抽帧拼图 → 人确认后 `approve --stage subs` |
| 「第49课到哪了」 | `status 49`（九步表 + 来源 + HTML 地址） |
| 「看看产物 / 成品呢 / 继续」 | `deliver <no> --json` → **一次 `present_files` 只放六件套**（顺序见专节，别混中间产物） |
| 「继续第49课」 | 读 `lesson.json` 找第一个非 done 的步骤，从那里接着跑（幂等） |
| 「来源补一下」 | `source 49 --url …`（或 `--by`） |
| 「传网盘」 | `upload 49` dry-run → 人确认 → `upload 49 --apply`（双网盘）→ **百度 MCP 搬移 + 回读写 `remote_check.json`** → 再 `upload 49 --apply` 解锁 blocked |
| 「文案字数过不过」 | `xhs <no>`（只读体检；标题≤20 / 正文≤1000，话题不计入） |
| 「可以发了」 | `verify` → 人确认 → `approve --stage final` → `publish`（只出清单，超字数会拒绝） |
| 「发给麦田 / 准备发布工程 / 用这张豆包图发」 | `maitian_prep.py <no> --cover <图路径>` → 本地工程 → 人跑 doctor / plan / run，最后自己点发布 |
| 「改了字幕，重跑」 | `qa` → 重新 approve → `build`；不重下视频、不重转录 |

**三次人工介入**（其余后台跑）：① 选素材 / 定剪辑区间 ② 扫拼图 + 逐句听辨后打勾
③ 看终验报告后放行发帖。② 的 `frames_sheet.jpg` 交付时**必须置顶展示**（见上方固定事实），
别让用户展开「查看所有产物」才能看。所有外部动作（写定稿目录、传双网盘、上线共享站）
都要用户明确说「可以 / 传吧」，不自动做。

**新开会话不用重复交代背景**：固定规范在用户级记忆，课的状态在
`lessons/NN-slug/lesson.json`，`status <no>` 一眼恢复进度。
命令行备用入口：skill 根目录的 `pe.cmd`（`pe.cmd status 49`），已封装 python 路径。

## 一课一档（唯一事实源）

固定根 = `config.yaml: project_root`（纯 ASCII，不随会话工作区变化，规避 ffmpeg 中文路径坑）。

```
ParentEnglish/lessons/46-halloween-games/
├── lesson.json            元数据 + by/源信息 + 9 步状态 + approvals
├── src.mp4                下载原件
├── src.info.json          yt-dlp --write-info-json 落的来源事实源（频道/原标题/视频ID）
├── cut.mp4                2 分钟剪辑成片（转录前必须定稿）
├── transcript.json        全链路唯一一次转录，词级时间戳
├── subtitle_manifest.csv  完整台词清单（一句一行）
├── subs.json              人工校对后的双语条目 ← 英文唯一事实源
├── final.mp4              带片尾成片（未压缩，网盘版）
├── subtitle_work/         txt/ srt_only/（SRT 绝不与 mp4 同目录同名）
├── html/                  index.html + audio/full.mp3 + video/（压缩版）+ img/
├── pdf/                   打印版
├── xhs.txt                小红书 / 抖音文案
├── upload_bundle/         三件套 + manifest.txt + mirror/（给上传脚本读）+ upload_log.txt
├── publish_checklist.txt  发布清单
└── reports/               qa_report.md / verify_report.md / frames_sheet.jpg
```

`subs.json` 格式（`[{start, end, en, cn, sentence_id?}, ...]`，秒，end 已 gap-fill）：
**下游 HTML 直接读它生成 part2 的 en/cuts，不要再跑 `ocr_subs.py` 去 OCR 自己烧的字幕**；
文案的 8 句也从它的完整清单里挑（对应 `bilingual-subtitles` Step 0.5）。

## 交付展示：六件套（用户 2026-11-08 明确要求）

用户在工作流里**最需要看的就是这 6 个**，顺序是用户给的，**不要重排、不要塞进折叠区**：

| # | 产物 | 相对路径 | 用户拿它做什么 |
|---|---|---|---|
| 1 | 字幕抽帧拼图 | `reports/frames_sheet.jpg` | 扫一眼字幕有没有裁切 / 折行 / 重影 |
| 2 | 翻译后成品 MP4 | `final.mp4` | 带双语字幕 + 片尾的网盘版成片 |
| 3 | 整视频 MP3 | `html/audio/full.mp3` | 配套音频 |
| 4 | 小红书 / 抖音文案 | `xhs.txt` | 发帖正文 |
| 5 | 打印版 PDF | `pdf/*.pdf` | 完整学习单 |
| 6 | 学习页 HTML | `html/index.html` | 手机端学习页（会自动开预览） |

**执行规则（硬性）**：

1. 每个阶段跑完、或用户说「看看产物 / 继续 / 成品呢」，先跑
   `%PY% %PE% deliver <no> --json`，把返回的 6 个路径**原序**传给**一次** `present_files`，
   `files` 数组里**只有这 6 个**。
2. 绝不把 QA 报告、手机截图拼图、压缩视频、manifest、upload_log、lesson.json、
   contact sheet 塞进同一次展示。要展示额外证据，另起一条消息、单独一次展示，
   且那次仍把六件套放最前。
3. 卡片超过一屏，UI 会把后面的收成「查看所有产物 (N)」——用户明确说不要去折叠里翻。
   **宁可少展示，也不要把六件套挤下去。**
4. `deliver` 缺项会打印「缺 <路径>」，先补齐再展示，不许拿别的文件凑数。
5. 回复正文里也要把这 6 个的路径 / 大小点名，别只丢一组卡片让用户猜哪个是哪个。

## 百度上传成功判定：远端回读 gate（2026-11-08 定案）

**根因**：`bdpan.exe` 是百度开放平台应用，只有 `/apps/bdpan/` 应用沙箱的写权限；
用户打开网盘看的是根目录 `/油管亲子英语/`。从第 47 课起改用 CLI 上传后，文件确实都传
成功了，但全落在沙箱里，用户看到的目录停在第 46 课（46 及之前是另一条有全盘权限的
通道传的）。日志越显示「3/3 全成功」，越容易误判。

**判定规则（硬性）**：

1. `pecore.summarize_upload()` 只报 CLI 调用条数，`baidu_verified` 恒为 False。
2. `upload --apply` 跑完日志后读 `upload_bundle/remote_check.json`：缺文件 /
   `verified != true` / 目录以 `/apps/` 开头 / 文件名或字节数对不上 →
   `upload` 标 `blocked` 并打印精确待办，**不标 done**。
3. `verify` 同样查这个文件，不通过就把 `[百度远端] …` 计进 problems → 报告 FAIL。
4. 夸克侧不受影响，仍按日志 `OK/SKIP` 统计。

**编排层每课必做的百度收尾**（用 `baidu-netdisk` MCP，零风险、可重复）：

```json
file_copy {"async":0,"ondup":"skip","filelist":"[{\"path\":\"/apps/bdpan/油管亲子英语/50.感恩节\",\"dest\":\"/油管亲子英语\",\"newname\":\"50.感恩节\"}]"}
```

然后 `file_list {"dir":"/油管亲子英语/50.感恩节","page":1}` 回读 3 个文件名 + `size`，
写进 `upload_bundle/remote_check.json`：

```json
{
  "verified": true,
  "checked_at": "2026-11-08 15:55:00",
  "channel": "baidu-netdisk MCP file_list",
  "baidu_visible": {
    "dir": "/油管亲子英语/50.感恩节",
    "files": {"50.感恩节.mp4": 39976242,
              "50.感恩节.mp3": 2109169,
              "50.感恩节.pdf": 244411}
  }
}
```

最后 `pe.py upload <no> --apply`（幂等）或 `pe.py verify <no>` 解锁。
**优先 `file_copy` 不要 `file_move`**：沙箱副本留着不影响，清理是可逆的额外动作。
另：根目录列表分页有短暂缓存，刚复制完用 `file_keyword_search` 或子目录 `file_list`
确认更可靠。

## 来源自动采集（`source` 命令）

`fetch` 下载时带 `--write-info-json`，落 `src.info.json`；`pecore.parse_source_info()` 从
`uploader_id` / `uploader` / `channel` 里优先取带 `@` 的 handle，映射成 `parent-english-html`
要求的 `by`（有 @ 带 @，没有就用频道显示名），同时存 `source_url` / `source_title` /
`source_video_id` / `source_channel_id`。`new --by` 因此**可不填**。

```bash
%PY% %PE% source 46                       # 查看 / 从已有 src.info.json 重读
%PY% %PE% source 46 --url <YouTube链接>   # 补抓（--dump-single-json，不下载视频）
%PY% %PE% source 46 --by "@channel"       # 手工素材兜底登记
```

## 命令

```bash
set PY="<PYTHON_EXE>"
set PE="<SKILLS_DIR>/parent-english-pipeline/scripts/pe.py"

%PY% %PE% new 46 --zh 万圣节游戏 --en "Halloween Games" --cat 节日文化
%PY% %PE% fetch 46 --url <YouTube 链接>    # 同时自动采集来源
%PY% %PE% cut 46 --suggest                 # 先给候选 2 分钟区间
%PY% %PE% cut 46 --keep 12.0 134.0        # 定稿剪辑，重编码保证时间轴从 0 起
%PY% %PE% subs 46                          # 转录一次 + 打印下游待办
%PY% %PE% qa 46                            # 自动检查 + 抽帧拼图 + 报告
%PY% %PE% approve 46 --stage subs          # 人扫完拼图/听辨后打勾
%PY% %PE% build 46                         # 抽 full.mp3 + 检查 HTML/PDF/文案 + 提醒写来源
%PY% %PE% upload 46                        # dry-run：归集三件套 + 造脚本镜像
%PY% %PE% upload 46 --apply                # 交付定稿目录 + 双传夸克/百度
%PY% %PE% verify 46                        # 核对 HTML / PDF / 上传文件 / 来源标注
%PY% %PE% approve 46 --stage final         # 终验 PASS 后才放行发帖
%PY% %PE% publish 46                       # 出发布清单，不发帖
%PY% %PE% status 46                        # 九步状态表（含来源与 HTML 地址）
%PY% %PE% deliver 46 --json                # 六件套绝对路径（展示顺序，供 present_files 直接用）
%PY% %PE% mark 46 subs --done              # 手工步骤完成后登记（会校验产物）
```

通用参数：`--root` 覆盖 project_root、`--force` 强制重跑、`--json` 机器可读输出。

## 九步与依赖

| 步 | 命令 | 依赖 / 闸门 | 本层自动做的事 |
|---|---|---|---|
| 1 | `new` | — | 建目录、写 lesson.json |
| 2 | `fetch` | source_url | yt-dlp 下载（代理 <PROXY>）+ `--write-info-json` **自动采集来源** |
| 3 | `cut` | src.mp4 | silencedetect 给候选区间、ffmpeg 精确裁剪、记时长 |
| 4 | `subs` | cut.mp4 | **只跑一次** faster-whisper → transcript.json；打印烧字幕待办 |
| 5 | `qa` | subs.json / final.mp4 | 宽度断言、孤儿屏、**中英按屏对应**、时间轴、覆盖率、片尾时长、抽帧拼图（**交付置顶展示**） |
| 6 | `build` | `approvals.subs` | 抽 full.mp3、HTML 资源/div/七 Part 检查、**ffprobe 实测 `html/` 媒体压缩（视频 ≤20MB / 720p / H.264、音频有损 ≤160kbps、引用不越界）→ `reports/media_audit.md`**、产物齐备、提醒写来源；不 PASS 标 `blocked`。整站打包源另跑 `check_media.py <slug>` |
| 7 | `upload` | `approvals.subs` + `build=done` | 三件套归集、交付定稿目录、造镜像、`--apply` 双传；**百度必须远端回读才标 done** |
| 8 | `verify` | 上传已完成 | 汇总大小/时长/资源、**查来源标注**、**复跑 `html/` 媒体压缩实测**、生成报告；整站打包源另跑 `check_media.py <slug>`；有问题则状态 `failed` |
| 9 | `publish` | `approvals.final` + 终验 PASS | 输出发布清单（标题/正文/置顶/视频路径） |

状态值：`pending` / `done` / `blocked` / `failed` / `skipped`。每步幂等：产物齐且 `done` 就 SKIP，
`--force` 才重跑。改了字幕只重跑 `qa` 及之后，不用重下视频。

## 人工介入只保留三处

① 选素材 + 定剪辑区间（审美判断）② 字幕 QA 看拼图 + 逐句听辨（用户硬要求）
③ 终验 + 复制文案发帖（平台动作）。其余后台跑。

## 未接通时怎么继续

`subs` / `build` 的创作部分由下游 skill 完成后，用 `mark <no> <stage> --done` 登记。
`mark` 会先校验该步的期望产物确实存在，否则拒绝。这样状态表始终可信。

## 文案字数闸门（2026-11-17 用户要求）

用户原话：「小红书文案完善一下，正文不能超 1000 字，标题不能超 20 字」。
脚本 `scripts/xhs_check.py`，口径**逐字对齐麦田** `mdldm-maitian-publisher/lib/bundle.js`：

- 字数 = Unicode 码点（`[...s].length` == Python `len(s)`）；emoji 按 1 个码点。
- 标题：每个候选 1..20；**全部**候选都得合规（不是只挑一个短的）。
- 正文：1..1000，**话题行不计入**（麦田 `splitTopics` 把正文最后一行全是 `#` 的拆进 topics）。
- 话题 ≤10；置顶评论 3 条。
- 块头只认白名单 `【主题/推荐标题/标题备选/标题/正文笔记/正文/置顶评论…】`；
  正文里的「茴【演员】」「茴【年兽】」是内容，**不能**当块头（早期发布台踩过这个坑，把正文切碎）。
- 兼容两套标签：`【推荐标题】/【正文笔记】/【置顶评论】` 与
  `【标题备选】/【正文】/【置顶评论备选】`；话题也认 52 课的 `话题：#a #b` 写法并提示改成独立 `#` 行。
- **2026-11-18 新版格式**：标题 1 条（`地道油管亲子英语 | <主题名>`，半角 `|`）、
  开场 1–2 句、5 句英文+中文、5 个 tag，**无置顶评论**。校验器据此放宽：
  标题 ≥1 即可（不再强制 3 条），置顶评论可选（给了就 3 条）。新旧格式都过。

三处接入（`scripts/pe.py`）：`build` 超限→blocked + 精确待办、`verify` 超限→报告 FAIL、
`publish` **直接 PipelineError 拒绝出清单**（免得不合格文案流进发布链路）。

```bash
%PY% %PE% xhs 53                       # 单独体检，只读，不改状态
%PY% -B %SKILL%/scripts/xhs_check.py --dir "%PROJ%/lessons"   # 全量体检
```

2026-11-17 全量体检结果：50/51/56 PASS；52 正文 1151 超 151；53 标题 27 + 正文 1529；
54 标题 21/21 + 正文 1037；55 标题 22/23；57 标题 29/22；58 标题 28/23。
**这些是文案本身的问题，闸门只报不自动改**——创作由 `video-english-xhs` 重出或人工精简，
改完重跑 `xhs`。未点名的课不许顺手改。

## 麦田发布链路（2026-11-17 用户选定方案）

用户选了「浏览器自动填表 + 自己改完点发布」，不是剪贴板发布台（那个留作轻量备用，
文件在 `<PROJECT_ROOT>/publish_desk.html`）。

三者分工（本机 `<MAITIAN_DIR>/` 已装好，别重装）：

| 谁 | 做什么 |
|---|---|
| 本层 `maitian_prep.py` | 把一课组装成麦田工程：文案→`发布素材.md`、`final.mp4`→`成片.mp4`（**faststart**，moov 前置，否则小红书报「无视频流信息」）、豆包 3:4 图→`cover-3x4/4x3/16x9`、SRT→`字幕.srt`、调 make-publish + validate |
| 麦田发布助手（插件仓 `mdldm-maitian-publisher`） | 打开上传页、传视频/封面、填文案、设定时 |
| 麦田中控 `mdldm-maitian` | 分批、防重、等你点发布、取链接、采数据；`config.json` 里 `xhs/douyin` 在 `manual` |

```bash
# 1) 准备工程（本地，零外部副作用；--cover 传用户发来的豆包 3:4 图，缺省用 poster.jpg）
%PY% -B %SKILL%/scripts/maitian_prep.py <no> --cover "<豆包图路径>"
#    dry-run 先看：加 --dry-run；默认输出 <MAITIAN_DIR>/发布工程/<序号>.<主题>/

# 2) 用户人工（不得代劳）：2-login.bat 登录小红书/抖音 → 关掉 → 3-doctor.bat 验登录态
# 3) 用户确认后才跑（外部副作用，opt-in）：
#    cd /d <MAITIAN_HUB>
#    node src/hub.mjs plan "<工程目录>"
#    node src/hub.mjs run  "<工程目录>"     ← 自动传视频/图片、填文案，填好就停
# 4) 用户到创作中心检查后，自己点「发布」
```

**平台规则（2026-11-21 用户改版，后续所有课照此）**：

| 平台 | 标题 / 正文 | 话题 / 标签 | 分区 / 定时 |
|---|---|---|---|
| B站 | 与小红书、抖音**完全一致**：`地道油管亲子英语 \| <主题名>` + 同一段开场和 5 句，不再写来源署名 | 5 个基础 tag，不含平台活动 tag | 分区固定 **亲子**（适配器默认，`p.category` 可覆盖）；创作声明仍由用户点发布前确认 |
| 小红书 | 同上 | 5 个基础 tag + `#RED11月精选作者评选`（共 6） | 支持定时 |
| 抖音 | 同上 | 5 个基础 tag + `#抖音精选app征稿中`（共 6；`bundle.js` 的 `maxTopics` 已放宽到 6） | 支持定时；自动选合集 `亲子英语口语·100个场景合集`（`p.collection` 可覆盖）、保存权限显式勾「允许」（`p.savePermission` 可覆盖） |

- 基础 tag 固定 `#亲子英语 #英语启蒙 #英语口语 #双语育儿 #<主题名>`，
  **「幼儿英语启蒙」已作废**，老课文案不批量回改，只有用户点名的课才重出。
- 平台活动 tag 由 `maitian_prep.py` 按平台追加，**不写进 `xhs.txt`**，所以 `xhs_check.py` 的 5 tag 口径不变。
- 定时发布：`maitian_prep.py <no> --schedule "YYYY-MM-DD HH:mm"` 会写进 `发布素材.md` 头部；
  也可手工在 md 头部加 `> 定时发布：...`。约束：**晚于当前 2 小时以上、14 天以内**，
  三个适配器都会打开定时开关并填时间，填完仍需用户核对并点发布。

**硬规矩**：`maitian_prep.py` 只写本地工程目录，**不启 Chrome、不连平台、不调 hub plan/run**；
`hub run` 与最终「发布」都要用户明确点头。封面由用户用豆包做，不让 AI 出图。
已对麦田源码做一处 Windows 兼容修复（详见 11-17 日志）：`tools/make-publish.mjs` 与
`tools/validate.mjs` 的 `relative()` 结果统一成正斜杠，否则 `封面/cover-*.png` 匹配不上、
covers 永远是空、`validate` 误报找不到封面。升级麦田后若复发，重打这个补丁。

## 扩展点

- 接 `bilingual-subtitles`：`burn.py` 沉淀后，在 `subs` 步直接调用，省掉手工登记。
- 接 `parent-english-html`：把 `build` 改成读 `subs.json` 直接生成 part2 与 `series.json.by`，跳过 `ocr_subs.py`。
- 上传脚本镜像已内置（`upload_bundle/mirror/`），不需要往旧项目 `outputs/` 里塞文件。
