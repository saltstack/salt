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

If you call `salt-extend` with no parameters, it will prompt you through all the options at the command-line.

    usage: salt-extend [-h] [--extension EXTENSION]
                       [--salt-directory SALT_DIRECTORY] [--name NAME]
                       [--description DESCRIPTION] [--no-merge] [--debug]
    
    Quickly boilerplate an extension to SaltStack
    
    optional arguments:
      -h, --help            show this help message and exit
      --extension EXTENSION, -e EXTENSION
                            Extension type, e.g. 'module', 'state'.
      --salt-directory SALT_DIRECTORY, -o SALT_DIRECTORY
                            Directory where your salt installation is kept
                            (defaults to .).
      --name NAME, -n NAME  Module name.
      --description DESCRIPTION, -d DESCRIPTION
                            Short description of what the module does.
      --no-merge            Don't merge the module into the salt directory, keep
                            in a temp location
      --debug               Display detailed logs whilst applying templates

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
