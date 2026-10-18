@echo off

echo ==============================
echo 🤖 BOT STARTED
echo ==============================

REM Go to your folder
cd /d  "C:\Power_automate\robot-main"

REM Run Python script
python recruit_manual.py

echo ==============================
echo ✅ BOT FINISHED
echo ==============================

exit

