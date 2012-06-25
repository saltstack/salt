================
Salt File Server
================

Salt comes with a simple file server suitable for distributing files to the
Salt minions. The file server is a stateless ZeroMQ server that is built into
the Salt master.

The main intent of the Salt file server is to present files for use in the
Salt state system. With this said, the Salt file server can be used for any
general file transfer from the master to the minions.

The cp Module
-------------

The cp module is the home of minion side file server operations. The cp module
is used by the Salt state system, salt-cp and can be used to distribute files
presented by the Salt file server.

Environments
````````````

Since the file server is made to work with the Salt state system, it supports
environments. The environments are defined in the master config file and
when referencing an environment the file specified will be based on the root
directory of the environment.

get_file
````````

The cp.get_file function can be used on the minion to download a file from
the master, the syntax looks like this:

.. code-block:: bash

    # salt '*' cp.get_file salt://vimrc /etc/vimrc

This will instruct all Salt minions to download the vimrc file and copy it
to /etc/vimrc

File Server Client API
----------------------

A client API is available which allows for modules and applications to be
written which make use of the Salt file server.

The file server uses the same authentication and encryption used by the rest
of the Salt system for network communication.

FileClient Class
````````````````

The FileClient class is used to set up the communication from the minion to
the master. When creating a FileClient object the minion configuration needs
to be passed in. When using the FileClient from within a minion module the
built in ``__opts__`` data can be passed:

.. code-block:: python

    import salt.minion

    def get_file(path, dest, env='base'):
        '''
        Used to get a single file from the Salt master

        CLI Example:
        salt '*' cp.get_file salt://vimrc /etc/vimrc
        '''
        # Create the FileClient object
        client = salt.minion.FileClient(__opts__)
        # Call get_file
        return client.get_file(path, dest, False, env)

Using the FileClient class outside of a minion module where the ``__opts__``
data is not available, it needs to be generated:

.. code-block:: python

    import salt.minion
    import salt.config

    def get_file(path, dest, env='base'):
        '''
        Used to get a single file from the Salt master
        '''
        # Get the configuration data
        opts = salt.config.minion_config('/etc/salt/minion')
        # Create the FileClient object
        client = salt.minion.FileClient(opts)
        # Call get_file
        return client.get_file(path, dest, False, env)

