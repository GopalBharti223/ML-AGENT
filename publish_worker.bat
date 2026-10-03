@echo off
rem ============================================================
rem  publish_worker.bat - Task-Scheduler-friendly wrapper for
rem  publish_worker.py (delayed publish: unlisted -> public).
rem
rem  Register to run every 3 minutes (run ONCE in a terminal):
rem
rem    schtasks /Create /TN "YouTube Publish Worker" /TR "d:\ML_AGENT\publish_worker.bat" /SC MINUTE /MO 3 /F
rem
rem  Or run as a self-looping daemon (checks every 120 s):
rem
rem    d:\ML_AGENT\publish_worker.bat --loop 120
rem
rem  NOTE: the interactive one-time OAuth consent per channel
rem  needs a visible console - run it directly instead:
rem
rem    d:\ML_AGENT\venv\Scripts\python.exe publish_worker.py --auth <channel>
rem ============================================================

cd /d d:\ML_AGENT

if not exist logs mkdir logs

"d:\ML_AGENT\venv\Scripts\python.exe" publish_worker.py %* >> "d:\ML_AGENT\logs\publish_worker.log" 2>&1
