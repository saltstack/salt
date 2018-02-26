.. _targeting-range:

==========
SECO Range
==========

SECO range is a cluster-based metadata store developed and maintained by Yahoo!

The Range project is hosted here:

https://github.com/ytoolshed/range

Learn more about range here:

https://github.com/ytoolshed/range/wiki/

Prerequisites
=============

To utilize range support in Salt, a range server is required. Setting up a
range server is outside the scope of this document. Apache modules are included
in the range distribution.

With a working range server, cluster files must be defined. These files are
written in YAML and define hosts contained inside a cluster. Full documentation
on writing YAML range files is here:

https://github.com/ytoolshed/range/wiki/%22yamlfile%22-module-file-spec

Additionally, the Python seco range libraries must be installed on the salt
master. One can verify that they have been installed correctly via the
following command:

.. code-block:: bash

    python -c 'import seco.range'

If no errors are returned, range is installed successfully on the salt master.

Preparing Salt
==============

Range support must be enabled on the salt master by setting the hostname and
port of the range server inside the master configuration file:

.. code-block:: yaml

    range_server: my.range.server.com:80

Following this, the master must be restarted for the change to have an effect.

Targeting with Range
====================

Once a cluster has been defined, it can be targeted with a salt command by
using the ``-R`` or ``--range`` flags.

For example, given the following range YAML file being served from a range
server:

.. code-block:: bash

    $ cat /etc/range/test.yaml
    CLUSTER: host1..100.test.com
    APPS:
      - frontend
      - backend
      - mysql


One might target host1 through host100 in the test.com domain with Salt as follows:

.. code-block:: bash

    salt --range %test:CLUSTER test.ping


The following salt command would target three hosts: ``frontend``, ``backend``, and ``mysql``:

.. code-block:: bash

    salt --range %test:APPS test.ping
