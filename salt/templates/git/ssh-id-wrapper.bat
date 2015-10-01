@echo off
set opts=-oStrictHostKeyChecking=no -oPasswordAuthentication=no -oKbdInteractiveAuthentication=no -oChallengeResponseAuthentication=no
if "%GIT_IDENTITY%" == "" goto NOIDENT
set ident=-oIdentityFile='%GIT_IDENTITY%'
:NOIDENT
"%GIT_SSH_EXE%" %opts% %ident% %*
