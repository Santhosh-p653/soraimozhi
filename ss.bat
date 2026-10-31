@echo off
:: Strands-Ship launcher for Windows (project-local shortcut).
:: Delegates to the installed kit at %USERPROFILE%\.strands-ship\bin\ss.bat
:: Run this from inside the strands-ship-agent folder.

set "SS=%USERPROFILE%\.strands-ship\bin\ss.bat"

if not exist "%SS%" (
    echo [ERROR] strands-ship is not set up yet.
    echo Run setup first:
    echo   python e:\aws\strands-ship\skills\ship-setup\scripts\ship_windows.py setup
    exit /b 1
)

call "%SS%" %*
