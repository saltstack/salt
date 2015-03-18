:: Remove all Compiled Python files (.pyc)
del /S /Q .\bin\*.pyc

:: Delete Unused Docs and Modules
rd /S /Q .\bin\Doc
rd /S /Q .\bin\share
rd /S /Q .\bin\tcl
rd /S /Q .\bin\Lib\idlelib
rd /S /Q .\bin\Lib\lib-tk
rd /S /Q .\bin\Lib\test
rd /S /Q .\bin\Lib\unit-test

:: Delete Unused .dll files
del /S /Q .\bin\DLLs\tcl85.dll
del /S /Q .\bin\DLLs\tclpip85.dll
del /S /Q .\bin\DLLs\tk85.dll

:: Delete .txt files
del /q .\bin\NEWS.txt
del /q .\bin\README.txt
