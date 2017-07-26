@ echo off
:: Script for starting the Salt-Master
:: Accepts all parameters that Salt-Master accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt-master

:: Set PYTHONPATH
Set PYTHONPATH=C:\salt\bin;C:\salt\bin\Lib\site-packages

:: Launch Script
"%Python%" "%Script%" %*

