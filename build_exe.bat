@echo off
cd /d %~dp0
echo ============================================
echo   Build launcher exe (build.py)
echo ============================================
where py >nul 2>&1
if not errorlevel 1 (
    py -3 build.py
    goto :done
)
where python >nul 2>&1
if not errorlevel 1 (
    python build.py
    goto :done
)
echo [ERROR] Python not found.
echo Please install Python 3.9+ from https://www.python.org/downloads/
:done
echo.
pause