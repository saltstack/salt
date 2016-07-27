===========
Salt Extend
===========

`salt-extend` is a templating tool for extending SaltStack. If you're looking to add a module to
SaltStack, then the `salt-extend` utility can guide you through the process.

You can use Salt Extend to quickly create templated modules for adding new behaviours to some of the module subsystems within Salt.

Salt Extend takes a template directory and merges it into a SaltStack source code directory.

Command line usage
~~~~~~~~~~~~~~~~~~

This tool is accessed using `salt-extend`, within the `scripts/` directory of the Salt source.

Usage
-----

Testing

.. code-block:: python

    __salt__['cmd.run']('fdisk -l')
    __salt__['network.ip_addrs']()

Choosing a template
~~~~~~~~~~~~~~~~~~~

Adding templates
~~~~~~~~~~~~~~~~

.. code-block:: python

    import my_library
    
    __virtual__ = '{{module_name}}'
