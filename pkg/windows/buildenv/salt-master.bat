@ echo off
:: Script for starting the Salt-Master
:: Accepts all parameters that Salt-Master accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Binary=%SaltDir%\bin\Scripts\salt-master.exe

:: Launch binary
"%Binary%" %*
