@ echo off
:: Script for starting the Salt-Minion
:: Accepts all parameters that Salt-Minion Accepts

:: Define Variables
Set Python=%~dp0bin\python.exe
Set Script=%~dp0bin\Scripts\salt-unity

"%Python%" "%Script%" %*
