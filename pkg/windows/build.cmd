@ echo off
Set "CurDir=%~dp0"
PowerShell -ExecutionPolicy RemoteSigned -File "%CurDir%\build.ps1" %*
