===============================
Troubleshooting the Salt Minion
===============================

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


.. _using-salt-call:
