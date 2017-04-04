.. _internals-fileserver-client:

The Salt Fileserver and Client
==============================

Introduction
------------

Salt has a modular fileserver, and mulitple client classes which are used to
interact with it. This page serves as a developer's reference, to help explain
how the fileserver and clients both work.

Fileserver
----------

The fileserver is not a daemon, so the fileserver and client are not a true
server and client in the traditional sense. Instead, the fileserver is simply a
class (``salt.fileserver.Fileserver``), located in
`salt/fileserver/__init__.py`_. This class has access to the configured
fileserver backends via a loader instance, referenced as ``self.servers``. When
a request comes in from the fileclient, it will ultimately result in a
``Fileserver`` class function being run.

The functions in this class will run corresponding functions in the configured
fileserver backends to perform the requested action. So, in summary:

1. A fileclient class makes a request...
2. which triggers the fileserver to run a function...
3. which runs a named function in each of the configured backends.

Not all of the functions will always execute on every configured backend. For
instance, the ``find_file`` function in the fileserver will stop when it finds
a match, so if it finds a match for the desired path in the first configured
backend, it won't proceed and try to find the file in the next backend in the
list.

Additionally, not all backends implement all functions in the
``salt.fileserver.Fileserver`` class. For instance, there is a function called
``update``, which exists to update remote fileservers such as the ``git``,
``hg``, and ``svn`` backends. This action has no use however in the ``roots``
backend, so it is simply not implemented there, and thus the ``roots`` backend
will be skipped if the ``update`` function is run on the fileserver.

Backends for the fileserver are located in `salt/fileserver/`_ (the files not
named ``__init__.py``).

.. _`salt/fileserver/__init__.py`: https://github.com/saltstack/salt/tree/develop/salt/fileserver/__init__.py
.. _`salt/fileserver/`: https://github.com/saltstack/salt/tree/develop/salt/fileserver

Fileclient
----------

There are three fileclient classes:

salt.fileclient.RemoteClient
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This client is used when :conf_minion:`file_client` is set to ``remote``. This
is how minions request files from the master.

Functions in this client will craft a payload and send it to the master via the
transport channel. This is the same way that the minion asks the minion to do
other things, such as updating and requesting data from the mine. The payload
will be a dictionary with a key called ``cmd``, and other values as needed.

Payloads sent via the transport channel are processed my an MWorker instance on
the master, and the MWorker's ``_handle_aes()`` function will execute the
command. The command will be a function attribute of the
``salt.master.AESFuncs`` class. The AESFuncs class' ``__setup_fileserver()``
function instantiates a ``salt.fileserver.Fileserver`` instance and maps its
member functions to AESFuncs attributes. This is what makes the fileserver
functions available remotely. The result of the function is returned back
through the transport channel to the minion.

Transporting files is done in chunks, the size of which is decided by the
``file_buffer_size`` config option. If you look at the ``serve_file()``
function in any of the fileserver backends, you can see how the ``loc`` value
in the payload determines the offset so that an intermediate chunk of the file
can be served. The RemoteClient's ``get_file()`` function will loop until the
end of the file is reached, retrieving one chunk at a time.

salt.fileclient.FSClient
~~~~~~~~~~~~~~~~~~~~~~~~

This client is used when :conf_minion:`file_client` is set to ``local``. This
is how masterless minions request files.

This class inherits from the RemoteClient, but instead of using a transport
channel (zmq, tcp, etc.), it uses a "fake" transport channel
(``salt.fileserver.FSChan``), which implements its own ``send()`` function.
Thus, when a function that the FSClient inherits from the RemoteClient runs
``self.channel.send()``, it's actually calling
``salt.fileserver.FSChan.send()``, which calls corresponding functions in the
``salt.fileserver.Fileserver()`` class. The result is that local file requests
use the same code as remote file requests, they just bypass sending them
through an actual transport channel and instead call them on the FSChan's
Fileserver instance.

salt.fileclient.LocalClient
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This client is now used exclusively by Pillar. This used to be used when
:conf_minion:`file_client` was set to ``local``, but the ``FSChan`` class was
written to allow minions with ``file_client: local`` to access the full set of
backends. This class will probably be renamed at some point as it is often
confused with ``salt.client.LocalClient``.


The :mod:`cp <salt.modules.cp>` Module
--------------------------------------

Most of the user-facing interaction with the fileclient happens via the
:mod:`cp <salt.modules.cp>` module. The functions in this module instantiate a
fileclient instance (if one is not already saved to the ``__context__``
dunder) and run fileclient functions.
