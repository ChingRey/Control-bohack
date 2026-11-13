@echo off
cd /d "%~dp0"
start "" http://127.0.0.1:8772
python -X utf8 backend.py --port 8772
pause
