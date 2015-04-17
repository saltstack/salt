@ echo off
:: Script for starting the Salt-Minion
:: Accepts all parameters that Salt-Minion Accepts

:: Define Variables
Set Python="%~dp0\bin\python.exe"
Set Script="%~dp0\bin\Scripts\salt-cp"

"%Python%" "%Script%" %*
