.. _salt-extend:

===============
``salt-extend``
===============

A utilty to generate extensions to the Salt source-code. This is used for :

- Adding new execution modules, state modules
- Adding unit tests to existing modules
- Adding integration tests to existing modules


Synopsis
========

.. code-block:: bash

    salt-extend --help

Description
===========

``salt-extend`` is a templating tool for extending SaltStack. If you're looking to add a module to
SaltStack, then the ``salt-extend`` utility can guide you through the process.

You can use Salt Extend to quickly create templated modules for adding new behaviours to some of the module subsystems within Salt.

Salt Extend takes a template directory and merges it into a SaltStack source code directory.

*See also*: :ref:`Salt Extend <development-salt-extend>`.

Options
=======

.. program:: salt-extend

.. option::  --extension, -e

    The extension type you want to develop, e.g. module, module_unit, state

.. option::  --salt-directory, -o

    The path to the salt installation, defaults to .

.. option::  --name, -n

    The module name for the new module

.. option::  --description, -d

    A description of the new extension

.. option::  --no-merge

    Don't merge the new module into the Salt source directory specified by `--salt-directory`, save
    to a temporary directory and print the directory path

.. option::  --debug

    Print debug messages to stdout


See also
========

:manpage:`salt-api(1)`
:manpage:`salt-call(1)`
:manpage:`salt-cloud(1)`
:manpage:`salt-cp(1)`
:manpage:`salt-key(1)`
:manpage:`salt-main(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
:manpage:`salt-run(1)`
:manpage:`salt-ssh(1)`
:manpage:`salt-syndic(1)`
