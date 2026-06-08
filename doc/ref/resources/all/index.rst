.. _all-salt.resources.types:

==========================
Resource types
==========================

In-tree resource types shipped with Salt. Resource types in extensions
follow the same shape under ``saltext.<ext>.resources.<rtype>``.

.. currentmodule:: salt.resources

.. autosummary::
    :toctree:
    :template: autosummary.rst.tmpl

    dummy
    ssh

Per-type submodules:

.. toctree::
    :maxdepth: 1

    salt.resources.dummy.modules.test
    salt.resources.ssh.modules.cmd
    salt.resources.ssh.modules.pkg
    salt.resources.ssh.modules.state
    salt.resources.ssh.modules.test
