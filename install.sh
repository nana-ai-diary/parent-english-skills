#!/usr/bin/env bash
# ============================================================
# 亲子英语 Skills 一键安装脚本 / Parent English Skills Installer
# macOS / Linux
set -e

echo "========================================="
echo " 亲子英语 Skills 安装器 / Installer"
echo "========================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS="yt-scene-finder bilingual-subtitles parent-english-html parent-english-netdisk video-english-xhs parent-english-pipeline"

# ---- 1. 检测客户端目录（WorkBuddy / QoderWork 双兼容）----
if [ -n "$SKILL_TARGET" ]; then
    SKILL_DIR="$SKILL_TARGET"
elif [ -d "$HOME/.workbuddy" ]; then
    SKILL_DIR="$HOME/.workbuddy/skills"
elif [ -d "$HOME/.qoderworkcn" ]; then
    SKILL_DIR="$HOME/.qoderworkcn/skills"
else
    SKILL_DIR="$HOME/.workbuddy/skills"
fi

echo ""
echo "Skills 目标目录 / Target: $SKILL_DIR"
echo "（可用 SKILL_TARGET 环境变量覆盖 / override with SKILL_TARGET）"

echo ""
echo "[1/5] 复制 6 个 skills / Copying 6 skills..."
mkdir -p "$SKILL_DIR"

for skill in $SKILLS; do
    if [ -d "$SCRIPT_DIR/skills/$skill" ]; then
        mkdir -p "$SKILL_DIR/$skill"
        cp -r "$SCRIPT_DIR/skills/$skill/." "$SKILL_DIR/$skill/"
        echo "  ✓ $skill"
    else
        echo "  ⚠ $skill not found, skipping"
    fi
done

# ---- 2. 检查 Python ----
echo ""
echo "[2/5] 检查 Python / Checking Python..."
if command -v python3 &>/dev/null; then
    echo "  ✓ Python $(python3 --version)"
else
    echo "  ✗ Python 未安装 / not found"
    echo "    macOS: brew install python3"
    echo "    Linux: sudo apt install python3 python3-pip"
    exit 1
fi

# ---- 3. 检查 ffmpeg ----
echo ""
echo "[3/5] 检查 ffmpeg / Checking ffmpeg..."
if command -v ffmpeg &>/dev/null; then
    echo "  ✓ ffmpeg $(ffmpeg -version 2>&1 | head -1)"
else
    echo "  ffmpeg 未安装，正在安装 / not found, installing..."
    if command -v brew &>/dev/null; then
        brew install ffmpeg
    elif command -v apt &>/dev/null; then
        sudo apt update && sudo apt install -y ffmpeg
    else
        echo "  ✗ 请手动安装 ffmpeg / Please install ffmpeg manually"
        echo "    https://ffmpeg.org/download.html"
        exit 1
    fi
    echo "  ✓ ffmpeg installed"
fi

# ---- 4. 安装 Python 依赖 ----
echo ""
echo "[4/5] 安装 Python 依赖 / Installing Python packages..."
pip3 install -r "$SCRIPT_DIR/requirements.txt" --quiet
echo "  ✓ faster-whisper, Pillow, yt-dlp, PyYAML"

# ---- 5. 检查 lark-cli（可选）----
echo ""
echo "[5/5] 检查 lark-cli（飞书文档用）/ Checking lark-cli (for Feishu docs)..."
LARK_CLI="$HOME/.qoderworkcn/bin/lark-cli"
if [ -x "$LARK_CLI" ] || command -v lark-cli &>/dev/null; then
    echo "  ✓ lark-cli found"
else
    echo "  ⚠ lark-cli 未找到（可选，用于创建飞书文档）"
    echo "    lark-cli not found (optional, for Feishu doc creation)"
    echo "    安装 / Install: npm install -g @anthropic/lark-cli"
    echo "    或下载 QoderWork 桌面应用自带"
fi

# ---- 6. 创建配置文件 ----
echo ""
if [ ! -f "$SCRIPT_DIR/config.yaml" ]; then
    cp "$SCRIPT_DIR/config.example.yaml" "$SCRIPT_DIR/config.yaml"
    echo "[✓] 已创建 config.yaml，请编辑为你的实际路径"
    echo "    Created config.yaml — please edit with your actual paths"
else
    echo "[✓] config.yaml 已存在，跳过"
    echo "    config.yaml exists, skipping"
fi

# ---- 完成 ----
echo ""
echo "========================================="
echo " ✅ 安装完成 / Installation complete!"
echo "========================================="
echo ""
echo "Skills 已安装到 / Installed to: $SKILL_DIR"
echo ""
echo "下一步 / Next steps:"
echo "  1. 编辑 config.yaml 设置片尾视频 / 字体 / cookie"
echo "  2. 编辑 skills/parent-english-pipeline/config.yaml，把所有 <...> 占位符换成本机实际值"
echo "  3. 在客户端中用 @skill:<name> 触发；编排层用 @skill:parent-english-pipeline"
echo ""
echo "其他 Agent / Other agents:"
echo "  Claude Code: 读取本仓库的 AGENTS.md"
echo "               Read AGENTS.md in this repo"
echo "  Codex:       同上"
echo ""
