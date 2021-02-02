@echo off
REM cd with /d (?)
cd /d "%~dp0"
python bp_to_imgV2.py %1
pause