@echo off
REM TaskManager — Windows launcher
REM Open a terminal in this directory and run: run.bat

cd /d "%~dp0"

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Set Flask app
set FLASK_APP=app:create_app

REM Run the server
flask run --host 0.0.0.0 --port 5001
