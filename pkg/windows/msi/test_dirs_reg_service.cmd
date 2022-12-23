@echo off
IF exist  "c:\salt\conf" (
echo      "c:\salt"
dir /b    "c:\salt"
echo      "c:\salt\conf"
dir /b /s "c:\salt\conf" )

IF exist  "C:\ProgramData\Salt Project\salt\conf" (
echo      "C:\ProgramData\Salt Project\salt\conf"
dir  /b   "C:\ProgramData\Salt Project\salt\conf" )

IF exist  "C:\Program Files (x86)\Salt Project\salt" (
echo      "C:\Program Files (x86)\Salt Project\salt"
dir  /b   "C:\Program Files (x86)\Salt Project\salt" )

IF exist  "C:\Program Files\Salt Project\salt" (
echo      "C:\Program Files\Salt Project\salt" 
dir /b    "C:\Program Files\Salt Project\salt" )

Reg Query "HKLM\SOFTWARE\Salt Project\salt"

sc query salt-minion
