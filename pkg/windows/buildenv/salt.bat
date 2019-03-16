@ echo off
:: Script for starting the Salt CLI
:: Accepts all parameters that Salt CLI accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt

:: Launch Script
"%Python%" -E -s "%Script%" %*
