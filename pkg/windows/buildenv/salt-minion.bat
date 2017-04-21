@ echo off
:: Script for starting the Salt-Minion
:: Accepts all parameters that Salt-Minion Accepts

:: Get current codepage, change codpage to Unicode
for /f "tokens=2 delims=:." %%x in ('chcp') do set cp=%%x
chcp 65001

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt-minion

:: Launch script
"%Python%" "%Script%" %*

:: Capture Python Error
Set PyError=%ERRORLEVEL%

:: Change codepage back
chcp %cp%

exit /B %PyError%