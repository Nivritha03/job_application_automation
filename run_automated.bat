@echo off
title AI Job Agent - Fully Automated Mode
echo ==========================================================
echo Starting AI Job Agent in Fully Automated Mode...
echo Sequence: Naukri, Instahyre, Wellfound, Hirist, Cutshort, Indeed, Foundit, Glassdoor, LinkedIn, Greenhouse, Lever, Ashby, Workable
echo Search Keywords: Loaded from config.yaml
echo WARNING: This mode will submit real job applications!
echo ==========================================================
echo.
echo Running: python main.py --site all --location "india"
echo.
python main.py --site all --location "india" --ai
echo.
echo ==========================================================
echo Pipeline execution completed.
echo ==========================================================
pause
