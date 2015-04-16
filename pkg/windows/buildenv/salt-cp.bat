@ echo off
:: Script for starting the Salt-Minion
:: Accepts all parameters that Salt-Minion Accepts

:: Define Variables
Set SaltInstallDir=%~dp0
Set Python="%SaltInstallDir%bin\python.exe"
Set Script="%SaltInstallDir%bin\Scripts\salt-cp"

%Python% %Script% %*
