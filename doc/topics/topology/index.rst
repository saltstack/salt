.. _architecture-overview:

============
Architecture
============

If you are used to configuration management tools that require you to plan
down to the last detail before you install anything, you are probably wondering
why this section doesn't appear before the installation instructions. With
Salt, you can switch to a high availability architecture at any time, and add
additional components to scale your deployment as you go.

Since a single Salt master can manage thousands of systems, we usually
recommend that you start by deploying a single Salt master, and then modifying
your deployment as needed for redundancy, geographical distribution, and scale.

.. toctree::
    :maxdepth: 1
    :glob:

    ../highavailability/index
    syndic
    ../tutorials/intro_scale
    ../tutorials/multimaster
    ../tutorials/multimaster_pki


