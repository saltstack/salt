@ echo off
Set "CurDir=%~dp0"
PowerShell -ExecutionPolicy RemoteSigned -File "%CurDir%\install_wix.ps1" %*
