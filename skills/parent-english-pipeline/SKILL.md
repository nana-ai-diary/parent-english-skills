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
| **网盘里的媒体** | **未压缩原版**：定稿目录里带双语字幕 + 「关注我」片尾的翻译后 MP4，以及整视频音轨 `full.mp3`（128k / 44.1k / 单声道）+ PDF。**绝不能把 HTML 的压缩版传上网盘。** |
| **双网盘** | `upload_lesson.py --apply` 一条命令**同时传夸克 + 百度**（百度走本机 `bdpan.exe` CLI，落在 `/apps/bdpan/油管亲子英语/<序号>.<主题>/`）。WorkBuddy 的 `baidu-netdisk` 连接器是另一条通道，它 `unavailable` 不影响上传。47 / 48 课已实测双传成功。 |
| **每课必须写来源** | HTML 页头 `srcbar` 写 `来源：YouTube @频道`，页脚写版权声明。`parent-english-html` 由 `series.json` 的 `by` 派生 → 本层 `fetch` 自动把 `by` 采好，`build` 提醒、`verify` 检查，漏写就终验 FAIL。 |

> ⚠️ 百度「假 FAIL」：百度列表 API 偶发 `errno=-7`，`upload_lesson.py` 会把**已成功上传**的文件
> 打印成 `FAIL [百度] …`。判据是输出里的 `✓ 已新建上传 (fsid …)` / `"status": "ok"`，
> 不是 FAIL 字样。`pecore.normalize_external_result()` 已按此口径归一化，别改回无脑见 FAIL 就判失败。

## 四条铁律

1. **不假成功**：某步没接通或产物不齐，状态只能是 `blocked` / `failed`，并打印精确待办。
   绝不在 `NOT_WIRED` 时标 `done`。子命令错误（含 MCP 的 `isError: true`）一律归一化成失败。
2. **外部副作用 opt-in**：`upload` 默认 dry-run（不写定稿目录、不联网盘），`--apply` 才交付 + 双传；
   `publish` 永远只出清单，不发帖；共享站上线仍走「先问后发」。
3. **QA 是闸门不是清单**：`approvals.subs` 为空时 `build` / `upload` 直接拒绝；
   `approvals.final` 为空、或终验报告不是 PASS 时，`publish` 直接拒绝。
   `approve` 会实读 `qa_report.md` / `verify_report.md` 确认 PASS，不靠状态、不靠口头确认。
4. **来源不许空**：`by` 为空或 HTML 里没有来源标注，终验判 FAIL。来源靠 `fetch` 自动采集，不靠人记。

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
| 「继续第49课」 | 读 `lesson.json` 找第一个非 done 的步骤，从那里接着跑（幂等） |
| 「来源补一下」 | `source 49 --url …`（或 `--by`） |
| 「传网盘」 | `upload 49` 先 dry-run → 人确认 → `upload 49 --apply`（双网盘） |
| 「可以发了」 | `verify` → 人确认 → `approve --stage final` → `publish`（只出清单） |
| 「改了字幕，重跑」 | `qa` → 重新 approve → `build`；不重下视频、不重转录 |

**三次人工介入**（其余后台跑）：① 选素材 / 定剪辑区间 ② 扫拼图 + 逐句听辨后打勾
③ 看终验报告后放行发帖。所有外部动作（写定稿目录、传双网盘、上线共享站）都要用户明确说
「可以 / 传吧」，不自动做。

**新开会话不用重复交代背景**：固定规范在用户级记忆，课的状态在
`lessons/NN-slug/lesson.json`，`status <no>` 一眼恢复进度。
命令行备用入口：skill 根目录的 `pe.cmd`（`pe.cmd status 49`），已封装 python 路径。

## 一课一档（唯一事实源）

固定根 = `config.yaml: project_root`（纯 ASCII，不随会话工作区变化，规避 ffmpeg 中文路径坑）。

```
<PROJECT_ROOT>/lessons/46-halloween-games/
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
| 5 | `qa` | subs.json / final.mp4 | 宽度断言、孤儿屏、时间轴、覆盖率、片尾时长、抽帧拼图 |
| 6 | `build` | `approvals.subs` | 抽 full.mp3、HTML 资源/七 Part 检查、产物齐备、**提醒写来源** |
| 7 | `upload` | `approvals.subs` + `build=done` | 三件套归集、**交付到定稿目录**、造脚本镜像、`--apply` 双传夸克+百度 |
| 8 | `verify` | 上传已完成 | 汇总大小/时长/资源、**查来源标注**、生成报告；有问题则状态 `failed` |
| 9 | `publish` | `approvals.final` + 终验 PASS | 输出发布清单（标题/正文/置顶/视频路径） |

状态值：`pending` / `done` / `blocked` / `failed` / `skipped`。每步幂等：产物齐且 `done` 就 SKIP，
`--force` 才重跑。改了字幕只重跑 `qa` 及之后，不用重下视频。

## 人工介入只保留三处

① 选素材 + 定剪辑区间（审美判断）② 字幕 QA 看拼图 + 逐句听辨（用户硬要求）
③ 终验 + 复制文案发帖（平台动作）。其余后台跑。

## 未接通时怎么继续

`subs` / `build` 的创作部分由下游 skill 完成后，用 `mark <no> <stage> --done` 登记。
`mark` 会先校验该步的期望产物确实存在，否则拒绝。这样状态表始终可信。

## 扩展点

- 接 `bilingual-subtitles`：`burn.py` 沉淀后，在 `subs` 步直接调用，省掉手工登记。
- 接 `parent-english-html`：把 `build` 改成读 `subs.json` 直接生成 part2 与 `series.json.by`，跳过 `ocr_subs.py`。
- 上传脚本镜像已内置（`upload_bundle/mirror/`），不需要往旧项目 `outputs/` 里塞文件。
