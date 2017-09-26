@ echo off
:: Script for starting the Salt-Minion
:: Accepts all parameters that Salt-Minion Accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt-minion

:: Stop the Salt Minion service
net stop salt-minion

:: Launch Script
"%Python%" -E -s "%Script%" -l debug
