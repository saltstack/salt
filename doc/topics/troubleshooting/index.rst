===============
Troubleshooting
===============

The intent of the  troubleshootign secion is to introduce solutions to a 
number of common issues encountered by users and the tools that are available
to aid in developing states and salt code.

Running in the Foreground
=========================

A great deal of information is available via the debug logging system, if you
are having issues with minions connecting or not starting run the minion and/or
master in the foreground:

  # salt-master -l debug
  # salt-minion -l debug


Using salt-call
===============

The salt-call command was originally developed for aiding in the development
of new salt modules. Since then many applications have arisen for the salt-call
command that is bundled with the salt minion. These range from the original
intent of the salt-call, developmetn assistance, to gathering large amounts of
data from complex calls like state.highstate.

When developing the state tree it is geenrally recommended to invoke
state.highstate with salt-call, this displays a great deal more information
about the highstate execution then if it is called remotely.


