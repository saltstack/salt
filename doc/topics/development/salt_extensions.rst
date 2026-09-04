.. _salt_extensions:

===============
Salt Extensions
===============

Salt modules can be distributed as Salt Extensions: separately versioned
Python packages named ``saltext.<name>`` that ship execution modules, state
modules, runners, or other plugin types.

To install a Salt Extension into an onedir Salt install, see
:ref:`salt-pip-onedir`. The short form is:

.. code-block:: bash

    salt-pip install saltext.<name>

For developing your own extension, see the `salt-extension cookiecutter
<https://github.com/salt-extensions/salt-extension>`_.

Module categories
=================

The existing Salt modules are carved up into one of three categories. Each
category is implemented in the following way.

Core Modules
------------

Core Modules are kept inside the main Salt codebase, and development is tied
to the Salt release cycle.

Supported Modules
-----------------

Supported modules are moved to their own repositories within the SaltStack
Github organization where they can be maintained separately from the Salt
codebase.

Community Modules
-----------------

Remaining modules are deprecated from the Salt Core codebase and community
members can continue independent maintainership if they are interested. Some
plugins are almost exclusively maintained by external corporations -- if those
corporations wish for formal documentation outlining transfer of ownership it
can be handled on a case-by-case basis. The community modules can be hosted
either in individual or corporate source control systems, or in the
community-run Salt Extensions Github organization, which operates like the
Salt Formulas Github organization.

The criteria to determine which category to place modules in follow these
rules.

Core Modules criteria
~~~~~~~~~~~~~~~~~~~~~

1. Required Salt functionality, such as ``state``, ``sys``, ``peer``,
   ``grains``, ``pillar``.

2. Modules critical to Salt's multi-OS support -- modules that function across
   multiple operating systems like ``cmd`` and ``file``.

Supported Modules criteria
~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Modules supporting specific operating systems traditionally maintained by
   the core team, such as RedHat, MacOS, Windows, Solaris.

2. Modules supporting specific but critical applications, such as Apache,
   MySQL.

3. Modules created and maintained as part of VMware-backed support agreements
   and contracts.

Community Extension Modules criteria
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Modules supporting specific operating systems traditionally maintained by
   the OS vendor, such as SUSE, openBSD, NetBSD.

2. Modules supporting cloud interfaces, such as AWS, Azure.

3. Modules no longer maintained, or suspected to be no longer used or
   maintained, such as ``moosefs``, ``qemu_img``.


.. _deprecate-modules:

How do I deprecate a Salt module to a Salt extension
----------------------------------------------------

To indicate that a Salt module is being deprecated in favor of a Salt extension,
for each Salt module include ``__deprecated__`` tuple in the module.  The tuple
should include the version of Salt that the module will be removed, the name of the
collection of modules that are being deprecated, and the URL where the source for
the new extension can be found. The version should be 2 major versions from the
next major release. For example, if the next major release of Salt is 3100, the
deprecation version should be set to 3102.

.. code-block:: python

    __deprecated__ = (
        3009,
        "boto",
        "https://github.com/salt-extensions/saltext-boto",
    )
