.. _salt_extensions:

===============
Salt Extensions
===============

Salt modules can be distributed as Salt Extensions.

The existing Salt modules will be carved up into one of three categories. Each category will be
implemented in the following way:

## Core Modules

Core Modules will be kept inside the main Salt codebase, and development will be tied to the
Salt release cycle.

## Supported Modules

Supported modules will be moved to their own repositories within the SaltStack Github
organization where they can be maintained separately from the Salt codebase.

## Community Modules

Remaining modules will be deprecated from the Salt Core codebase and community members
will be able to continue independent maintainership if they are interested. Some plugins are
almost exclusively maintained by external corporations – if these corporations wish for formal
documentation outlining transfer of ownership it can be handled on a case-by-case basis. The
community modules can be hosted either in individual or corporate source control systems,
alternatively they can also be hosted in the community run Salt Extensions Github organization,
that will operate like the Salt Formulas Github organization.
The criteria to determine which category to place modules in will follow these rules:

## Core Modules

1. Required Salt Functionality

  a. Modules such as state, sys, peer, grains, pillar, etc.

2. Modules critical to Salt’s Multi OS support

  a. Modules that function across multiple operating systems like cmd and file.

## Supported Modules

1. Modules to support specific operating systems traditionally maintained by the core team
– such as RedHat, MacOS, Windows, Solaris, etc.

2. Modules to support specific but critical applications, such as Apache, MySQL, etc.

3. Modules created and maintained as part of VMware backed support agreements and
contracts.

## Community Extension Modules

1. Modules to support specific operating systems traditionally maintained by the OS vendor
– such as SUSE, openBSD, NetBSD, etc.

2. Modules to support cloud interfaces, such as AWS, Azure, etc.

3. Modules no longer maintained, or which we suspect are also no longer used or
maintained, such as moosefs, qemu_img, etc.


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

.. code-block: python

    __deprecated__ = (
        3009,
        "boto",
        "https://github.com/salt-extensions/saltext-boto",
    )
