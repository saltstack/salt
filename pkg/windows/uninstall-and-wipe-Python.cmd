@echo off

:: uninstall Python 2.7 64bit
MsiExec.exe /X {16E52445-1392-469F-9ADB-FC03AF00CD62} /QN

:: wipe the Python directory
::  DOS hack first create dir because Windows cannot test not existing without error message
md c:\Python27  1>nul 2>nul
rd /s /q c:\Python27 || echo Failure: c:\Python27 still exists, please find out why and repeat.
