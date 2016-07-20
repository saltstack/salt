=========
Salt Virt
=========

The Salt Virt cloud controller capability was initially added to Salt in
version 0.14.0 as an alpha technology.

The initial Salt Virt system supports core cloud operations:

- Virtual machine deployment
- Inspection of deployed VMs
- Virtual machine migration
- Network profiling
- Automatic VM integration with all aspects of Salt
- Image Pre-seeding

Many features are currently under development to enhance the capabilities of
the Salt Virt systems.

.. note::

    It is noteworthy that Salt was originally developed with the intent of
    using the Salt communication system as the backbone to a cloud controller.
    This means that the Salt Virt system is not an afterthought, simply a
    system that took the back seat to other development. The original attempt
    to develop the cloud control aspects of Salt was a project called butter.
    This project never took off, but was functional and proves the early
    viability of Salt to be a cloud controller.

.. warning::
    Salt Virt does not work with KVM that is running in a VM. KVM must be running
    on the base hardware.

Salt Virt Tutorial
==================

A tutorial about how to get Salt Virt up and running has been added to the
tutorial section:

:doc:`Cloud Controller Tutorial </topics/tutorials/cloud_controller>`

The Salt Virt Runner
====================

The point of interaction with the cloud controller is the :strong:`virt`
runner. The :strong:`virt` runner comes with routines to execute specific
virtual machine routines.

Reference documentation for the virt runner is available with the runner
module documentation:

:py:mod:`Virt Runner Reference <salt.modules.virt>`

Based on Live State Data
========================

The Salt Virt system is based on using Salt to query live data about
hypervisors and then using the data gathered to make decisions about cloud
operations. This means that no external resources are required to run Salt
Virt, and that the information gathered about the cloud is live and accurate.


Deploy from Network or Disk
===========================

.. toctree::
    disk
    nic
