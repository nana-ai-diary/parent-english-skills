@echo off
chcp 65001 >nul
setlocal
set "PY=<PYTHON_EXE>"
set "PE=%~dp0scripts\pe.py"
if not exist "%PY%" (
  echo [ERROR] Python not found: %PY%
  exit /b 1
)
if not exist "%PE%" (
  echo [ERROR] pe.py not found: %PE%
  exit /b 1
)
"%PY%" -B "%PE%" %*
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
