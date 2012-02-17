=====================
The sys Pseudo Module
=====================

The regular salt modules execute in a separate context from the salt minion
and manipulating the actual salt modules needs to happen in a higher level
context within the minion process. This is where the sys pseudo module is
used.

The sys pseudo module comes with a few functions that return data about the
available functions on the minion or allows for the minion modules to be
refreshed. These functions are as follows:

sys.list_functions
==================

Return a list of all the loaded and available functions on the specified
minion

sys.list_modules
================

Return a list of all the loaded and available modules on the specified
minion

sys.doc
=======

This meta function combines the documentation data from the selected minion
modules and displays it to the terminal in a clean, readable way.

sys.reload_modules
==================

The reload_modules function invokes a reload of all of the modules on a
minion. This function can be called if the modules need to be re-evaluated for
availability or new modules have been made available to the minion.
