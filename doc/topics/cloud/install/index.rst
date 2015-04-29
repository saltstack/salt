Install Salt Cloud
==================

Salt Cloud is now part of Salt proper.  It was merged in as of
:doc:`Salt version 2014.1.0 </topics/releases/2014.1.0>`.

On Ubuntu, install Salt Cloud by using following command:

.. code-block:: bash

    sudo add-apt-repository ppa:saltstack/salt
    sudo apt-get update
    sudo apt-get install salt-cloud

If using Salt Cloud on OS X, ``curl-ca-bundle`` must be installed. Presently,
this package is not available via ``brew``, but it is available using MacPorts:

.. code-block:: bash

    sudo port install curl-ca-bundle

Salt Cloud depends on ``apache-libcloud``.  Libcloud can be installed via pip
with ``pip install apache-libcloud``.

Installing Salt Cloud for development
-------------------------------------

Installing Salt for development enables Salt Cloud development as well, just
make sure ``apache-libcloud`` is installed as per above paragraph.

See these instructions: :doc:`Installing Salt for development </topics/development/hacking>`.
