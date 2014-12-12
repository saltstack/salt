===============
State Providers
===============

.. versionadded:: 0.9.8

Salt predetermines what modules should be mapped to what uses based on the
properties of a system. These determinations are generally made for modules
that provide things like package and service management.

Sometimes in states, it may be necessary to use an alternative module to
provide the needed functionality. For instance, an older Arch Linux system may
not be running systemd, so instead of using the systemd service module, you can
revert to the default service module:

.. code-block:: yaml

    httpd:
      service.running:
        - enable: True
        - provider: service

In this instance, the basic :py:mod:`~salt.modules.service` module (which
manages :program:`sysvinit`-based services) will replace the
:py:mod:`~salt.modules.systemd` module which is used by default on Arch Linux.

However, if it is necessary to make this override for most or every service,
it is better to just override the provider in the minion config file, as
described in the section below.

Setting a Provider in the Minion Config File
============================================

.. _`issue tracker`: https://github.com/saltstack/salt/issues

Sometimes, when running Salt on custom Linux spins, or distribution that are derived
from other distributions, Salt does not successfully detect providers. The providers
which are most likely to be affected by this are:

- pkg
- service
- user
- group

When something like this happens, rather than specifying the provider manually
in each state, it easier to use the :conf_minion:`providers` parameter in the
minion config file to set the provider.

If you end up needing to override a provider because it was not detected,
please let us know! File an issue on the `issue tracker`_, and provide the
output from the :mod:`grains.items <salt.modules.grains.items>` function,
taking care to sanitize any sensitive information.

Below are tables that should help with deciding which provider to use if one
needs to be overridden.


Provider: ``pkg``
*****************

======================= =======================================================
Execution Module        Used for
======================= =======================================================
apt                     Debian/Ubuntu-based distros which use ``apt-get(8)``
                        for package management
brew                    Mac OS software management using `Homebrew`_
ebuild                  Gentoo-based systems (utilizes the ``portage`` python
                        module as well as ``emerge(1)``)
freebsdpkg              FreeBSD-based OSes using ``pkg_add(1)``
openbsdpkg              OpenBSD-based OSes using ``pkg_add(1)``
pacman                  Arch Linux-based distros using ``pacman(8)``
pkgin                   NetBSD-based OSes using ``pkgin(1)``
pkgng                   FreeBSD-based OSes using ``pkg(8)``
pkgutil                 Solaris-based OSes using `OpenCSW`_'s ``pkgutil(1)``
solarispkg              Solaris-based OSes using ``pkgadd(1M)``
solarisips              Solaris-based OSes using IPS ``pkg(1)``
win_pkg                 Windows
yumpkg                  RedHat-based distros and derivatives (wraps ``yum(8)``)
zypper                  SUSE-based distros using ``zypper(8)``
======================= =======================================================

.. _Homebrew: http://brew.sh/
.. _OpenCSW: http://www.opencsw.org/


Provider: ``service``
*********************

======================= =======================================================
Execution Module        Used for
======================= =======================================================
debian_service          Debian (non-systemd)
freebsdservice          FreeBSD-based OSes using ``service(8)``
gentoo_service          Gentoo Linux using :program:`sysvinit` and
                        ``rc-update(8)``
launchctl               Mac OS hosts using ``launchctl(1)``
netbsdservice           NetBSD-based OSes
openbsdservice          OpenBSD-based OSes
rh_service              RedHat-based distros and derivatives using
                        ``service(8)`` and ``chkconfig(8)``. Supports both
                        pure sysvinit and mixed sysvinit/upstart systems.
service                 Fallback which simply wraps sysvinit scripts
smf                     Solaris-based OSes which use SMF
systemd                 Linux distros which use systemd
upstart                 Ubuntu-based distros using upstart
win_service             Windows
======================= =======================================================


Provider: ``user``
******************

======================= =======================================================
Execution Module        Used for
======================= =======================================================
useradd                 Linux, NetBSD, and OpenBSD systems using
                        ``useradd(8)``, ``userdel(8)``, and ``usermod(8)``
pw_user                 FreeBSD-based OSes using ``pw(8)``
solaris_user            Solaris-based OSes using ``useradd(1M)``,
                        ``userdel(1M)``, and ``usermod(1M)``
win_useradd             Windows
======================= =======================================================


Provider: ``group``
*******************

======================= =======================================================
Execution Module        Used for
======================= =======================================================
groupadd                Linux, NetBSD, and OpenBSD systems using
                        ``groupadd(8)``, ``groupdel(8)``, and ``groupmod(8)``
pw_group                FreeBSD-based OSes using ``pw(8)``
solaris_group           Solaris-based OSes using ``groupadd(1M)``,
                        ``groupdel(1M)``, and ``groupmod(1M)``
win_groupadd            Windows
======================= =======================================================


Arbitrary Module Redirects
==========================

The provider statement can also be used for more powerful means, instead of
overwriting or extending the module used for the named service an arbitrary
module can be used to provide certain functionality.

.. code-block:: yaml

    emacs:
      pkg.installed:
        - provider:
          - cmd: customcmd

In this example, the state is being instructed to use a custom module to invoke
commands.

Arbitrary module redirects can be used to dramatically change the behavior of a
given state.