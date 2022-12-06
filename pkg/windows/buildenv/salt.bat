@ echo off
:: Script for starting the Salt CLI
:: Accepts all parameters that Salt CLI accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Binary=%SaltDir%\bin\Scripts\salt.exe

:: Launch binary
"%Binary%" %*
