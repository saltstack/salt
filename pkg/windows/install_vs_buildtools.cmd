@ echo off
Set "CurDir=%~dp0"
PowerShell -ExecutionPolicy RemoteSigned -File "%CurDir%\install_vs_buildtools.ps1" %*
