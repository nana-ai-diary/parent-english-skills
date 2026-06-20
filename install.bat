@echo off
chcp 65001 >nul 2>&1
echo =========================================
echo  亲子英语 Skills 安装器 / Installer (Windows)
echo =========================================

set SCRIPT_DIR=%~dp0
set SKILL_DIR=%USERPROFILE%\.qoderworkcn\skills

echo.
echo [1/5] 复制 skills / Copying skills...
if not exist "%SKILL_DIR%" mkdir "%SKILL_DIR%"

for %%S in (bilingual-subtitles video-english-xhs yt-scene-finder) do (
    if exist "%SCRIPT_DIR%skills\%%S" (
        xcopy /E /I /Y "%SCRIPT_DIR%skills\%%S" "%SKILL_DIR%\%%S" >nul 2>&1
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
echo   [OK] faster-whisper, Pillow, yt-dlp

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
    echo [OK] config.yaml 已存在
)

echo.
echo =========================================
echo  OK 安装完成 / Installation complete!
echo =========================================
echo.
echo Skills: %SKILL_DIR%
echo.
echo 下一步 / Next:
echo   1. 编辑 config.yaml 设置路径
echo   2. 重启 QoderWork 或 Claude Code 即可使用
echo.
pause
