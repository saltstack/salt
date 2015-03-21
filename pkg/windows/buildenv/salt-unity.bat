@ echo off
:: Script for starting the Salt-Minion
:: Accepts all parameters that Salt-Minion Accepts

:: Define Variables
Set Python="%cd%\bin\python.exe"
Set Script="%cd%\bin\Scripts\salt-unity"

"%Python%" "%Script%" %*
