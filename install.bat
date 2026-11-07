@echo off
chcp 65001 >nul 2>&1
echo =========================================
echo  亲子英语 Skills 安装器 / Installer (Windows)
echo =========================================

set SCRIPT_DIR=%~dp0
set "SKILLS=yt-scene-finder bilingual-subtitles parent-english-html parent-english-netdisk video-english-xhs parent-english-pipeline"

rem ---- 1. 检测客户端目录（WorkBuddy / QoderWork 双兼容）----
set "SKILL_DIR="
if defined SKILL_TARGET set "SKILL_DIR=%SKILL_TARGET%"
if not defined SKILL_DIR if exist "%USERPROFILE%\.workbuddy" set "SKILL_DIR=%USERPROFILE%\.workbuddy\skills"
if not defined SKILL_DIR if exist "%USERPROFILE%\.qoderworkcn" set "SKILL_DIR=%USERPROFILE%\.qoderworkcn\skills"
if not defined SKILL_DIR set "SKILL_DIR=%USERPROFILE%\.workbuddy\skills"

echo.
echo Skills 目标目录 / Target: %SKILL_DIR%
echo （可用 SKILL_TARGET 环境变量覆盖 / override with SKILL_TARGET）

echo.
echo [1/5] 复制 6 个 skills / Copying 6 skills...
if not exist "%SKILL_DIR%" mkdir "%SKILL_DIR%"

for %%S in (%SKILLS%) do (
    if exist "%SCRIPT_DIR%skills\%%S" (
        xcopy /E /I /Y "%SCRIPT_DIR%skills\%%S" "%SKILL_DIR%\%%S\" >nul 2>&1
        echo   [OK] %%S
    ) else (
        echo   [!!] %%S not found, skipping
    )
)

echo.
echo [2/5] 检查 Python / Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   [!!] Python 未安装，请从 python.org 下载
    echo        Python not found. Download from python.org
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   [OK] %%v

echo.
echo [3/5] 检查 ffmpeg / Checking ffmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo   [!!] ffmpeg 未安装
    echo        ffmpeg not found
    echo        安装方式 / Install via:
    echo          winget install ffmpeg
    echo          或 / or: choco install ffmpeg
    echo          或 / or: https://ffmpeg.org/download.html
    exit /b 1
)
echo   [OK] ffmpeg found

echo.
echo [4/5] 安装 Python 依赖 / Installing Python packages...
pip install -r "%SCRIPT_DIR%requirements.txt" --quiet
echo   [OK] faster-whisper, Pillow, yt-dlp, PyYAML

echo.
echo [5/5] 检查 lark-cli / Checking lark-cli...
set LARK_CLI=%USERPROFILE%\.qoderworkcn\bin\lark-cli.cmd
if exist "%LARK_CLI%" (
    echo   [OK] lark-cli found
) else (
    echo   [!!] lark-cli 未找到（可选，用于飞书文档）
    echo        lark-cli not found (optional, for Feishu docs)
    echo        安装 / Install: npm install -g @anthropic/lark-cli
)

echo.
if not exist "%SCRIPT_DIR%config.yaml" (
    copy "%SCRIPT_DIR%config.example.yaml" "%SCRIPT_DIR%config.yaml" >nul
    echo [OK] 已创建 config.yaml，请编辑为你的实际路径
) else (
    echo [OK] config.yaml 已存在，跳过
)

echo.
echo =========================================
echo  OK 安装完成 / Installation complete!
echo =========================================
echo.
echo Skills: %SKILL_DIR%
echo.
echo 下一步 / Next:
echo   1. 编辑 config.yaml 设置片尾视频 / 字体 / cookie
echo   2. 编辑 skills\parent-english-pipeline\config.yaml，把所有 ^<...^> 占位符换成本机实际值
echo   3. 在客户端中用 @skill:^<name^> 触发
echo.
pause
