===============
State Providers
===============

.. versionadded:: 0.9.8

Salt predetermines what modules should be mapped to what uses based on the
properties of a system. These determinations are generally made for modules
that provide things like package and service management.

Sometimes in states it may be needed for an alternative module to be used
to provide the functionality needed. For instance, an Arch Linux system may
have been set up with systemd support, so instead of using the default service
module detected for Arch Linux, the systemd module can be used:

.. code-block:: yaml

    httpd:
      service.running:
        - enable: True
        - provider: systemd

In this instance the systemd module will replace the service virtual module
which is used by default on Arch Linux, and the httpd service will be set up
using systemd.

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

In this example the default pkg module is being redirected to use the *yumpkg5*
module (*yum* via shelling out instead of via the yum API), but is also using
a custom module to invoke commands. This could be used to dramatically change
the behavior of a given state.
