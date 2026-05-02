@echo off
setlocal
set PATH=%~dp0bin;%~dp0bin\Scripts;%PATH%
echo Starting Data_Flow Application...
bin\python.exe -m streamlit run app.py
pause
