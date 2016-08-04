@echo off

:: uninstall Python 2.7.12 64bit
MsiExec.exe /X {9DA28CE5-0AA5-429E-86D8-686ED898C666} /QN

:: wipe the Python directory
::  DOS hack first create dir because Windows cannot test not existing without error message
md c:\Python27  1>nul 2>nul
rd /s /q c:\Python27 || echo Failure: c:\Python27 still exists, please find out why and repeat.
