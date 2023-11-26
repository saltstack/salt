@ echo off
Set "CurDir=%~dp0"
PowerShell -ExecutionPolicy RemoteSigned -File "%CurDir%\setup.ps1" %*
