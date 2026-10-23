---
name: video-english-xhs
description: 从视频中提取核心英语词汇和实用句型，生成小红书/抖音视频配文和评论区置顶信息，并自动创建飞书文档整理完整笔记。当用户发送视频并要求提取英语学习内容、生成抖音帖子、整理视频英语笔记、做飞书文档时使用。Extract core English vocabulary and practical sentences from videos, generate Xiaohongshu/Douyin post captions and pinned comments, and auto-create Feishu docs with complete study notes. Use when extracting English learning content from videos or creating social media posts.
version: 5.2.0
---

# 视频英语 → 抖音配文 + 置顶评论

收到视频后，严格按以下流程执行。直接产出结果，不要反复确认。

## Step 0: 拿到视频（三种来源）

**A. 飞书文档里内嵌了视频**（最常见：用户发一个 `my.feishu.cn/docx/xxx` 链接说"视频在文档里"）：

```bash
export PATH="/usr/bin:/bin:$PATH"   # Git Bash 常缺 coreutils，先补 PATH
# 1. 取文档内容，找到 <figure> 里的 token
lark-cli docs +fetch --doc "<文档URL或token>" --doc-format markdown --detail simple --as user
#   回显里形如：<figure view-type="Preview"><source name="xx.mp4" mime="video/mp4" token="BOBDbHgG..."/></figure>

# 2. 下载（148MB / 2 分钟视频实测约 10 秒）
lark-cli docs +media-download --token "<上面的token>" --type media --output "<绝对路径>.mp4" --as user
```

**B. 用户直接给本地文件**：跳过本步。

**C. YouTube 链接**：走 `youtube-download` skill。

> 拿到的视频先用 ffprobe 看时长，决定后面要不要切片：
> `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 <file>`

## Step 1: 转录视频

> **先查有没有现成的转录**：同一支视频若先用 `bilingual-subtitles` 做过双语字幕，
> 工作区（如 `xxxx_work/transcript.json`）已有一份 **medium 模型 + 词级时间戳**的结果，
> 直接复用即可，不必再跑一遍推理（medium 全片约 1m20s）。
> 复用时确认 JSON 是 `{segments:[{start,end,text,words}]}` 结构；`words` 若字段名是
> `w/s/e`（自定义导出格式），取值要用 `w["w"] / w["s"] / w["e"]`，不是 `word/start/end`。

```bash
# 使用专用虚拟环境的 Python（依赖已隔离安装，勿用全局 python）
"~/.workbuddy/binaries/python/envs/parent-english/Scripts/python.exe" "{SKILL_DIR}/scripts/transcribe.py" "视频路径"
```

> ⚠️ **不要用 `~/.workbuddy/binaries/python/versions/3.13.12/python.exe` 再 pip install faster-whisper**——
> `envs/parent-english` 里已经装好了（Scripts 下有 ct2-* 即为证），装到别处属于污染环境。
> 需要词级时间戳时用 `word_timestamps=True`，模型 `small` 足够（2 分钟音频 CPU 约 100 秒）。
> 首次下载模型走 `HF_ENDPOINT=https://hf-mirror.com` + 代理 7890。

- 若提示找不到模块，说明依赖未安装，先确认该 venv 存在，不要改用全局 pip 安装

- 输出 JSON：`{ text, segments, language }`
- 如果视频较长（>5min），转录后聚焦与主题相关的核心片段
- 如遇转录失败，检查 faster-whisper 模型是否已下载到 `~/.cache/whisper_{model}_ct2/`

## Step 2: 校验转录结果 + 选句子

### 先校验转录准确性

faster-whisper 经常出现上下文错误（如 "red leaves" 应为 "reed leaves"、"zongzi" 应为 "rice dumplings"）。在使用转录结果之前：

- 根据视频主题和常识，检查转录中的明显错误
- 常见错误类型：同音词混淆（red/reed、corn/cone）、外来词误听、专业术语偏差
- 发现明显错误时，用上下文中正确的词替换
- 如果不确定某句转录是否正确，直接跳过不用

### 再从校验后的文本中选句子（8句左右）

- 直接从 segments 中复制原文句子，不做任何修改
- 不要"优化"英文表达，不要替换词汇，不要缩短或合并句子
- 即使转录中有小瑕疵（如 whisper 识别偏差），也使用转录输出原文
- 如果某句转录质量太差无法使用，直接跳过，不要自己改写

### 选句标准（8句左右）

- 优先选：简单短句、互动类指令、鼓励类表达、日常高频口语
- 必须选：家长和孩子互动时真的会说出口的句子
- 文化背景句可以保留：传统节日、习俗类视频中，介绍文化的句子适合亲子共学，可选1-2句
- 不要选：复杂烹饪指令、纯技术性描述等不适合对小朋友说的话
- 关键词覆盖：视频主题的核心词（如食物名、物品名的英文）必须在选出的句子中至少出现一次。用视频原文中实际使用的词，不要自己造词
- 场景覆盖：尽量覆盖视频中的不同环节/动作（如准备、操作、互动、收尾），让句子串起完整的场景体验

### 中文翻译

- 每句英文配一句中文翻译，紧跟在英文下方，单独一行
- 意译为主，语气自然口语化，像在跟小朋友说话
- 不要逐字直译

## Step 3: 写中文包装文案

**只有以下部分需要自己撰写（需要去AI味）：**
- 标题
- 开头 Hook
- 过渡句
- 点评句
- CTA（茴【关键词】）
- 置顶评论

**英文句子和中文翻译不需要去AI味，保持 Step 2 的原文。**

### 标题
- 固定前缀"地道亲子英语｜"，后面跟场景描述，总长度不超过20字
- 参考：荡秋千别只会说 Go! / 剪指甲别只会说 Don't move / 宝宝洗脸每天都能用

### Hook（开头）
- 必须制造情绪波动：好奇、震惊、共鸣、FOMO、反常识
- 每次变换风格，不要连续用同一种
- Hook 内容必须与视频实际内容相关，不要编造视频中没有的场景或人物
- 自检：这句话能不能让人产生"咦？"的反应？

**Hook 风格参考（混合使用）：**

反差挑战型：端午节包粽子只会说 make zongzi？/ 荡秋千别只会喊 Go Go Go！/ 剪指甲别只会说 Don't move
震惊/反常识型：这5句话我居然用了3年才发现！/ 原来"自己荡"用英语根本不是 swing by yourself
FOMO型：外网妈妈圈都在用的亲子英语，国内几乎没人教 / 刷到就是赚到！这几句英语我后悔没早点知道
共鸣痛点型：每次想说英语但话到嘴边又变成中文… / 我英语不好，但这几句我能说得出口
成果/证据型：我家2岁娃现在会自己说 Hold on tight 了

### 点评句
- 点出选出的句子中哪些表达特别地道或容易想不到
- 提到的词/表达必须出现在选出的英文句子中，不要提到视频场景无关的词

### 关键词
- 从视频主题提取2-4字核心词，用于茴【】互动
- 如：粽子、秋千、剪指甲、洗澡、刷牙

## Step 4: 组装输出

严格按以下版式输出。标题和置顶评论各给3个备选，正文笔记只给1版。

```
【主题】
地道亲子英语｜XXX

【推荐标题】
1. 地道亲子英语｜[标题A，20字以内]
2. 地道亲子英语｜[标题B，20字以内]
3. 地道亲子英语｜[标题C，20字以内]

【正文笔记】

[开头 Hook]

[过渡句]

1. [视频原文英文句子，不做任何修改]
[中文翻译]

2. [视频原文英文句子，不做任何修改]
[中文翻译]

...（共8句左右）

[点评句]

想看完整版，茴【[关键词]】
关注❤️收藏，每天一个地道亲子英语场景！

[5个话题标签]

【置顶评论】
1. [备选A]
2. [备选B]
3. [备选C]
```

### 标题备选要求
- 3个标题风格不同：一个反差挑战型、一个共鸣/痛点型、一个简洁直给型
- 每个都带固定前缀"地道亲子英语｜"，总长度≤20字

### 置顶评论备选要求
- 都用"茴【关键词】"互动
- 3个风格略有不同：可以有直接版、预告版、提问版等变化
- 基本结构：引导用户评论关键词 + 预告后续内容

## Step 5: 质量检查

输出前逐项检查，不合格就改：
1. 每句英文是否和视频转录原文完全一致？（逐字对比）
2. 3个标题是否都≤20字？风格是否各不相同？
3. 正文是否≤1000字？
4. 点评中提到的词是否都出现在选出的英文句子里？
5. 视频核心词（场景名/食物名的英文）是否在选句中至少出现一次？
6. Hook 内容是否与视频实际内容相关？（不要编造视频中没有的人或场景）
7. Hook 风格是否和上次不同？
8. 3个置顶评论是否都包含茴【关键词】？
9. 全文是否不含平台敏感词（私信我、发你、给你、免费、领取等引流/营销词）？

## 禁止事项

- 绝对不要修改视频转录出的英文句子
- 不要自己造英文句子或替换英文词汇
- 不要在中文翻译里加英文注释
- 不要用"让我们""接下来"等 AI 味过渡语
- 不要出现 markdown 格式符号（#, -, *, >）
- 不要在帖子中出现文件路径、工具名、转录相关字眼
- 不要在句子列表中加 emoji
- 不要在 Hook 中编造与视频内容无关的场景或人物

### 平台敏感词（小红书/抖音限流词，绝对不能出现）

- 引流类："私信我""私我""DM""戳我""加我""加V""加微信""公众号"
- 资料类："发你资料""领取资料包""免费送""资料包""课件""电子版""完整版领取"
- 营销类："0元""免费""白嫖""福利""限时""秒杀""下单""购买链接"
- 承诺类："包教包会""保证""一定学会""必看"

替代方案：用"茴【关键词】"引导评论互动即可，不要在文案中承诺发送任何资料。置顶评论中说"我后面整理成：词汇 + 常用句 + 亲子对话版，方便你直接用"是可以的（暗示后续会发，但不直接承诺"发你""私信领"）。

## 去AI味（仅限中文包装文案）

### 禁止的AI痕迹
- 填充短语："这几个表达""值得一提""确保""展示"
- 公式化结构：三段式排列、整齐的平行句
- 宣传腔："超实用""必备""核心""关键"
- 模糊归因："很多家长发现""据说""专家表示"

### 增加人味
- 第一人称真实经历
- 具体细节和画面感
- 网络用语和口语："贼好用""说实话""哈哈""老母亲"
- 长短句交替，打破整齐节奏
- 承认不完美
- 适当用昵称："宝妈们""姐妹们"

## 输出方式

保存为 `.txt` 文件，文件名：`xhs_[视频主题关键词].txt`。
文件内容按【主题】【推荐标题】【正文笔记】【置顶评论】四个板块排列。
同时直接展示给用户。

## Step 6: 创建飞书文档（需用户明确要求 / opt-in）

> 安装时加固说明：原 skill 要求"输出配文后自动创建飞书文档"，属于未授权的外部写入动作。
> 现改为：**默认只输出配文，不创建任何飞书文档**。只有在用户明确说"建飞书文档"时才继续，
> 且必须确认 lark-cli 已在 `~\.workbuddy\skills\parent-english.config.yaml`
> 的 `lark_cli` 字段中配置（值为空则跳过并说明原因）。

用户明确要求后，才创建飞书文档整理完整学习笔记。

### 6.0 前置：确认 lark-cli 版本 ≥ 1.0.96（否则颜色全丢）

```bash
lark-cli --version          # < 1.0.96 必须升级
lark-cli update --check --json   # 查最新版本
```

**⚠️ `lark-cli update` 对本机这种 shim 安装无效**：`--check` 会返回 `"auto_update": false`，
`update` 命令只是打印 GitHub Release URL，不会下载，表现为**长时间挂起无输出**（实测两次各卡 8 分钟）。
另外它默认走 `HTTPS_PROXY=127.0.0.1:52171`（WorkBuddy 沙箱代理），访问 GitHub 不通——这也是卡住的原因。

**正确的手动升级方式**（实测成功）：

```bash
# 1. 下载 Windows 版（14.7MB，走真实外网代理 7890 = Clash Verge）
HTTPS_PROXY=http://127.0.0.1:7890 python -c "
import urllib.request, zipfile, hashlib
url='https://github.com/larksuite/cli/releases/download/v1.0.96/lark-cli-1.0.96-windows-amd64.zip'
urllib.request.urlretrieve_ = None
req=urllib.request.Request(url, headers={'User-Agent':'curl/8'})
open('lark-new.zip','wb').write(urllib.request.urlopen(req, timeout=600).read())
zipfile.ZipFile('lark-new.zip').extract('lark-cli.exe', 'lark-new')
"
# 2. 备份并替换（替换前先杀掉所有 lark 进程）
#    备份：~\lark-cli-home\bin\ext\lark-cli-core-windows-amd64.exe
#          → 同目录 .bak-v45
#    复制：lark-new\lark-cli.exe  →  lark-cli-core-windows-amd64.exe
# 3. 验证
lark-cli --version   # → 1.0.96
```

下载前务必核对 SHA256 与 `https://github.com/larksuite/cli/releases/download/v1.0.96/checksums.txt` 一致
（1.0.96 windows-amd64.zip = `efd31a894c8b427d209727cb9e140a8b62c7955f404a6e7004e623fc687d42fa`）。

### 6.1 截取封面图

用 ffmpeg 从视频截取一张有代表性的画面作为封面（优先取前3秒内有主题相关的帧）：

```bash
ffmpeg -ss 1 -i "视频路径" -vframes 1 -q:v 2 "输出路径/cover.jpg" -y
```

### 6.2 创建文档

> 实践验证（2026-09-24）：`docs +create --api-version v2` **必须**带 `--content`，
> 单独传 `--title` 会报 `--content is required`；`--markdown` 不是 v2 create 的有效参数。
> 建好空文档后，先 `+media-insert` 插封面（会落在文档最前），再 `append` 正文，顺序最省事。

用 lark-cli 创建飞书文档，文档名以【主题】命名。注意 lark-cli 要求相对路径：

```bash
# 写标题到临时文件
echo '<title>主题名</title>' > doc_title.xml
# 必须在文件所在目录执行，用 @文件名 传入内容
cd "工作目录"
"%LARK_CLI%（从 config.yaml 的 lark_cli 字段读取，未配置则跳过）" docs +create --api-version v2 --content "@doc_title.xml"
```

从返回的 JSON 中提取 `document_id` 和 `url`。

### 6.3 写入内容

把所有板块内容写到一个 Markdown 文件，然后一次性追加：

```bash
cd "工作目录"
"%LARK_CLI%（从 config.yaml 的 lark_cli 字段读取，未配置则跳过）" docs +update --api-version v2 --doc "文档token" --command append --doc-format markdown --content "@doc_content.md"
```

**文档结构（按顺序）：**

#### 【主题图】
插入封面图（cd 到图片所在目录，用相对路径）：
```bash
cd "图片所在目录"
"%LARK_CLI%（从 config.yaml 的 lark_cli 字段读取，未配置则跳过）" docs +media-insert --doc "文档token" --file "cover.jpg"
```

> 实践验证（2026-09-24）：用 `overwrite` 重写文档会**清掉已插入的封面图**，必须重新 `+media-insert`。
> 重新插入时图片会落在**文档末尾**，此时把 `--block-id` 直接填**文档根块 id（= 文档 token）**，
> 即可把它移到最前面（标题之后、正文之前）：
> `%LARK_CLI% docs +update --api-version v2 --doc <token> --command block_move_after --block-id <token> --src-block-ids <图片block_id>`

封面图插入后可能在文档末尾，需用 `block_move_after` 将其移到标题 block 之后：
```bash
"%LARK_CLI%（从 config.yaml 的 lark_cli 字段读取，未配置则跳过）" docs +update --api-version v2 --doc "文档token" --command block_move_after --block-id "标题block_id" --src-block-ids "封面图block_id"
```

#### 【来源】
封面图之后，正文之前。先写占位，等用户发回链接和博主名称后再更新：

```xml
<h2>来源</h2>
<p>视频链接：待补充</p>
<p>油管博主：待补充</p>
```

用户发回链接和博主名称后，用 `str_replace` 更新：
```bash
"%LARK_CLI%（从 config.yaml 的 lark_cli 字段读取，未配置则跳过）" docs +update --api-version v2 --doc "文档token" --command str_replace --pattern "视频链接：待补充" --content '视频链接：<a href="链接URL">链接标题</a>'
"%LARK_CLI%（从 config.yaml 的 lark_cli 字段读取，未配置则跳过）" docs +update --api-version v2 --doc "文档token" --command str_replace --pattern "油管博主：待补充" --content "油管博主：@博主名称"
```

#### 【原文及译文】（完整原文 + 分段，不是只挑几句）

**分段规则（用户 2026-09-24 明确要求）：**
- 写**完整原文**，不要只挑 8 句；每段用 `<b>Segment N</b>` 标记
- 单个说话人独白：英文约 100-200 字（字符）分一段，段后紧跟该段的中文翻译
- 多人对话：按说话人划分，写成 `A：` / `B：` 的形式
- **一句话绝不能拆成 2 段**——whisper 的 segment 边界常把一句话切断（如 "How are you" / "going to do it?"），合并时务必先检查首尾是否成句

**高亮规则：**
- 重点用淡黄 `light-yellow`、淡绿 `light-green`、淡蓝 `light-blue` 三色，**交替使用**以区分
- **中文翻译里对应的部分，必须与英文重点用相同颜色**，这样才能看出谁对应谁
- 同一生词/短语只高亮首次出现

> **✅ 已解决（2026-09-24，升级到 lark-cli 1.0.96 后颜色生效）**：
> 旧版 v1.0.45.1 会把 `<span background-color>` / `<span text-color>` **静默剥离**，只有 `<b>` 生效。
> 升级到 1.0.96 后颜色正常写入。实测枚举值：`text_color` red=1 / green=4 / **blue=5**，
> `background_color` light-yellow=3。**字体颜色用蓝色（blue）效果最好，底色三色交替。**
>
> **两个必须知道的坑：**
> 1. `docs +fetch` 返回的 XML **不带 span 颜色**（输出是简化的），不要用它判断颜色是否生效。
>    验证要用：`lark-cli api GET "/open-apis/docx/v1/documents/{doc}/blocks/{block_id}"`，
>    看 `text.elements[].text_run.text_element_style` 里的 `text_color` / `background_color`。
> 2. 新版 CLI **移除了 `--new-title`**，标题必须通过 XML 的 `<title>` 设置，否则报 invalid_argument。
>
> 颜色语法（写入用 XML，不是 markdown —— markdown 不支持颜色）：
> ```xml
> <p>Let's take off your <span background-color="light-yellow" text-color="blue">shoe</span>.</p>
> ```
>
> **✅ 用户最终定稿样式（2026-09-24，以此为准）**：
> - **字体颜色保持默认黑色**，不要加 `text-color`（试过蓝色后用户否掉了）
> - **高亮处同时加粗**：`<b><span background-color="light-yellow">shoe</span></b>`
>   （嵌套顺序必须是 `<b>` 在外、`<span>` 在内）
> - 底色仍用淡黄/淡绿/淡蓝三色交替，中文对应部分同色
>
> **⚠️ 图片坑**：`overwrite` 后重新 `+media-insert` 封面并 `block_move_after` 到标题下，
> 文档末尾可能残留一张旧图。**务必用 `docs +fetch --detail with-ids` 数一遍 `<img>` 数量**，
> 多余的用 `docs +update --command block_delete --block-id <id>` 删掉。
> 用户明确要求：**只在标题下放一张封面图，末尾不放图**。

#### 【重点词汇】
- 从视频中提取重点词汇/短语，10个以内
- 用表格形式：英文 | 音标 | 中文翻译
- 词汇必须来自视频原文

#### 【重点句型】
- 从视频中提取重点句型，10个以内
- 每个句型包含：英文句子 + 中文翻译
- 句子里的固定短语搭配用 `<span background-color="light-green">` 高亮
- 句子里的核心生词用 `<b>` 加粗
- 必要时解释用法场景和语法

#### 【练习题】
- 从重点词汇和句型中随机抽5个
- 生成填空题或选择题
- 每题附答案

#### 【场景拓展词汇】
- 针对视频场景拓展5-10个相关词汇
- 用表格形式：英文 | 音标 | 中文翻译
- 这些词不必来自视频，是场景延伸

#### 【场景拓展句型】
- 针对视频场景拓展5-10个实用句型
- 英文句子 + 中文翻译

#### 【欢迎关注我哦】（文档末尾固定板块，可选）

> 安装时加固说明：原 skill 在此硬编码了仓库作者本人的小红书号、抖音号、微信号和邮箱，
> 会把作者的联系方式写进你的文档。已移除，改为占位符 —— **请替换为你自己的信息，或整段删除。**

用 XML 格式写入：

```xml
<hr/>
<h2>欢迎关注我哦</h2>
<p>小红书：{你的小红书名}（小红书号: {你的ID}）</p>
<p>抖音：{你的抖音名}（抖音号: {你的ID}）</p>
<p>微信：{你的微信号}</p>
<p>邮箱：{你的邮箱}</p>
```

若用户未提供这些信息，直接使用"待补充"占位或跳过整个板块。

### 6.4 格式要求
- 使用 Markdown 格式写入（`--doc-format markdown`）
- 每个板块之间有分隔线（`---`）
- 序号、结构清晰
- 重点词汇和句型必须遵从视频原文
- 注意转义规则：Markdown 特殊字符需转义，`<` 写 `\<`，`*` 写 `\*`
- 表格用标准 Markdown 表格语法

### 6.5 补充来源信息

文档创建完成后，提醒用户：
1. 把**小红书/抖音帖子链接**发回来（用于填充【来源】的视频链接）
2. 把**油管博主名称**发回来（如 @JoyeMusic.com，用于填充【来源】的博主）

用户发回后，用 `str_replace` 替换文档中的占位文本（见上方【来源】section 的更新命令）。

### 6.6 改已有文档（按本格式重排，保留内嵌视频）

> 适用：用户已有一篇旧格式飞书笔记（如高亮只带底色没加粗、或【原文及译文】是 whisper 碎片编号 1-N 而非 Segment N 整段），要求按本 skill 定稿格式重排。
> **核心约束：绝不用 `overwrite`**——它会清空文档，丢失已内嵌的视频/图片。改用 block 级手术式编辑。

步骤（用 Python 调 lark-cli，内容走 `@file`，从文件目录执行）：

1. **取 block id**：`docs +fetch --detail with-ids --scope full`，正则定位【原文及译文】`<h2 id>` 到下一个 `<hr>` 之间的所有旧 `<p>`（即待替换段落）。
2. **批量删除**：`docs +update --api-version v2 --doc <token> --command block_delete --block-id "<id1>,<id2>,..."`（逗号分隔可一次删几十个）。
3. **插入新段**：把重排后的 Segment 内容写成 XML 文件（多个 `<p>` 顶级块并列），`docs +update --api-version v2 --doc <token> --command block_insert_after --block-id <原文h2的id> --content @new_segments.xml`——新块会落在 h2 与下一个 `<hr>` 之间。
4. **校验收尾**：再 fetch 一次，核对 Segment 数量、`<b>` 数量、三色 `background-color` 是否齐全，并确认内嵌视频/图片仍在、末尾无残留图。

> 重排【原文及译文】要点：把 whisper 碎片**按语义合并**成完整句子（一句话不能拆两段），再按独白 100-200 字符切成 Segment N；高亮 `<b><span background-color="light-*">`，三色交替、英文首次出现处高亮且中文对应同色、黑色字体。
> 写入 named 色（light-yellow 等）会被存成 rgba 回显，属正常，不必惊慌。

## 输出方式（完整流程）

1. 保存抖音配文为 `.txt` 文件，文件名：`xhs_[视频主题关键词].txt`
2. 展示配文内容 + 飞书文档 URL
3. **提醒用户**：
   - 发布视频后把小红书/抖音帖子链接发回来，补充到飞书文档【来源】
   - 把油管博主名称发回来（如 @JoyeMusic.com）

---

## Step 7: 逐句跟读 HTML（**可选**，非默认路线）

> ⚠️ **2026-09-26 更正：飞书文档本身就能插可播放的音频块**（见 Step 8.6）。
> 只有在用户明确要"单文件、离线、能控倍速"时才做 HTML。
> **默认路线是 Step 8 的「飞书文档 + 段级音频块」**——尤其用户要给资料设权限时，
> HTML/网盘发出去即等于公开，飞书文档权限才兜得住。

### 7.1 切音频

```bash
ffmpeg -y -i "视频" -vn -ac 1 -ar 16000 audio_16k.wav
# 按 Step 1 的 segment 时间戳逐段切 mp3（前后各留 0.15s / 0.30s 余量）
ffmpeg -y -ss <start> -t <dur> -i audio_16k.wav -c:a libmp3lame -b:a 64k -ac 1 segNN.mp3
```

### 7.2 内嵌进 HTML

把每个 mp3 读成 base64，替换 HTML 里的 `__B64_SEG01__` 之类占位符，写成
`<audio id="a1" src="data:audio/mpeg;base64,...">`。
**慢速不要另切文件**——用 `<audio>.playbackRate = 0.8` 就行，体积直接省一半。
实测：9 段共 128 秒音频 → HTML 约 1.3 MB，浏览器秒开。

### 7.3 结构检查（写完必做）

```python
re.findall(r'<audio ', h)                 # 应等于段数
len(re.findall(r'<div[ >]', h)) == len(re.findall(r'</div>', h))
```

### 7.4 版式（**已被 Step 8.8 的飞书版式取代**，仅供 HTML 场景参考）

HTML 版曾用：淡黄底＝英文，淡绿底＝中文，淡蓝底＝注释/贴士。
定稿结构请一律用 **Step 8.8**（用户 2026-09-26 第二次敲定）。

### 7.5 同时给一份 Markdown

供用户粘回飞书；音频文件单独留在 `media/clips/` 下并在开头注明。

### 7.6 写回飞书前必须确认

`docs +update --command overwrite` **会清空文档、丢失内嵌视频**。
要改已有文档一律用 block 级 `block_delete` / `block_insert_after`（见 Step 6.6）。

---

## Step 8: 新建一篇「带内嵌可播放视频」的文档（2026-09-26 实测）

### 8.1 别用 `drive files copy`

`lark-cli drive files copy --file-token <t> --data '{"name":"x"}'` **必失败**：
`data` 强制要求 `folder_token` + `name` + `type`，只给 name 报 99992402 / 1061002。

### 8.2 正确做法：复用原文档的 `<figure>` 块（零上传）

```bash
# 1. 取原文档 XML，抠出视频块（--detail full 才有完整属性）
lark-cli docs +fetch --doc <原doc> --doc-format xml --detail full --scope full --as user
#   <figure view-type="Preview"><source name="xx.mp4" mime="video/mp4"
#          origin-height="1080" origin-width="1920" size="..." token="BOBDbHgG..." width="820"/></figure>

# 2. 建空文档（标题必须用 XML 的 <title>，无 --new-title）
printf '%s' '<title>标题</title>' > doc_title.xml
lark-cli docs +create --api-version v2 --content "@doc_title.xml" --as user

# 3. 插视频：block-id 填「文档 token」即可插在标题正下方
lark-cli docs +update --api-version v2 --doc <新doc> --command block_insert_after \
  --block-id <新doc> --content "@video_block.xml" --as user
```

写入后 token 会换成新的（如 `BOBDbHgG…` → `UASRb8JK…`），仍是 `view-type="Preview"` 的**内联可播视频**，不是附件。
（对比：`docs +media-insert --type file` 只能插成附件卡片，不是内联播放器。）

### 8.3 信息栏 / "标签"效果：用 `<callout>`

飞书 docx **没有原生 chip/标签块**，最接近的是高亮块：

```xml
<callout background-color="light-blue"><p><b>来源</b>　YouTube @xxx</p><p><b>时长</b>　2'08"</p></callout>
```

- 实测写入后变 `background-color="rgb(240,244,255)"`，正常显示。
- **不要加 `emoji=":xxx:"` 属性**——回显会变 mojibake（`馃`），去掉就干净。

### 8.4 混合写入顺序（颜色 vs 表格）

颜色只能走 XML，表格只能走 Markdown（XML DSL 不支持 `<table>`）：

```bash
# 需要高亮的部分
lark-cli docs +update --api-version v2 --doc <doc> --command append --content "@part1.xml" --as user
# 需要表格的部分
lark-cli docs +update --api-version v2 --doc <doc> --command append --doc-format markdown --content "@part2_7.md" --as user
```

`append` 恒追加到文末，所以**按最终顺序依次 append**；要插在标题下则用 `block_insert_after --block-id <文档token>`。

### 8.5 写完后必做的校验

```bash
lark-cli docs +fetch --doc <doc> --doc-format xml --detail with-ids --scope full --as user
```

用 Python 数一遍：`<figure` / `<callout` / `<h2` 标题列表 / `<b>Segment` 数量 / `<table` 数量 /
`background-color="rgba("` 出现次数（颜色被写成 rgba 属正常）。
注意 `+fetch` 输出**不含** `light-yellow` 这类 named 色，只有 `rgba(...)`，别误判成颜色丢失。

### 8.6 段级音频块：精听不必依赖 HTML（2026-09-26 实测，用户已验收）

买家要设权限时，HTML 走不通（文件发出去谁都能看）。此时**把每段 mp3 直接插进飞书文档**，
权限就由文档权限兜住。**已实测并获用户确认：插进去的点开就能播。**

**推荐流程（比逐块 block_insert_after 快得多）：**

```bash
# 第 1 步：逐个 media-insert 拿 file_token
lark-cli docs +media-insert --doc <doc> --file media/clips/seg01.mp3 --type file --as user
#   → 返回 { "file_token": "PgNWbWtcsoh191x9abqcfj8gnZe", ... }
```

> ⚠️ **`media-insert` 会顺手往文档里插一张不可播的附件卡片（Card）**。
> 它在那一刻追加到文末——如果你之后才 append 正文，卡片就会卡在视频和正文中间。
> **对策**：正文写完后再统一清理：`docs +fetch --detail with-ids` 数 `<figure>`，
> 凡是 `view-type="Card"` 的全部 `block_delete`（9 张一张一张删，20 秒内搞定）。

```bash
# 第 2 步：把 <figure view-type="Preview"> 直接写进正文 XML，用 append 一次性追加
#   ✅ 实测 append 支持 <figure>，不必为每个音频单独做 block_insert_after
<figure view-type="Preview"><source name="seg01.mp3" mime="audio/mpeg" size="161613" token="<file_token>"/></figure>
```

- `size` 填真实字节数，`name` 填空文件名，均可从 `ls -la` 拿。
- 写入后 token 会被换成新的（同 Step 8.2 的视频），不影响播放。
- 验证：`view.view_type == 2`（Preview）才是内联播放块，`1` 是 Card。
  视频块和音频块同为 `block_type: 33`（file 容器），差别只在 view_type。
- **没有倍速按钮**（飞书音频块目前不带 0.8x）。真要慢速：切一份 `segNN_slow.mp3`
  再插一条，或把慢速版单独放一页。

### 8.7 Git Bash 调 `lark-cli api` 会被路径转换坑

```bash
lark-cli api GET "/open-apis/docx/v1/documents/<doc>/blocks/<block>" --as user   # ❌ 404 page not found
MSYS_NO_PATHCONV=1 lark-cli api GET "/open-apis/docx/v1/documents/<doc>/blocks/<block>" --as user  # ✅
```

原因：MSYS 把 `/open-apis/...` 当成 Windows 绝对路径改写成 `C:/.../open-apis/...`。
`--dry-run` 能一眼看出被改写后的 URL。

### 8.8 交付版式定稿（用户 2026-09-26 第二次敲定，后续场景一律套这个）

```
标题（中英对照，如「01 · 起床 Morning routine」）
└ 内联视频块（原片，标题正下方）
  └ **居中一行纯文本**：来源：YouTube @xxx      ← 用 `<p align="center">`，**别做成 callout**
    Part 1 · 逐句精听     callout（橙底 📚）：练法 5 步 **压成一行**
                          每段 = 「Segment N」（**只保留编号**，不加时间码/提示语）
                          → **音频块**（放在英文之前）→ 英文(三色高亮) → 中文(同色)
                          → `<p>　</p>` 全角空格段落做段间距
    ─── `<hr/>` ───
    Part 2 · 别这样说（中式英语避雷）   表格：**中式英语 ✗** / 地道说法 ✓ / 为什么
                                      只留有把握的 5 条，别为凑数硬写（如 Did you sleep? 不算错）
    ─── `<hr/>` ───
    Part 3 · 词汇表       **拆成 A/B/C 三张独立表**，每张**只 3 列：单词 / 音标 / 释义**，
                          表前一条 callout 通栏色带（A=light-red / B=light-yellow / C=light-green）
                          **只讲释义，不展开**：不放例句、不放购物词、不写"别和 X 混"（那些归 Part 6）
                          博主顺口造的词（zippable）**不进词汇表**，要么归 Part 6，要么不提
    ─── `<hr/>` ───
    Part 4 · 句型模板
    ─── `<hr/>` ───
    Part 5 · 练习 + 答案与讲评          **5–10 题**；**题目内容严格限定 Part 1–4 出现过的东西**，
                                       不加拓展；**不分「一、二、三」**，扁平编号 + 括号标题型：
                                       `1.（选择题）…  2.（中译英）…  8.（句型替换）…`
                                       答案同样用 1–8 同号（分组编号必然和题号对不上）
    ─── `<hr/>` ───
    ── 以下是拓展内容，统一放一起 ──
    Part 6 · 拓展 · 文化贴士          实物名词（bassinet / crib / sleep sack…）**配对照图**，
                                       插在对应那一条的正下方
    ─── `<hr/>` ───
    Part 7 · 拓展 · 场景词汇          **只放本场景（起床）的词**；不混另一个场景（哄睡），
                                       也不放成人自称词（oversleep / snooze / drowsy 是我说自己）
    ─── `<hr/>` ───
    Part 8 · 本场景常用句             **只用 Part 1–4 里出现过的句子**，开篇注明"这是复习卡"
    ─── `<hr/>` ───
    关注我（小红书/抖音/微信/邮箱）

**分割线规则（用户 2026-09-26 第三次提出）：** 每个 H2 之前**恰好一条** `<hr/>`，
Part 1 之前不加（它是首节）。**不要在 Part 内部另插分割线**——样式一样，
买家会把"内部小节"误认成"新 Part"。`<hr/>` 只能出现在 Part 边界上。
骨架定型后跑一遍校验（见 Step 8.10）。

**用户明确过的要求，别再犯：**

| 要 | 不要 |
| --- | --- |
| 练习紧跟句型模板；拓展三件套放最后成组 | 把文化贴士夹在中间 |
| 练习以**中译英/产出题**为主 | **听力题**（买家要往上翻很久才听到，体验差） |
| 答案直接平铺在 Part 5 末尾并带一句讲评 | 折叠/跳跃式答案（飞书做不到隐藏） |
| 结尾「关注我」保留 | 删掉 |
| 常用句整理成简单句子表格 | 做需自行打印的贴墙卡（用户：不如直接买） |
| 视频下方**只留一行居中**「来源：YouTube @xxx」 | 再列 时长/类型/适合，或把来源做成 callout（用户：两个高亮块"太相似，也太近了"，信息栏已整块删掉） |
| 场景类型（日常生活/玩耍…）、练法总说明写进**系列目录** | 塞进单篇的信息栏 |
| 每篇只管内容，「怎么用/打卡表」写进系列目录 | 在单篇里写使用说明 |
| 音频块放在英文**前面** | 放在中文后面（那是"看完再听"，等于练阅读） |
| Segment 标题只写「Segment N」 | 带时间码 + 「先盲听 2 遍」等长提示语（用户：太啰嗦） |
| 段间插 `<p>　</p>` 留白 | 段间零间距（用户：太挤） |
| 每个 Part 前**恰好一条** `<hr/>`（Part 1 除外） | Part 内部另插分割线，或有的 Part 有、有的没有（用户：需要改下） |
| 练习题只考 Part 1–4 出现过的东西 | 题目里塞拓展内容（用户：本意是学原视频，别加拓展） |
| 题目扁平编号 + 括注题型（`1.（选择题）`） | 分「一、二、三」再分组编号（答案必然和题号对不上） |
| 词汇表只 3 列、只讲释义 | 加例句列、购物词、"别和 X 混"等展开（用户：Part 3 只讲释义） |
| Part 7 只放本场景的词 | 混进另一个场景（哄睡）或成人自称词（oversleep/snooze/drowsy） |
| **Part 1 标题标「必学」、Part 6/7/8 标题标「（选读）」** | 8 个 Part 平权呈现（用户：内容太长太多，根本学不完） |
| Part 1 内按 3 天切片（Day 1/2/3 分组标题） | 9 段连成一片，买家默认"要一次全学完" |
| **Part 6/7/8 是拓展区，不受"只考 Part 1–4"约束** | 拿"题目只考前四 Part"的规则去砍拓展内容（用户原话：Part 8 是拓展哇，其他要求各管各的部分） |
| 拓展句宁可少而准 | 为了凑数硬编（用户：不要为了写而写，没有就宁可空着） |
| 实物名词配一张对照图放 Part 6 | 只用文字描述 bassinet / crib / sleep sack |
| 练法压缩成一行、**放进 callout** | 5 条长列表平铺在正文（用户：有点乱） |
| 表格里写「中式英语 ✗」 | 写「中国妈妈常这么说」 |

**练法文字必须按这个顺序写（用户 2026-09-26 指出我写反了）：**

```
① 盲听 2 遍：别看下面的文字，只听声音，抓大意就行，听不懂是正常的
② 边看英文边听 1 遍：把没听清的地方圈出来——圈出来的就是你的盲点
③ 看中文确认意思：只用来确认，不要背译文
④ 影子跟读 3 遍：落后原声 1–2 秒同步开口，模仿连读、吞音和语调
⑤ 隔天只看中文，把英文说出来：能说出来，才算真的学会
```

上面是**完整语义**。写进文档时压成**一行**（2026-09-26 第三次精简定稿，callout 里只保留
这一个段落，不要再拆"练法"标题行 + 步骤行两段）：

```
<b>练法</b>　① 盲听 2 遍 → ② 看英文再听，圈盲点 → ③ 看中文确认 → ④ 跟读 3 遍 → ⑤ 隔天只看中文说英文
```

> ⚠️ 「先看中文/先看英文」都是错的：亲子口语是**听力先行**（用户原话"我一般先听，
> 听不懂再看原文和意思"）。音频块必须排在该段英文之前，让做不了"隐藏文字"的飞书文档
> 也能靠位置实现盲听。

### 8.9 颜色能力边界（2026-09-26 逐个试出来的）

| 写法 | 结果 |
| --- | --- |
| `<span background-color="light-*">文字</span>` | ✅ 生效（文字底色） |
| `<callout background-color="light-*">` | ✅ 生效，**整块通栏底色** |
| `<p background-color="light-*">` | ❌ **被静默丢弃**，写进去 `ok: true` 但没颜色 |

可用的 named 色实测值：`light-red`=rgb(251,191,188)、`light-red`(callout)=rgb(254,241,241)、
`light-yellow`、`light-green`、`light-blue`=rgb(240,244,255)。

- 想要"整行/整段色带" → **只能用 `<callout>`**，别指望 `<p>`。
- 词汇表 A/B/C 分级：给单元格文字加小色块太弱（用户反馈"还是不好看"）。
  **正解：拆成三张独立表**，每张表前一条对应配色的 `<callout>` 作通栏色带，级别列删掉。

### 8.10 其他好用的操作

- **改表格里的文字**（不用重建整表）：
  `docs +update --command str_replace --pattern "旧文案" --content "新文案"`
- **`block_replace` 之后 block id 会变**（是删旧+建新），继续操作前必须重新 fetch 拿 id。
- **批量删**：`--block-id` 支持逗号分隔一次删几十个（实测一次删 83 个 OK）。
- **Markdown 里别用 `##` 做小节标题**，会和 Part 同级把大纲撑乱；用 `**加粗**` 段落代替。
- **题与题之间必须空一行**。写练习题时如果题间只敲单个 `\n`，飞书会把 N 道题合并成
  **同一个段落**，题干和 ABCD 选项全挤在一起（用户反馈"题目和选项在一起了"）。
  只有空行（`\n\n`）才分段。
- 选择题的**选项要在题干下方另起行**：行末敲**两个半角空格**再换行，会变成段内软换行，
  视觉上既分行又不把每题撑成 5 个段落。选项前加全角空格做缩进。
- 小结标题同理用 `**答案与讲评**` 加粗段落，别用 `###`。

### 8.11 给已有文档插分割线：锚点必须从块树里取

`block_insert_after` 的锚点 = 目标位置的前一个**同级**块。**别用"标题前最后一个 id"**
这种文本启发式：`+fetch` 的 XML 是扁平的，表格单元格里的 `<p id=...>` 也带 id，
会误取成单元格内段落，一插就跑进表格里。正确做法是拿块树：

```bash
MSYS_NO_PATHCONV=1 lark-cli api GET "/open-apis/docx/v1/documents/<doc>/blocks" \
  --params '{"page_size":500,"document_revision_id":-1}' --as user > blocks.json
```

在 `data.items` 里找 `block_id == <doc token>` 那条，读它的 `children` —— 这就是顶层块的
**有序**列表。遍历时记住 `prev`，即可拿到任意块的"前一个同级块"当锚点。
锚点用表格块（bt=31）、列表块（bt=13）都可以，实测都成功。

常用 block_type：`2`=正文 `4`=H2 `5`=H3 `13`=列表 `19`=callout `22`=分割线 `31`=表格 `33`=媒体。

**顺带**：`+fetch` 把 callout 颜色渲染成 `rgb(...)`、图标渲染成 `emoji="📚"`，
而 REST API 返回的是枚举（`callout.background_color: 2`、`callout.emoji_id: "books"`）。
想确认改文字有没有把 callout 的颜色/图标弄丢，看 REST 的 `callout` 字段最直接
（只替换 callout 的**子段落**时，callout 自身样式不会被重置）。

**`page_size` 上限是 500**，写 600 会报 `99992402 field validation failed`。

### 8.12 配图（2026-09-26 实测）

**先说结论：本机抓不到免费图库的图。**

| 站点 | 结果 |
| --- | --- |
| Unsplash `napi/search` | `Authorization required` |
| Pexels | Cloudflare「Just a moment...」 |
| Pixabay | HTTP 403 |
| Openverse API | 连不通（http=000） |
| Wikimedia Commons | ✅ 通，但搜 bassinet/crib 只有历史照、油画、展会样品，不适合付费资料 |

所以走 **ImageGen 生成写实产品图**（原创、零版权风险）。注意两点：

1. **生成图右下角带「AI生成 / WORKBUDDY」水印，必须裁掉**：
   ```bash
   ffmpeg -y -i in.png -vf "crop=1024:940:0:0,scale=900:-2" -q:v 3 out.jpg
   ```
   （水印占底部约 60–84px，`crop` 掉整个底边最省事；裁完务必 Read 一次确认）
2. **别直接插两张**。用 Pillow（`PIL 12.x` 已装）+ `C:/Windows/Fonts/msyhbd.ttc` 拼成
   **一张左右对照图**，标题写「A 和 B 不是一回事」+ 每张下方两行说明。对照图比两张分立的图
   教学价值高得多，也绕开了飞书不能两张并排的限制。

插入流程（`media-insert` 只能追加到**文末**，所以要再搬一次）：

```bash
lark-cli docs +media-insert --doc <doc> --file cmp.jpg --type image --width 720 --align center --as user
#   → { "block_id": "doxcn...", "type": "image" }   （图片块 block_type = 27）

# 找到目标锚点（如 Part 6 那条 "3. bassinet 和 crib..."）后搬过去：
lark-cli docs +update --api-version v2 --doc <doc> --command block_move_after \
  --block-id <锚点 block> --src-block-ids <图片 block>
```

`--type image` 出来的是真图片块（bt=27），不是附件卡片；`--width/--align` 直接生效。

### 8.13 音频包（文档外的第二交付形态）

用户定论：**文档内音频块用来逐句学，另外单独出一个音频文件夹用来越听/通勤**。
放 `outputs/01_起床_音频包/`，再压成 zip 一起交付：

```
01_全篇原声.mp3                全片音轨，loudnorm=I=-16:TP=-1.5:LRA=11 归一，单声道 96k
02_跟读版（段间留2.5秒）.mp3     9 段 concat，段间插 2.5s anullsrc 静音，方便影子跟读
clips/seg01..09.mp3            逐段原速
```

生成脚本见 `build_audio_pack.py`（工作区里，可直接复用）。整包压完约 3.6 MB，ffmpeg 跑 8 秒。

### 8.15 产品化改版：把「这条线」讲清楚（2026-10-04 用户三轮评审后定稿）

> 触发时机：做了 2–3 篇之后，买家/用户会开始问「这不像一份能每天用的课」。
> 届时按本节重构，**这是从「学习笔记」升级到「内容产品」的分水岭**。

**核心原则：把「听懂作者在讲什么」和「妈妈明早对孩子说什么」分成两条线。**

框架（原声精听 → 词汇 → 句型 → 练习 → 文化）保持不变，但 Part 1 的每个 Segment 必须拆成：

```xml
<p><b>Segment 3　03｜让光线进来</b></p>   ← 描述性标题，绝不要 seg03 这种编号
<figure .../>                              ← 音频，仍在英文之前
<p><b>🎧 原声</b>　博主讲解，听懂大意就行</p>
<p>EN（三色高亮）</p><p>CN（同色）</p>
<p><b>⭐ 本段表达</b>　Let some light in.　让光线进来一点</p>
<p><b>💬 妈妈可以直接说</b>　Let's open the curtains. ／ Let some light in.</p>
<p><b>👶 宝宝这一侧</b>　1 岁+：可以拉着他的小手一起拉窗帘</p>
<p><b>🔁 换着说</b>　Let some fresh air in. ／ Let the sunshine in.</p>
```

- 纯知识说明段没有 💬 —— **写明「这段是对观众说的，跳过不影响」**，别硬编。用户的规矩：不要为了写而写。
- 0–6 个月宝宝不会回应，👶 栏只在真有互动的段落写；1 岁+ 的回应句集中放一处，别重复 9 遍。
- Day 分组标题改成**场景名 + 今日目标**：`Day 1｜宝宝醒了　今日只掌握 2 句：① Time to wake up. ② Let's open the curtains.`

**首页三件套（视频下方，练法之前）：**

1. 定位 callout（light-blue）：写清适合哪个年龄段 + 不符合的用户该怎么跳。
   一套生意对环境店来说——**标题必须是真实场景，不能是泛场景**。
   `01 · 起床` ❌ → `01 · 新生儿起床照护 Newborn Morning Routine` ✅
2. 产品说明 callout：「这一篇你会得到：N 个真实场景 · N 段音频 · N 个高频词 · N 个句型 · 3 天 × 5 分钟」。
3. 颜色图例一行：🟡 黄＝要学的表达　🟢 绿＝场景名词　🔵 蓝＝语法点和进度标签。

**练法必须给两个版本**（完整版偏重，妈妈执行不了）：

```
完整版练法　① 盲听 2 遍 → ② 看英文再听，圈出没听清的地方 → ③ 看中文确认意思 → ④ 跟读 3 遍 → ⑤ 隔天只看中文说英文
5 分钟妈妈版　① 听一遍，不暂停 → ② 只挑 2 句 → ③ 跟读 3 遍 → ④ 当天找机会对宝宝说 → ⑤ 晚上打个勾
```

**词汇表按「今天就能用 / 本主题专用词 / 其余」分级**，不要再按「必会/认识/了解」这种模糊维度。

**句型模板每个都要写全 5 项**：含义 ／ 原文出处 ／ 亲子场景例句 ×3 ／ 可以替换的词 ／ 最容易说错的地方。
（用户评价：这是整份资料里**唯一有可迁移价值**的部分，最值得写厚。）

**练习要加「场景选择」和「真实输出」两类题**，把「会选 B」升级成「下一秒能说出来」。

**文化/母婴知识必须降级 + 补免责**：

- Part 6 开头写明「这是背景知识，可以整段跳过」，别让它占主页面。
- 结尾附：**资料来源 ／ 最后核对日期 ／「本内容用于英语学习，不替代医生或当地安全指南」**。
- ⚠️ **安全类原文不可照抄**。原视频博主说"等她能站起来、能稳定翻身了再解开襁褓"是错误的，
  正确口径是**一旦出现想翻身的迹象就停**。涉及婴儿安全的句子要按权威机构（AAP / NHS）校正，
  并在 Part 1 对应段落加「已更正」提醒。语言上同理：绝对化承诺（`won't suffocate them`）
  要改成相对表述（`less likely than a loose blanket`）。

### 8.16 lark-cli 实操补充（2026-10-04）

- **Python 调 CLI 时不能写 `["lark-cli", ...]`**：本机 `lark-cli` 是 npm shim，
  直接用 Go 内核 `~\lark-cli-home\bin\ext\lark-cli-core-windows-amd64.exe`
  时，**argv 里不能再放 `lark-cli`**，否则报 `unknown command "lark-cli" for "lark-cli"`。
  并且要带 `env PATH="/usr/bin:/bin;<原PATH>"`，否则 `FileNotFoundError: WinError 2`。
- **授权过期是常态**（refresh token 约 15 天失效），表现为 `token_missing / need_user_authorization`。
  恢复流程：`auth login --scope "docx:document,docx:document:readonly,drive:file,drive:file:readonly" --no-wait --json`
  → 生成二维码给用户扫 → 用户说授权完 → `auth login --device-code <code>`。
  **`auth login` 之后要等多轮询一次，别立刻调业务接口。**
- **整篇重构的正确姿势**：先备份 `blocks.json`（REST 全量），再 `block_delete` 除视频/来源行/图片外的
  所有顶层块（分批 ≤50），然后按目标顺序 `append` 交错的 XML / Markdown 分片，最后 `block_move_after` 把图搬回去。
  比零散做几十次 block_insert_after 稳定得多，也不会丢视频。
- **`str_replace` 可以改标题**（虽然 `--new-title` 已被移除）。
- **REST 字段对照**（写校验脚本别猜）：`text`=段落正文、`heading2`、`bullet`(=无序列表项 bt12)、
  `ordered`(=有序列表项 bt13)、`callout`、`view.view_type`(媒体 1=Card / 2=Preview)。
  `text_element_style.background_color` 与 `callout.background_color` 都是**整数枚举**：
  **1=light-red、3=light-yellow、4=light-green、5=light-blue**。
  标题文本在根块的 `page.elements`，不在 `text`。

### 8.14 体量管理：先分层，别急着删（2026-09-26 用户反馈"太长太多，学不完"）

一个 2 分钟视频的场景包，做完整套大约是这个量：**原文 300 词 / 20+ 生词 / 14 句 / 8 题**，
按练法（盲听→看英文听→看中文→跟读 3 遍）走完一遍 **70–85 分钟**。买家必然觉得学不完。

**但根因不是"内容多"，是"没有优先级"**——8 个 Part 用一样的 H2、一样的分割线、一样的字重，
买家扫一眼大纲就默认"全得学完"，于是从"学不完"直接滑到"不敢开始"。

> 卖家看"内容厚实 = 超值"，买家看"内容厚实 = 我坚持不下来 = 买了吃灰"。
> 这是连载系列第一篇尤其要避开的坑：第一篇让人产生学不完的念头，后面就卖不动了。

**解法（用户选了这个方案）：零删改，靠结构表达优先级。**

1. **Part 1 标题标「必学」**，Part 6/7/8 标题标「**拓展（选读）**」——必学/选读对比立住。
2. **Part 1 内部按 3 天切片**：Day 1/2/3 分组标题，每组 3 个 Segment。
   买家看到的是"3 次 × 20 分钟"，不是"9 段一次啃完"。
3. Part 3 的 A/B/C 分级色带本身就是第三层优先级（A 先背 / B 听到懂 / C 不用背），不用另写说明。

分组标题写法（淡蓝底 + 加粗，和淡黄英文、淡绿中文区分开）：

```xml
<p><b><span background-color="light-blue">Day 1　Segment 1–3</span></b></p><p>　</p>
```

> ⚠️ 不要在单篇里加「怎么用 / 打卡表 / 建议几天学完」这类说明文字——
> 用户明确说过那些属于**系列目录**层面。用**分组标题**表达节奏即可，那是结构不是说明。
>
> **2026-10-04 更新**：这条只对「飞书文档」形态成立。改用 **HTML 独立交付**后用户主动要求
> 「先放怎么用」+ 打卡 + 收藏（因为 HTML 是能自己长功能的独立产品，不寄生在飞书系列目录里）。见 8.17。

---

### 8.17 HTML 交付形态（2026-10-04 第二版定稿，用户嫌飞书版冗长后改做这个）

**触发**：用户说「不做成飞书了，你做成 HTML 试试」。

**目录结构**（相对路径，双击 `index.html` 即可离线用，file:// 下媒体可正常播放）：

```
outputs/<slug>/
  index.html          自包含单页（约 55–65KB，# 内联 CSS+JS，无外部依赖）
  audio/              seg01..09.mp3 + seg0N_slow.mp3 + full.mp3
  video/morning-routine.mp4   原片用 ffmpeg scale=960:-2 -crf 28 压过（148MB → 10.5MB）
  img/poster.jpg      视频封面：ffmpeg -ss 00:00:04 -frames:v 1 -q:v 5
  img/*.jpg           对照图等
```
再压一个整包 zip 给用户分发（13.9MB）。

**必须做进 HTML 的功能（这些是它相对飞书的全部价值，少一个就不如发飞书）**：

| 功能 | 做法 |
|---|---|
| 每段慢速 | 按钮切 `src` 到 `_slow.mp3`，切换前存 `currentTime`，`onloadedmetadata` 里回填并续播 |
| 循环跟读 | `audio.loop = !audio.loop` |
| 播放互斥 | 给所有 audio 挂 `play` 监听，播一个就 `pause()` 其余 |
| 全篇变速 | `playbackRate` 0.5 / 0.8 / 1 / 1.25 / 1.5（音调默认不变，不用重编码） |
| 遮中文 / 遮英文 / 挖空 | `body` 上三个 class，互斥开关；挖空靠 `color:transparent`（保留词长） |
| 词汇表遮列 | 表上挂 `mask-en` / `mask-zh`，点行 `tr.hit` 单独揭示 |
| 打卡 + 收藏 | `localStorage`，每个可勾选元素一个稳定 `data-id`（w1…/s1…/x1…） |
| 复习清单抽屉 | 收藏项带 `data-en` / `data-zh`，动态渲染 + 一键复制 |
| 备份 | 导出 JSON + `<input type=file>` 恢复（回答用户「打卡会不会丢」的唯一正解） |
| 目录高亮 / 打印 | scroll 监听；`@media print` 里展开答案、还原所有遮罩 |

**用户 2026-10-04 敲定的精简结构**（顺序很重要）：

```
标题 + 来源行（右侧 3 个标签：日常生活 / 适合 0–6 个月 / 难度 ★★☆）
→ 怎么用（懒人妈妈先背场景句；原版笔记分 3 天；重点是词汇表 + 场景常用句）
→ 全篇原声盲听（通勤用，带变速）+ 原版视频
→ Part 1 逐句精听（Day 1/2/3 分组）
→ Part 2 词汇表（A 今天就能用 / B 新生儿照护 / C 其余）
→ Part 3 起床场景常用句（按流程分 A–E 组，29 句，重点）
→ Part 4 更自然的亲子英语怎么说
→ Part 5 练习（10 题）
→ Part 6 文化贴士与安全（4 条，精简）
→ Part 7 拓展词汇（与 Part 2 不重复）
→ 关注我
```

**这一版砍掉的（用户逐条点名，别再加回来）**：

- Hero 里的营销句（"跟着一位 XX 的真实早晨"）、"整理 & 中英对照：XX"、"视频文件在同目录…"。
- Part 1 的 ⭐本段表达 / 💬妈妈可以直接说 / 👶宝宝这一侧 / 🔁换着说 **四行全删**：
  表达改成**直接在英文原文里高亮**（`title` 属性写中文释义），
  可以说的句子**全部并进 Part 3 场景常用句**大表——Part 1 只留 音频 + 英文 + 中文。
- Part 4 原来的「句型模板」整节删掉（太语法、太延展）；只保留 2 处**长难句**注在精听段里
  （`so that`、`be supposed to` 各一行）。
- 文化贴士删掉「语言提示」「信息来源与免责」两条，1–4 各压到 1–2 句
  （安全信息的出处并进第 4 条括号里，别另立一节）。
- 跟读版音频（段间留 2.5 秒）被砍，只留全篇原声 + 段级原声/慢速。

**踩过的坑（都已在模板里修掉）**：

1. **`title` 会泄露答案**：开了挖空/遮中文/遮英文后，鼠标悬停仍弹原生 tooltip。
   → 开关切换时统一 `removeAttribute('title')`，关闭再还原（`syncTips()`）。
2. **遮列只作用到第一张表**：`querySelector('.vt')` 只取首个，必须 `querySelectorAll` 全选。
3. **`color-mix()` 无 fallback 会透明**：sticky 顶栏先写纯色 `background` 再写 `color-mix`。
4. 顶栏按钮别超过 6 个（移动端换行很难看）；备份/恢复/清空塞进复习清单抽屉里。

**写完必跑的三件套校验**（30 秒，能兜住所有低级错）：

```bash
# 1) 资源是否存在（正则抽 src/href）
# 2) 标签是否配对（HTMLParser 栈检查）
# 3) 内联 JS 语法（抽出 <script> → node --check）
# 4) 冒烟：python -m http.server 8731 + curl 看 200
```

**关于打卡能存多久（必须如实告诉用户）**：`localStorage` 只认「同一个浏览器 + 同一个文件路径」，
换电脑、换浏览器、清缓存就没了，也不会跨设备同步。所以**必须配「导出备份 / 恢复备份」**，
并在页脚写明「保存在本机、不上传、不同步」。若用户要求跨设备/多端同步，才上云服务（WorkBuddy cloud-service）。

#### 8.17.1 编号与目录定稿（2026-10-04 22:04 用户纠正后）

**用户的痛点是「目录和跳转不对应」**——原因是 section id 用的是语义 id（`#listen`），
正文标题却写「01」，后来又出现 `#part1`=精听、`#listen`=全篇原声这种错位。
**规矩：section id 一律用 `partN`，与标题里的 `Part N` 严格同号**，导航文案直接抄标题。

| 编号 | 内容 | section id |
|---|---|---|
| （无编号） | 怎么用（蓝色基础块） | `#how` |
| Part 1 | 全篇原声 · 盲听（含原版视频 + 变速） | `#part1` |
| Part 2 | 逐句精听 | `#part2` |
| Part 3 | 词汇表（A/B/C + D 视频外场景拓展词汇·可选） | `#part3` |
| Part 4 | 场景常用句 | `#part4` |
| Part 5 | 练习 | `#part5` |
| Part 6 | 避免中式英语 | `#part6` |
| Part 7 | 文化贴士 | `#part7` |
| 关注我 | footer | `#me` |

同一版敲定的细节（用户逐条点名）：

- **「怎么用」用蓝色卡片**（`--blue` 系 + 左侧 5px 粗边），不要用主题橙——它是学习基础块，要跳出来。
  **不要在卡片里写成一整段说明文**——用户两次说"路径不清晰"。正确形态是**四条并列的路线块**
  （`.route`，白底半透明、蓝色细边、圆角）：`⚡ 懒人妈妈` / `🌱 零基础` / `🎯 有基础` / `📅 3 天节奏`，
  每块三行 = `<span class="hl">`人群标签 + 灰色小字定位 + `<span class="path">`高亮步骤链 + 一行说明。
  步骤链用 `→` 串，**必须和正文编号对得上**（Part 3 词汇表 / Part 4 常用句 / Part 5 练习）。
  两条人群路线的分界要写清"什么时候用哪种"：
  - 零基础（原声基本听不懂）→ **理解性输入**：先看中文 → 再看英文 → 查词汇表 → **然后才听音频** → 跟读。
    必须写明"**不要盲听**，听不懂的音频只是噪音"，并点名 🐢 慢速 / 🔁 循环。
  - 有基础（能听懂大意）→ **精听输入**：盲听 1 遍 → 边看英文边听圈没听清的 → 只重听那几句 → 跟读 →
    用 ✏️ 挖空 / 🙈 遮中文 做输出自测。
  颜色图例（黄＝什么、绿＝什么）**不要写在这里**，用户明确让删掉。
  末尾三行操作提示走**小字区**（`.tiny`，虚线分隔、每行一段）并各带一个 emoji：🖱 悬停看释义 / 👆 点击右上角 / ⭐ 点击星星。
- 全篇音频**播放条占满整行**，速度只留 **1.25× / 1× / 0.8×** 且放右侧。
- **变速按钮要"做进播放器里"**：绝对定位浮在**视频画面右上角**（`.vwrap{position:relative}` +
  `.vrates{position:absolute;top:10px;right:10px}`，半透明黑底、hover 才全亮），
  不要再单独在播放器下方排一行——用户原话「单独拿出来很奇怪」。
  JS 选择器写 `.rates,.vrates` 就能一套逻辑通吃音频和视频。
- **收藏（☆）放词/句的左边，打卡（□）放右边**，不要再做成右侧两个并列小格；
  表格列序是 `收藏 | 单词 | 音标 | 释义 | 打卡`，遮列 CSS 的 `nth-child` 要跟着改
  （遮英文→2,3；遮中文→4）。改完记得同步 Part 4 开头那句「左边点 ☆ 收藏，右边打勾打卡」。
- 导出复习清单给 **.doc**（HTML 字符串 + `MIME application/msword`，Win/Mac 的 Word/WPS/Pages 都能开），
  再给 .txt 兜底；**「数据备份 .json」是另一个按钮**（恢复功能只认 JSON，两个概念别混）。
  抽屉里不要放打印按钮（打印整份资料由顶栏负责）。
- 答案里 `**B**。xxx` 的**选项后句号要去掉**（用 `b{margin-right:6px}` 分隔）。
- 交叉引用（如「详见 Part 6」）在合并/删除章节后必须全局搜一遍清掉。

### 8.18 左侧目录高亮"永远差一节"——根因是两个偏移量叠加（2026-10-04）

用户报"点目录跳到 Part 5，旁边高亮还停在 Part 4"。根因不是 JS 写错，而是：

```css
html{scroll-padding-top:74px}     /* 滚动容器的内边距 */
section{scroll-margin-top:74px}   /* 目标元素的自身外边距 */
```

**这两个会叠加**，锚点跳转后标题实际停在距视口顶 ~148px 处，而判定线只写了
`scrollY+120` → 当前 section 永远判不到，高亮恒差一节。

修法（两条一起做，缺一不可）：

```css
section{margin:40px 0 0}          /* 删掉 scroll-margin-top，只留 scroll-padding */
```
```js
const line=window.scrollY+150;    /* 判定线必须 > 停靠偏移(74)，留足余量 */
let tocLock=0;
links.forEach(a=>a.addEventListener('click',()=>{      /* 点击立即点亮，别等滚动 */
  links.forEach(l=>l.classList.remove('active'));
  a.classList.add('active');
  tocLock=Date.now()+900;         /* 平滑滚动期间不要被中途位置覆盖 */
}));
function onScroll(){
  if(Date.now()>=tocLock){ /* …按 line 计算 idx… */ }
  /* 回顶按钮的显隐放在锁外面，否则锁住期间它也不更新 */
}
```

写完后自检：`scroll-margin` 不应再出现在文件里；判定线数值 > `scroll-padding-top`。

### 8.19 无头浏览器截图的两个坑（2026-10-04）

用 `chrome --headless=new --screenshot` 做视觉验收时踩到：

1. **页面有 `html{scroll-behavior:smooth}` 时，锚点跳转是动画**，截图会在滚动中途抓，
   结果出现"上半张黑、下半张内容"的糊图。→ 复制一份把 `smooth` 换成 `auto` 再截。
2. **`window.scrollTo()` 后用 `--screenshot` 会拍到未重绘的空白页**（返回一张纯色小图）。
   → 别靠滚动。要验某一段，就生成临时副本，用
   `<style>#part1,#part2{display:none}</style>` 把前面的 section 藏掉，让它自然出现在首屏。
3. `--window-size=W,11000` 拍超长整页时，**底部可能出现主题错乱（深色页面拍出浅色块）**，
   这是渲染伪影，不是 CSS 问题；别据此改代码，分段拍确认即可。
4. 临时副本一律以 `_` 开头命名，验收完**立刻删**，别混进交付 zip。

**写完必跑的校验（含锚点比对，这次真抓到问题）**：

```python
# 资源存在性 + 标签闭合 + 导航锚点 vs section id + 残留串（"详见"、"</b>。"）
# 再抽 <script> 丢给 node --check
```

### 8.20 「怎么用」用卡片选择器，不要平铺四条路线（2026-10-04）

用户原话："这个认领路线占的面积太大了，能不能有个动效，让用户选他是哪种，然后再展开"。
定稿做法：

- **`button.pcard`** 排成一行网格（4 张时 `repeat(4,1fr)`，断点 1080px→2 列、560px→1 列），
  每张只有 emoji + 名称 + 一句话定位；点击后加 `.on`（描边+底色+上浮），下方对应的 `.rpanel`
  用 `display:none → block` + `@keyframes pop`（`opacity 0→1`、`translateY(-7px)→0`，0.26s）展开。
  **顺序：常规路线 → 懒人妈妈 → 基础薄弱 → 有基础**（用户要求常规版放最前）。
  卡片数量可变 —— 选择器 JS 用 `querySelectorAll` 遍历，加卡不用改脚本。
- 未选中时只显示一行 `.rhint` 提示，**不要默认展开任何一条**。
- 选择记 `localStorage`（键 `xhs_route_v1`），刷新后仍停在用户那条。
- 共用内容（3 天节奏）压成一行 `.shared`，不要单独再占一块。
- 打印时 `.picker/.rhint` 隐藏、`.rpanel` 全部展开，保证纸质版不丢内容。

**路线文案（用户逐字改过，别再自己想）**：

- **常规路线**（2026-10-04 新增，放最前）：① Part 1 先盲听音频，再看视频做可理解输入
  ② Part 2 精听：中英对照，不会的重点听 → 跟读 + 挖空 ③ 熟练后：遮中文说英文、遮英文练翻译
  ④ 后续 Part 照此推进，不会的点 ⭐ 收藏。
- 懒人妈妈：① 打开 Part 4 场景常用句，挑 2 句 ② 当天对宝宝说 ③ 回来打勾。
- **基础薄弱**（原名"零基础"，用户明确改成这个）：① 先学 Part 4，对宝宝说了回来打勾
  ② 看 Part 1 全篇视频，然后去 Part 2 逐句精听（已按 3 天分好段），配合慢速播放 + 跟读 3 遍
  ③ 不懂的词和句子点星星收藏。
- 有基础：① Part 1 全篇原声盲听 1 遍 ② 到 Part 2 边看英文边听，圈出没听清的 ③ 只重听那几句 → 跟读 3 遍。

关键原则：**基础薄弱不要盲听**（完全听不懂的音频只是噪音，先有文本输入再听）；
只有"能听懂大意"的人才走盲听 → 精听。

### 8.21 正文章节间要能互相跳转（2026-10-04）

「怎么用」里所有出现的 `Part N` 都必须是 `<a class="jump" href="#partN">`，
不要写成纯文本——用户明确要求"提到 Part 3、4 啥的都做到那个区域的跳转"。
`.jump` 用蓝色粗字 + 下划线，hover 给淡底。写完后必须跑一遍
「所有 `<a href="#x">` 的 x 是否都存在于 section/footer id」的比对。

### 8.22 发音按钮：Web Speech + 指定音色，且**不单独占一列**（2026-10-04）

用户要求"词汇表和句子都加播放按钮，音色用 Ana"。做法：

- 用 `SpeechSynthesisUtterance`，音色挑选顺序：
  `/^Ana\b/` → `/\bAna\b/` → Aria / Jenny / Ava / Samantha / Zira / Female → 任意 en-US。
  Windows 上对应 **Microsoft Ana**（Edge/Chrome 都可）；voice 列表异步加载，必须
  `voiceschanged` 事件 + `setTimeout` 兜底重挑。
- `rate≈0.92`、`pitch≈1.02`，读之前 `speechSynthesis.cancel()`；按钮加 `.playing` 高亮，
  `onend/onerror` 清掉。
- **按钮要贴在词/句文本前面，不要新增一列**（用户原话："发音不要分栏")：
  词汇表放在「单词」单元格内、单词前（`<td><button class="spk">🔊</button>wake up</td>`）；
  句子放在 `.e` 英文正文最前面（`<div class="e"><button class="spk">🔊</button>Good morning…</div>`）。
  **新增列会把 `nth-child` 序号全打乱，遮英文/遮中文全失效**——这是本次返工的根因。
- 读音内容显式写在 `data-say` 上，不要靠遍历 DOM 猜。
- 全局 `document` 点击代理里要加 `if(t.closest('.spk')) return;`
  否则点喇叭会顺带触发"点表格行揭开答案"和高亮 `hit` 逻辑。
- 按钮在打印时 `display:none`。

**排查教训**：诊断脚本注入用 `s.replace('</body>', inject+'</body>')` 会**同时命中 JS 字符串里的
`'</body></html>'`**，把主脚本整段写坏，表现为"按钮全部失灵 + SyntaxError"。
注入一律用 `s.rfind('</body>')` 定位最后一个再切。

### 8.23 一句话定位标题（2026-10-04 起沿用）

词汇表四组别再叫 "A/B/C/D"，改成带定位的：

- A 今天就能用（对着宝宝张口就来的词）
- B 新生儿照护词（看懂视频和育儿内容用）
- C 视频里其余的词（只出现一次，认识即可）
- **D 视频外场景拓展词汇（可选）** ← 原来的独立「拓展词汇」章节并入这里，别再单开一节。

### 8.24 系列化：一个应用 + 子目录（2026-10-05）

做到 10+ 篇时要转成**系列站**，不要一篇一个应用、更不要每篇单独发一次。

**为什么必须合并成一个应用（决定性理由）**：`localStorage` 按 **origin（协议+域名+端口）** 隔离，
**不按路径**。同一个应用里的 100 个子目录共享一份 localStorage →
打卡、收藏、复习清单可以**跨篇汇总**；拆成 100 个应用（100 个子域）则数据彻底隔离，永远汇总不起来。

**机制（必须如实告诉用户）**：线上内容 = **本地目录的完整快照**。

- 加新篇 = 本地目录加子目录 → 重新发布 → 线上 = 旧的全部 + 新的，**已有篇不会丢**。
- 但 sites **每次发布都是整包压缩重传**，不是增量 → 目录越大越慢。
- 最大风险是**本地目录丢失/不全**：本地只剩一篇时发布，线上就被覆盖成一篇。本地是唯一事实来源，要常备份。
- 静态发布**不占云服务应用名额、不耗资源点**（那是 cloud-service 的事：免费版 10 个应用 / 月 5000 资源点）。
  官方未公布静态发布的单应用体积上限；实测 14 MB 一次过。

**体积实测（1080p 原片 2 分钟，作为选参数的基线）**

| 档位 | 视频 | 单篇合计 | 100 篇 |
|---|---|---|---|
| 960p crf28 | 10.1 MB | 14.2 MB | 1.4 GB |
| 720p crf30 | 5.5 MB | 9.6 MB | 950 MB |
| 540p crf32 | 3.2 MB | 7.2 MB | 720 MB |
| 480p crf32 | 2.8 MB | 6.9 MB | 685 MB |

音频是固定大头（约 3.66 MB：full 1.5 + 9 段原声 + 9 段慢速），**视频才是要调的变量**。
规模到 30 篇以上（目录 >300 MB）时，正解是把 audio/ video/ 迁到对象存储（腾讯云 COS 几百 MB
一年几块钱），站点只留 HTML（100 篇 ≈ 8 MB），重传变成秒级；视频内容仍是用户自己的，不是外链 YouTube。

**目录结构**

    series/
      index.html                 ← 总目录：SERIES 数组渲染卡片 + 读进度 + 蓝色「怎么用」卡
      01-newborn-morning/
        index.html  audio/  img/  video/
      02-xxx/ …

- 子页 slug 用 `NN-english-slug`，别用中文目录名（URL 编码难看）。
- 卡片链接写 `01-newborn-morning/index.html`，**别只写目录名** —— `file://` 下点目录不会自动找 index。
- 总目录的 `SERIES` 数组就是唯一清单，加篇只改这一处。

**子页要加的两样**

1. 顶栏返回链接：`<a class="home" href="../index.html">← 系列目录</a>` 放进 `.brand` 里，打印时随 topbar 隐藏。
2. **进度上报 IIFE**（放在主脚本之后）：打卡变化时写
   `localStorage['xhs.progress.<slug>'] = {done,total,ts}`。
   **不要动原有的 `K_CHECK` / `xhs_route_v1` 逻辑**，只额外写一个汇总 key —— 零风险，
   也不会破坏用户已有的打卡记录。总目录读这个 key 就能画进度条。

**环境坑**：Bash 工具里 `python -m http.server 8732 ... &` 起的进程会在**该条命令结束时被回收**，
下一条命令里再 curl / chrome 就 `ERR_CONNECTION_REFUSED`。
起服务器和截图/冒烟**必须写在同一条命令**里。另外往文件里写含反引号的文本，
**不要塞进 `python -c "..."` 的双引号里**（bash 会把反引号当命令替换），改用 Edit 工具或脚本文件。

### 8.25 从「一篇篇手搓」到「模板 + JSON 生成器」（2026-10-05，规模化必备）

系列超过 3 篇就别再复制粘贴 HTML 了。工作区固定三个工具（都在 `tools/`）：

| 文件 | 作用 |
|---|---|
| `tools/make_shell.py` | 从**任意一篇已定稿的成品页**抽出通用外壳 → `tools/shell.html`（含 `__TITLE__` `__BRAND__` `__TOC__` `__BODY__` `__KEY_CHECK__` `__KEY_FAV__` `__SLUG__` `__LESSON_CN__` 占位符） |
| `tools/build_lesson.py` | 读 `tools/lessons/<slug>.json` → 渲染正文 → 写 `outputs/亲子英语/<slug>/index.html` |
| `tools/check_series.py` | 一次性校验整个系列：资源是否都存在、锚点是否都有 id、标签是否配平、七个 Part 是否齐全 |

**改版式只改两处**：`shell.html`（CSS/JS 骨架）和 `build_lesson.py`（各 Part 的渲染函数）。
**加一篇只写一个 JSON**（约 200 行内容：part1/part2/part3/part4/part5/part6/part7），
不用碰 HTML。这样"用户要求换样式"时，30 篇一起重新生成是**秒级**的。

**JSON 里的引号陷阱**：正文 EN 要带高亮 `<span class='k y' title='换尿布'>`，
HTML 属性一律用**单引号**，否则和 JSON 的双引号打架；tooltip 文本里别出现撇号。
JSON 里**不要写 JS 表达式**（曾误写 `"...".replace(...)` 导致整个文件不是合法 JSON）。

**转写：小模型比大模型快两个数量级，质量够用。**
本机 `medium` + `beam_size=5` + `word_timestamps=True` 跑 72 秒音频 **>17 分钟还没完**；
换 `small` + `beam_size=1` + `temperature=0` + `vad_filter` + `condition_on_previous_text=False`
只用了 **12 秒**，专有名词（scrotum / umbilical cord / breakdown）全对。
**默认走 small+beam1**，只有出现明显错词再补跑 medium。
配套技巧：`cpu_threads=4`、`print(..., flush=True)` 让后台任务能看到进度。

**视频自带中英字幕时，用「拼图」校对而不是 OCR**：把字幕条区域按固定间隔抽帧拼成一张图，
一次就能读完整个视频的字幕流，还能顺手发现视频里的 **Tip 卡片**（那种粉色小提示框）——
那是现成的高质量教学内容，直接做成段落里的「💡 视频里的提示」。
注意 Tip 卡片出现时间很短且纵向位置会浮动，抽帧间隔取 1 秒、裁 `ih*0.11` 高、从 `ih*0.705` 起最稳。
**视频里烧录的中文别直接用**——机器翻译（"你要确保阴囊在下面"），自己重译成自然中文。

**取段音频要按语义切，不要按转写句切**。转写可能把一句话拆到两段
（seg08 结尾 "be able to stick your fingers in easily" 其实是 seg07 的续句），
合并后段标题才站得住。规格照抄 01：full 44.1k/96k 单声道，段 16k/64k，慢速 `atempo=0.8`。

---

## 做视频硬经验（字幕烧录 / 转录 / 复核，2026-10 踩坑沉淀）

下面这些是「把视频做成带双语字幕的成片」时反复踩的坑，沉淀在此避免重犯
（字幕烧录引擎是 `bilingual-subtitles` skill，这里只记决策与坑，不重复它的全部参数）。

### 转录：VAD 必须关，且交付前必须逐句复核

- **`vad_filter=False`**：安静 / 短促 / 边玩边喊的台词，faster-whisper 默认 Silero VAD 会吞掉 85%+ 语音。
  **实测**：消防车1 首版开 VAD 只有 44 段、漏 10 行；关 VAD 后补齐到 58 段。
  判据看「整课文本 ↔ 转录」对齐覆盖率，低于 60% 就是被滤残了（用 `vadcheck.py` 两套对比取高的）。
- **逐句复核是硬要求**：用户对「最近错漏太多」明确不满，要求「以后都记得要检查一下」。
  交付前必须：① 用 PIL 直方图逐条抽帧查字幕亮像素（EN/CN 亮像素 >800、CN 以下遮罩外 ≤110）；
  ② 听辨一遍，重点看长句有没有被截、专名有没有听错。别只信转录自动对齐。

### 字幕烧录

- **字幕一律加粗**：用 `C:\Windows\Fonts\msyhbd.ttc`（Microsoft YaHei **Bold**），不要常规 `msyh.ttc`。
  用户对「忘记加粗」明确提过。
- **长英文换行到两行**：整句口播在 EN 62px 下常超 1920 帧宽（上限约 1800px），按**词边界贪心**拆两行，
  遮罩高度自适应（单行 194px / 2 行 266px，底部始终贴边）。儿歌 / 短句卡片单行即可。
  **两行英文用两条独立 drawtext、各自显式 y**（en_y1=832 / en_y2=910，遮罩 808/272）；
  **别在 textfile 里塞 `\n` 让 ffmpeg 自动换行**——第二行会掉到 CN 行上叠在一起。
- **每条视频末尾必须拼接「关注我」片尾**（约 1.416s），缺失即视为失败。
  片尾起点 ≈ 总时长 − 1.416s；抽帧校验用 `-sseof -0.7`（`-ss` 越过真实末尾会静默不生成文件）。
- **可复用渲染模块**：新视频只写一个 `render_xxx.py` 调 `bili.py` 的
  `render_subs(subs, src, preset, out_mp4, out_srt, box_op=0.92)`，
  `subs = (start, end, en, cn, two_line)`，`en` 里带 `\n` 即自动两行。一次调用完成
  烧字幕 → 预设重编码 H.264+AAC@44100 → `-c copy` concat 片尾 → 写 SRT（自动建目录）。
  **交付的 `.srt` 不要和成片 mp4 同目录同名**（播放器会叠成双重字幕）。
- **YouTube 取字幕现状（2026-09 验证）**：本机 IP 被 bot 拦截，yt-dlp 全 client 失败；
  兜底用 WebFetch 抓 `youtubetotranscript.com`（只给英文轨）。下载视频走
  `yt-dlp + player_client=web_safari + --concurrent-fragments 4 + Netscape cookies`（需新会话新鲜 cookies）。
