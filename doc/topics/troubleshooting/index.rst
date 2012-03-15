===============
Troubleshooting
===============

The intent of the  troubleshooting section is to introduce solutions to a
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
intent of the salt-call, development assistance, to gathering large amounts of
data from complex calls like state.highstate.

When developing the state tree it is generally recommended to invoke
state.highstate with salt-call, this displays a great deal more information
about the highstate execution than if it is called remotely.

Too many open files
===================

The salt-master needs at least 2 sockets per host that connects to it, one for
the Publisher and one for response port. Thus, large installations may upon
scaling up the number of minions accessing a given master, encounter:

        12:45:29,289 [salt.master    ][INFO    ] Starting Salt worker process 38
        Too many open files
        sock != -1 (tcp_listener.cpp:335)

The solution to this would be to check the number of files allowed to be
opened by the user running salt-master (root by default):

        [root@salt-master ~]# ulimit -n
        1024

And modify that value to be at least equal to the number of minions x 2.
This setting can be changed in limits.conf as the nofile value(s),
and activated upon new a login of the specified user.

So, an environment with 1800 minions, would need 1800 x 2 = 3600 as a minimum
