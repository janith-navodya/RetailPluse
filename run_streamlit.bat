@echo off
title RetailPulse Decision Intelligence Portal
cd /d "%~dp0"
echo ===============================================================================
echo            Launching RetailPulse Decision Intelligence Portal
echo ===============================================================================
echo Activating virtual environment and starting Streamlit...
call "%~dp0.venv\Scripts\activate.bat"
streamlit run app.py
pause
