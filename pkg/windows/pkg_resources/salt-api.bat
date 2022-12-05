@ echo off
:: Script for starting the Salt-Api
:: Accepts all parameters that Salt-Api accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Binary=%SaltDir%\bin\Scripts\salt-api.exe

:: Launch binary
"%Binary%" %*
