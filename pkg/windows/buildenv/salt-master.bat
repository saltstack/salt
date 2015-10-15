@ echo off
:: Script for starting the Salt-Master
:: Accepts all parameters that Salt-Master accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt-master

"%Python%" "%Script%" %*
