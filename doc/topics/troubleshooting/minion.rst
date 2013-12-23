===============================
Troubleshooting the Salt Minion
===============================

Running in the Foreground
=========================

A great deal of information is available via the debug logging system, if you
are having issues with minions connecting or not starting run the minion in
the foreground:

.. code-block:: bash

  salt-minion -l debug

Anyone wanting to run Salt daemons via a process supervisor such as `monit`_,
`runit`_, or `supervisord`_, should omit the ``-d`` argument to the daemons and
run them in the foreground.

.. _`monit`: http://mmonit.com/monit/
.. _`runit`: http://smarden.org/runit/
.. _`supervisord`: http://supervisord.org/


What Ports does the Minion Need Open?
=====================================

No ports need to be opened up on each minion. If you've put both your Salt
master and minion in debug mode and don't see an acknowledgment that your
minion has connected, it could very well be a firewall.

You can check port connectivity from the minion with the nc command:

.. code-block:: bash

  nc -v -z salt.master.ip 4505
  nc -v -z salt.master.ip 4506

There is also a :doc:`firewall configuration</topics/tutorials/firewall>`
document that might help as well.

If you've enabled the right TCP ports on your operating system or Linux
distribution's firewall and still aren't seeing connections, check that no
additional access control system such as `SELinux`_ or `AppArmor`_ is blocking
Salt.

.. _`SELinux`: https://en.wikipedia.org/wiki/Security-Enhanced_Linux
.. _`AppArmor`: http://wiki.apparmor.net/index.php/Main_Page

Using salt-call
===============

The ``salt-call`` command was originally developed for aiding in the development
of new Salt modules. Since then, many applications have been developed for
running any Salt module locally on a minion. These range from the original
intent of salt-call, development assistance, to gathering more verbose output
from calls like :mod:`state.highstate <salt.modules.state.highstate>`.

When creating your state tree, it is generally recommended to invoke
:mod:`state.highstate <salt.modules.state.highstate>` with ``salt-call``. This
displays far more information about the highstate execution than calling it
remotely. For even more verbosity, increase the loglevel with the same argument
as ``salt-minion``:

.. code-block:: bash

    salt-call -l debug state.highstate

The main difference between using ``salt`` and using ``salt-call`` is that
``salt-call`` is run from the minion, and it only runs the selected function on
that minion. By contrast, ``salt`` is run from the master, and requires you to
specify the minions on which to run the command using salt's :doc:`targeting
system </topics/targeting/index>`.

Live Python Debug Output
========================

If the master seems to be unresponsive, a SIGUSR1 can be passed to
the processes to display where in the code they are running. If encountering a
situation like this, this debug information can be invaluable. First make
sure the minion is running in the foreground:

.. code-block:: bash

    salt-minion -l debug

Then pass the signal to the minion when it seems to be unresponsive:

.. code-block:: bash

    killall -SIGUSR1 salt-minion

When filing an issue or sending questions to the mailing list for a problem
with an unresponsive daemon this information can be invaluable.

