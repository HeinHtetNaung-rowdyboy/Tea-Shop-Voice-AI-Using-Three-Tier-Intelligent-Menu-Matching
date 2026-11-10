@echo off
cd /d "%~dp0"
if not exist .env copy .env.example .env
if not exist .venv py -3.11 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
start "Tea Shop API" cmd /k "call .venv\Scripts\activate.bat && uvicorn api:app --host 127.0.0.1 --port 8000"
start "Tea Shop Streamlit" cmd /k "call .venv\Scripts\activate.bat && streamlit run streamlit_app.py"
echo Two windows started. Edit .env passwords and Raj URL before real use.
