@ echo off
:: Script for invoking Salt Main
:: Accepts all parameters that Salt Main accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt

:: Set PYTHONPATH
Set PYTHONPATH=C:\salt\bin;C:\salt\bin\Lib\site-packages

:: Launch Script
"%Python%" "%Script%" %*

