================
salt.modules.sys
================

A pseudo-module for working with modules on a minion.

.. py:module:: salt.modules.sys

.. py:function:: doc([module[, module.function]])

    Display the inline documentation for all available modules, or for the
    specified module or function.

.. py:function:: reload_modules

    Instruct the minion to reload all available modules in memory.

.. py:function:: list_modules

    List all available (loaded) modules.

.. py:function:: list_functions

    List all known functions that are in available (loaded) modules.
