@ echo off
:: Script for invoking salt-key
:: Accepts all parameters that salt-key accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt-key

"%Python%" "%Script%" %*
