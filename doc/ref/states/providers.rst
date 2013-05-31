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

In this instance, the basic :py:mod:`~salt.modules.service` module will replace
the :py:mod:`~salt.modules.systemd` module which is used by default on Arch
Linux, and the :program:`httpd` service will be managed using
:program:`sysvinit`.

.. note::

    You can also set a provider globally in the minion config
    :conf_minion:`providers`.

Arbitrary Module Redirects
==========================

The provider statement can also be used for more powerful means, instead of
overwriting or extending the module used for the named service an arbitrary
module can be used to provide certain functionality.

.. code-block:: yaml

    emacs:
      pkg.installed:
        - provider:
          - pkg: yumpkg5
          - cmd: customcmd

In this example the default :py:mod:`~salt.modules.pkg` module is being
redirected to use the :py:mod:`~salt.modules.yumpkg5` module (:program:`yum`
via shelling out instead of via the :program:`yum` Python API), but is also
using a custom module to invoke commands. This could be used to dramatically
change the behavior of a given state.
