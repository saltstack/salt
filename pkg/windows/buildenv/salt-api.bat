@ echo off
:: Script for starting the Salt-Api
:: Accepts all parameters that Salt-Api accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt-api

:: Launch Script
"%Python%" -E -s "%Script%" %*
