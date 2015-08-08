@echo off
set opts="-oStrictHostKeyChecking=no -oPasswordAuthentication=no -oKbdInteractiveAuthentication=no -oChallengeResponseAuthentication=no"
if "%GIT_IDENTITY%" == "" goto NOIDENT
set opts="%opts% -i %GIT_IDENTITY%"
:NOIDENT

%GIT_SSH% %opts% %*
