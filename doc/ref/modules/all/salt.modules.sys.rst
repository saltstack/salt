================
salt.modules.sys
================

The regular salt modules execute in a separate context from the salt minion
and manipulating the actual salt modules needs to happen in a higher level
context within the minion process. This is where the sys pseudo module is
used.

The sys pseudo module comes with a few functions that return data about the
available functions on the minion or allows for the minion modules to be
refreshed. These functions are as follows:

.. py:module:: salt.modules.sys

.. py:function:: doc([module[, module.function]])

    Display the inline documentation for all available modules, or for the
    specified module or function.

.. py:function:: reload_modules

    Instruct the minion to reload all available modules in memory. This
    function can be called if the modules need to be re-evaluated for
    availability or new modules have been made available to the minion.

.. py:function:: list_modules

    List all available (loaded) modules.

.. py:function:: list_functions

    List all known functions that are in available (loaded) modules.
