@echo off
title AI Job Agent - Fresh Automated Mode
echo ==========================================================
echo Resetting local database to clear retries and starting fresh run...
echo Sequence: Naukri -> Instahyre -> Wellfound -> Hirist -> Cutshort -> Indeed -> Foundit -> Glassdoor -> LinkedIn -> ATS Boards
echo ==========================================================
echo.
if exist jobs.db (
    del jobs.db
    echo Database cleared successfully.
)
python -c "from core.database import init_db; init_db()"
echo.
python main.py --site all --location "india"
pause
