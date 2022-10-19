@ echo off
:: Script for starting the Salt-Minion
:: Accepts all parameters that Salt-Minion Accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Binary=%SaltDir%\bin\Scripts\salt-cp.exe

:: Launch binary
"%Binary%" %*
