===============================
Troubleshooting the Salt Master
===============================


What Ports does the Master Need Open?
=====================================

For the master, TCP ports 4505 and 4506 need to be open. If you've put both
your Salt master and minion in debug mode and don't see an acknowledgment
that your minion has connected, it could very well be a firewall.

There is also a :doc:`firewall configuration</topics/tutorials/firewall>`
document that might help as well.

If you've enabled the right TCP ports on your operating system or Linux
distribution's firewall and still aren't seeing connections, check that no
additional access control system such as `SELinux`_ or `AppArmor`_ is blocking
Salt.

.. _`SELinux`: https://en.wikipedia.org/wiki/Security-Enhanced_Linux
   .. _`AppArmor`: http://wiki.apparmor.net/index.php/Main_Page


.. _using-salt-call:
