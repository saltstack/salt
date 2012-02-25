==================================
Fedora & Enterprise Linux / CentOS
==================================

We are working to get Salt packages into EPEL. In the meantime you can ``yum
install salt-master salt-minion`` via our Fedora People repository.

Red Hat Enterprise Linux 5 & 6 or CentOS 5 & 6
----------------------------------------------

1.  Install the `EPEL`__ repository.

2.  Install our repository on FedoraPeople::

        wget -O /etc/yum.repos.d/epel-salt.repo \\
            http://repos.fedorapeople.org/repos/herlo/salt/epel-salt.repo

.. __: http://fedoraproject.org/wiki/EPEL#How_can_I_use_these_extra_packages.3F

Fedora 15 & 16
--------------

1.  Install our repository on FedoraPeople::

        wget -O /etc/yum.repos.d/fedora-salt.repo \\
            http://repos.fedorapeople.org/repos/herlo/salt/fedora-salt.repo
