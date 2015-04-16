net stop salt-minion

Set SaltInstallDir=%~dp0
Set Python="%SaltInstallDir%bin\python.exe"
Set Script="%SaltInstallDir%bin\Scripts\salt-minion"

%Python% %Script% -l debug -c "%SaltInstallDir%conf"
