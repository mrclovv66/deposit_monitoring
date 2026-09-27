@echo off

cd /d D:\Desktop\deposit_monitor

call .venv\Scripts\activate.bat

python weekly_job.py

exit