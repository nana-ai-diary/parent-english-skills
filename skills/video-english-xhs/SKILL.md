---
name: video-english-xhs
description: 从视频中提取核心英语词汇和实用句型，生成小红书/抖音视频配文和评论区置顶信息，并自动创建飞书文档整理完整笔记。当用户发送视频并要求提取英语学习内容、生成抖音帖子、整理视频英语笔记、做飞书文档时使用。Extract core English vocabulary and practical sentences from videos, generate Xiaohongshu/Douyin post captions and pinned comments, and auto-create Feishu docs with complete study notes. Use when extracting English learning content from videos or creating social media posts.
version: 5.2.0
---

# 视频英语 → 抖音配文 + 置顶评论

收到视频后，严格按以下流程执行。直接产出结果，不要反复确认。

## Step 1: 转录视频

```bash
# 使用专用虚拟环境的 Python（依赖已隔离安装，勿用全局 python）
"{VENV_PY}" "{SKILL_DIR}/scripts/transcribe.py" "视频路径"
```

> `{VENV_PY}` = 安装时为这些依赖单独创建的 venv 里的 python，
> 例如 Linux/macOS `~/.venvs/parent-english/bin/python`、
> Windows `%USERPROFILE%\.venvs\parent-english\Scripts\python.exe`。
> 具体路径取决于安装方式，以本机实际为准。

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
> 且必须确认 lark-cli 已在本 skill 的 `config.example.yaml`
> 的 `lark_cli` 字段中配置（值为空则跳过并说明原因）。

用户明确要求后，才创建飞书文档整理完整学习笔记。

### 6.0 前置：确认 lark-cli 版本 ≥ 1.0.96（否则颜色全丢）

```bash
lark-cli --version          # < 1.0.96 必须升级
lark-cli update --check --json   # 查最新版本
```

**⚠️ `lark-cli update` 对本机这种 shim 安装无效**：`--check` 会返回 `"auto_update": false`，
`update` 命令只是打印 GitHub Release URL，不会下载，表现为**长时间挂起无输出**（实测两次各卡 8 分钟）。
另外它可能继承了某个**访问不了 GitHub 的代理环境变量**（常见于各类沙箱 / IDE 内置代理），
表现同样是卡住——升级前先 `echo $HTTPS_PROXY` 确认，必要时显式指定你能出外网的那一个。

**正确的手动升级方式**（实测成功）：

```bash
# 1. 下载 Windows 版（14.7MB；{PROXY} 换成你本机可出外网的代理，无需代理则去掉该前缀）
HTTPS_PROXY={PROXY} python -c "
import urllib.request, zipfile
url='https://github.com/larksuite/cli/releases/download/v1.0.96/lark-cli-1.0.96-windows-amd64.zip'
req=urllib.request.Request(url, headers={'User-Agent':'curl/8'})
open('lark-new.zip','wb').write(urllib.request.urlopen(req, timeout=600).read())
zipfile.ZipFile('lark-new.zip').extract('lark-cli.exe', 'lark-new')
"
# 2. 备份并替换（替换前先杀掉所有 lark 进程）
#    备份：安装目录下的 lark-cli-core-windows-amd64.exe
#          （常见于 ~/.qoderworkcn/bin/ext/ 一类安装目录，以本机实际为准）→ 同目录 .bak-v45
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

> 下文 `{LARK_CLI}` = `config.example.yaml` 里 `lark_cli` 字段的值（lark-cli 可执行文件路径）。
> **该字段为空 = 用户没启用飞书，跳过整个 Step 6 并说明原因。**

```bash
# 写标题到临时文件
echo '<title>主题名</title>' > doc_title.xml
# 必须在文件所在目录执行，用 @文件名 传入内容
cd "工作目录"
{LARK_CLI} docs +create --api-version v2 --content "@doc_title.xml"
```

从返回的 JSON 中提取 `document_id` 和 `url`。

### 6.3 写入内容

把所有板块内容写成 **一个 XML 文件**（`doc_content.xml`），然后一次性写入。

> ⚠️ 必须用 `--doc-format xml`，**不能用 markdown** —— markdown 解析器不支持颜色，
> 会把 `<span background-color>` 全部剥掉（见【原文及译文】的高亮规则）。

```bash
cd "工作目录"
{LARK_CLI} docs +update --api-version v2 --doc "文档token" --command overwrite --doc-format xml --content "@doc_content.xml"
```

> 用 `overwrite` 而不是 `append`：append 会在旧内容后重复堆叠，改版时整篇重刷最干净。
> 代价是 overwrite 会清掉已插入的图片（见【主题图】）。

**文档结构（按顺序）：**

#### 【主题图】
插入封面图（cd 到图片所在目录，用相对路径）：
```bash
cd "图片所在目录"
{LARK_CLI} docs +media-insert --doc "文档token" --file "cover.jpg"
```

> 实践验证（2026-09-24）：用 `overwrite` 重写文档会**清掉已插入的封面图**，必须重新 `+media-insert`。
> 重新插入时图片会落在**文档末尾**，此时把 `--block-id` 直接填**文档根块 id（= 文档 token）**，
> 即可把它移到最前面（标题之后、正文之前）：
> `{LARK_CLI} docs +update --api-version v2 --doc <token> --command block_move_after --block-id <token> --src-block-ids <图片block_id>`

#### 【来源】
封面图之后，正文之前。先写占位，等用户发回链接和博主名称后再更新：

```xml
<h2>来源</h2>
<p>视频链接：待补充</p>
<p>油管博主：待补充</p>
```

用户发回链接和博主名称后，用 `str_replace` 更新：
```bash
{LARK_CLI} docs +update --api-version v2 --doc "文档token" --command str_replace --pattern "视频链接：待补充" --content '视频链接：<a href="链接URL">链接标题</a>'
{LARK_CLI} docs +update --api-version v2 --doc "文档token" --command str_replace --pattern "油管博主：待补充" --content "油管博主：@博主名称"
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
> 升级到 1.0.96 后颜色正常写入。实测枚举值：`text_color` red=1 / green=4 / blue=5，
> `background_color` light-yellow=3。（`text-color` 也能写，但定稿样式不用，见下）
>
> **两个必须知道的坑：**
> 1. `docs +fetch` 返回的 XML **不带 span 颜色**（输出是简化的），不要用它判断颜色是否生效。
>    验证要用：`lark-cli api GET "/open-apis/docx/v1/documents/{doc}/blocks/{block_id}"`，
>    看 `text.elements[].text_run.text_element_style` 里的 `text_color` / `background_color`。
> 2. 新版 CLI **移除了 `--new-title`**，标题必须通过 XML 的 `<title>` 设置，否则报 invalid_argument。
>
> 颜色语法（写入用 XML，不是 markdown —— markdown 不支持颜色）：
> ```xml
> <p>Let's take off your <b><span background-color="light-yellow">shoe</span></b>.</p>
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
- 句子里的固定短语搭配用 `<b><span background-color="light-green">...</span></b>` 高亮（同【原文及译文】规则）
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
- **使用 XML 格式写入**（`--doc-format xml`），不是 markdown
- 每个板块之间用 `<hr/>` 分隔
- 序号、结构清晰
- 重点词汇和句型必须遵从视频原文
- XML 转义：正文里的 `&` 写 `&amp;`，`<` 写 `&lt;`
- 表格用 `<table><tr><td>...</td></tr></table>` 语法
- **末尾不要放图片**（封面图放标题下方即可）

### 6.5 补充来源信息

文档创建完成后，提醒用户：
1. 把**小红书/抖音帖子链接**发回来（用于填充【来源】的视频链接）
2. 把**油管博主名称**发回来（如 @JoyeMusic.com，用于填充【来源】的博主）

用户发回后，用 `str_replace` 替换文档中的占位文本（见上方【来源】section 的更新命令）。

## 输出方式（完整流程）

1. 保存抖音配文为 `.txt` 文件，文件名：`xhs_[视频主题关键词].txt`
2. 展示配文内容 + 飞书文档 URL
3. **提醒用户**：
   - 发布视频后把小红书/抖音帖子链接发回来，补充到飞书文档【来源】
   - 把油管博主名称发回来（如 @JoyeMusic.com）
