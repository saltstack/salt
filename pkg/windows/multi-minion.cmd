:: This is a helper script for multi-minion.ps1.
:: See multi-minion.ps1 for documentation
@ echo off
Set "CurDir=%~dp0"
PowerShell -ExecutionPolicy RemoteSigned -File "%CurDir%\multi-minion.ps1" %*
