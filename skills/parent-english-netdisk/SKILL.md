---
name: parent-english-netdisk
description: 把亲子英语某课的定稿 MP4（未压缩翻译后成片）、PDF、整视频 MP3 同时上传到夸克和百度网盘《油管亲子英语》下「序号.主题」子文件夹。当用户说「上传第N课到网盘 / 把XX课的视频PDF音频传到夸克或百度 / 同步网盘资料」时使用。Upload a lesson's final MP4/PDF/full.mp3 to BOTH Quark and Baidu net disks.
version: 1.1.0
---

# 亲子英语 → 夸克 + 百度 双网盘上传

`upload_lesson.py --no N --project <项目根> --apply` **一条命令同时传夸克和百度**，
把三件套（定稿 MP4、整视频 MP3、PDF）归到两个网盘的《油管亲子英语》/`<序号>.<主题>/`。

## 前置（一次性）
- 夸克：`quark-nd-mcp` 二进制 + Cookie，默认 `<TOOLS_DIR>/quark-nd-mcp/quark-nd-mcp.exe`
  与 `<QUARK_CONFIG>`（**须用补丁版二进制**，sha1 回调 bug 见用户记忆）。
- 百度：本机 `bdpan` CLI，已装在 `<BDPAN_EXE>`。
  `bdpan` 是 Go CLI，不读系统代理，`bdpan_env()` 会显式注入 `<PROXY>`。
  百度远端落在 `/apps/bdpan/油管亲子英语/<序号>.<主题>/`，中文目录名是支持的。
- ⚠️ **WorkBuddy 的 `baidu-netdisk` 连接器与 bdpan CLI 是两条独立通道**。
  连接器状态 `unavailable` 不影响本 skill：47 / 48 课都是在连接器不可用时，
  由本脚本通过 bdpan CLI 成功双传的。不要因为连接器状态就判定「百度不能传」。

## 网盘目录约定（用户已有结构）
《油管亲子英语》/ `<序号>.<主题>` / 内含：`<序号>.<主题>.mp4` + `.pdf` + `.mp3`
例：`48.老师/` 下是 `48.老师.mp4` / `48.老师.mp3` / `48.老师.pdf`。
百度实际路径带 `/apps/bdpan/` 前缀，夸克是 `/油管亲子英语/`，脚本已各自处理。

## 已知坑：百度「假 FAIL」（2026-11-06，48 课实测）
百度列表/回读 API 偶发 `errno=-7` 内部错误（连 `/apps/bdpan/` 这种纯英文路径都列不了），
会让 `baidu_upload_file()` 把**已经成功上传**的文件打印成 `FAIL [百度] …`。
判据看**上传响应里的 `✓ 已新建上传` / `"status": "ok"` / fsid**，不要看脚本汇总的 FAIL 字样。
48 课三个文件都返回了真实 fsid（示例值已脱敏），
文件确实落地。调用方（如 `parent-english-pipeline`）必须按这个口径归一化，否则会误报失败。

## 命名规则（关键：绝不新建重复文件夹）
目标子文件夹 = **「序号.」前缀智能匹配**：
1. `list_files("/油管亲子英语")` 列出子文件夹；
2. 找**以 `<序号>.` 开头**的文件夹（如已有 `46.万圣节游戏`，序号 46 → 命中）；
3. 命中则**复用**（不新建），未命中才 `create_folder("/油管亲子英语/<序号>.<zh>")`。

这样能对齐用户手建的中文名（如「万圣节游戏」比系列 zh「万圣节」多了「游戏」），不会重复建。

## 源文件定位（双轨：HTML 压缩版 ≠ 网盘原版）
给定课程号 N（如 46），脚本**按目录扫描 + 前缀/特征匹配**（不强制特定文件名，适配真实命名）：
- 从 `<项目根>/tools/series.json` 的 `lessons[]` 取 `n==N` 的条目 → `slug`、`zh`（也兼容按 slug 匹配）；
- **MP4：优先 `<DELIVERY_DIR>/<N>.<主题>.mp4`** —— 这是带双语字幕 + 「关注我」片尾的
  **未压缩翻译后定稿原片**（如 `47.警察.mp4` 163 MB / `48.老师.mp4` 49 MB），网盘要的就是它。
  找不到才回退 `<项目根>/outputs/亲子英语/<slug>/video/` 下任意 `.mp4`。
  ⚠️ **绝不要把 HTML 整站用的 720p / crf30 压缩版传上网盘**，那是给网页在线播用的。
- PDF：`<项目根>/outputs/亲子英语/全套PDF/` 下找 `<N>.` 开头的 `.pdf`（可能带 `(1)` 等后缀，全收）；
- MP3（整视频「音频」）：`<项目根>/outputs/亲子英语/<slug>/audio/` 下按优先级找 ——
  ① `full.mp3` → ② `<N>.<...>.mp3` → ③ 任意非 `segNN` 段的 `.mp3`。是**整视频音轨**（128k / 44.1k / 单声道），
  不是分段精听音频；`seg01.ogg`/`full.ogg` 等网站优化用的 Opus **不上传**。
- 缺哪类文件，脚本 `WARN` 跳过该类，不中断其余上传。

## 调用方式
`scripts/upload_lesson.py` 一条命令**双网盘**：夸克走 quark-nd-mcp JSON-RPC，百度走 bdpan CLI。
```bash
python scripts/upload_lesson.py --no 46 --project "<CURRENT_PROJECT>" --apply
```
参数：
- `--no`：课程号（"46"）
- `--project`：parent-english-html 项目根（含 `outputs/` 与 `tools/series.json`）【必填】
- `--root`：父文件夹名，默认「油管亲子英语」（两个网盘共用此名）
- `--exe` / `--cfg`：可选，覆盖 quark-nd-mcp 二进制与 config 路径
- `--apply`：**默认 dry-run**（只预览，百度侧不连网、夸克侧只 list）；加 `--apply` 才真实上传两个网盘

脚本会：读 series → 收集三件套 → 夸克前缀匹配复用/新建 → 逐个 upload_file →
**再跑 `baidu_upload()`** 建目录 + 按 `<序号>.<主题>.<ext>` 改名上传 + 大小一致则 SKIP（幂等）。
网盘文件名统一为 `<序号>.<主题>.mp4/.mp3/.pdf`。

## 安全红线
- 夸克侧：同名文件大小不一致时会先 `delete` 再重传（脚本第 399 行），**只删该课文件夹内的同名文件**；
  不做 `move` / `rename` / 跨目录删除。百度侧只 `mkdir` + `upload --overwrite`。
- 覆盖同名文件前先 `--dry-run` 预览；外部副作用默认 opt-in（`--apply`）。
- Cookie 是用户私密凭据，只存本地 `<QUARK_CONFIG>`，**不**进任何 Git 仓库、不打印到日志外发。

## 常见问题
- 前缀匹配不到？确认 `--root` 下的文件夹确实以 `NN.` 开头；若课放在更深目录，先 `list_files` 看实际路径。
- 上传失败（401/鉴权）？Cookie 过期，让用户重新从 pan.quark.cn 抓 Cookie 覆盖 config.json 后重试。
- 百度输出 `FAIL` 但网页端能看到文件？**假 FAIL**，见上文「已知坑」；判据是 `✓ 已新建上传` / fsid，不是 FAIL 字样。
  也可等一会儿重跑 `--apply`，`baidu_ls()` 会按「同名 + 大小一致」自动 SKIP。
- MP3 缺失？该课还没抽 full.mp3：用 `ffmpeg -i <src>.mp4 -vn -c:a libmp3lame -b:a 128k -ar 44100 <slug>/audio/full.mp3` 先抽，再上传。
