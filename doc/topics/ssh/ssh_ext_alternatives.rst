.. _ssh-ext-alternatives:

====================
SSH Ext Alternatives
====================

In the 2019.2.0 release the ``ssh_ext_alternatives`` feature was added.
This allows salt-ssh to work across different python versions. You will
need to ensure you have the following:

  - Salt is installed, with all required dependnecies for both Python2 and Python3
  - Everything needs to be importable from the respective Python environment.

To enable using this feature you will need to edit the master configuration similar
to below:

.. code-block:: yaml

       ssh_ext_alternatives:
           2019.2:                     # Namespace, can be anything.
               py-version: [2, 7]      # Constraint to specific interpreter version
               path: /opt/2019.2/salt  # Main Salt installation directory.
               dependencies:           # List of dependencies and their installation paths
                 jinja2: /opt/jinja2
                 yaml: /opt/yaml
                 tornado: /opt/tornado
                 msgpack: /opt/msgpack
                 certifi: /opt/certifi
                 singledispatch: /opt/singledispatch.py
                 singledispatch_helpers: /opt/singledispatch_helpers.py
                 markupsafe: /opt/markupsafe
                 backports_abc: /opt/backports_abc.py

auto_detect
-----------

In the 3001 release the ``auto_detect`` feature was added for ``ssh_ext_alternatives``.
This allows salt-ssh to automatically detect the path to all of your dependencies and
does not require you to define them under ``dependencies``.

.. code-block:: yaml

       ssh_ext_alternatives:
           2019.2:                     # Namespace, can be anything.
               py-version: [2, 7]      # Constraint to specific interpreter version
               path: /opt/2019.2/salt  # Main Salt installation directory.
               auto_detect: True       # Auto detect dependencies
               py_bin: /usr/bin/python2.7 # Python binary path used to auto detect dependencies

If ``py_bin`` is not set alongside ``auto_detect``, it will attempt to auto detect
the dependnecies using the major version set in ``py-version``. For example if you
have ``[2, 7]`` set as your ``py-version``, it will attempt to use the binary ``python2``.

You can also use ``auto_detect`` and ``dependencies`` together.

.. code-block:: yaml

       ssh_ext_alternatives:
           2019.2:                     # Namespace, can be anything.
               py-version: [2, 7]      # Constraint to specific interpreter version
               path: /opt/2019.2/salt  # Main Salt installation directory.
               auto_detect: True       # Auto detect dependencies
               py_bin: /usr/bin/python2.7 # Python binary path to auto detect dependencies
               dependencies:           # List of dependencies and their installation paths
                 jinja2: /opt/jinja2

If a dependency is defined in the ``dependecies`` list ``ssh_ext_alternatives`` will use
this dependency, instead of the path that ``auto_detect`` finds. For example, if you define
``/opt/jinja2`` under your ``dependencies`` for jinja2, it will not try to autodetect the
file path to the jinja2 module, and will favor ``/opt/jinja2``.
