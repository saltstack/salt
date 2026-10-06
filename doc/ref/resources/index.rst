.. _all-salt.resources:

==========================
Salt Resources reference
==========================

.. versionadded:: 3008.0

Autodoc reference for the resource-framework modules and the resource
types shipped in core Salt. For the user-facing guide see
:ref:`resources`.


Resource types
==============

.. toctree::
    :maxdepth: 1

    all/index


Framework
=========

The resource registry — the master-side index of which minion manages
which resource:

.. automodule:: salt.utils.resource_registry
    :no-members:

Operator runner:

.. toctree::
    :maxdepth: 1

    /ref/runners/all/salt.runners.resource

Per-resource grains module:

.. toctree::
    :maxdepth: 1

    /ref/grains/all/salt.grains.resources
