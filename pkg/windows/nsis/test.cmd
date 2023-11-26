@ echo off
Set "CurDir=%~dp0"
PowerShell -ExecutionPolicy RemoteSigned -File "%CurDir%\tests\test.ps1" %*
