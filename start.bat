@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0VideoSegmentLabeler.exe" (
    echo VideoSegmentLabeler.exe was not found next to this script.
    echo Keep start.bat in the packaged VideoSegmentLabeler folder.
    pause
    exit /b 1
)

start "" /d "%CD%" "%~dp0VideoSegmentLabeler.exe"
endlocal
