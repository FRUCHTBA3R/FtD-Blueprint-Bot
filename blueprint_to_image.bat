@echo off
REM cd with /d (?)
cd /d "%~dp0"
python bp_to_img.py %1
pause