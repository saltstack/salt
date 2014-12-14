===================
Include and Exclude
===================

Salt sls files can include other sls files and exclude sls files that have been
otherwise included. This allows for an sls file to easily extend or manipulate
other sls files.

Include
=======

When other sls files are included, everything defined in the included sls file
will be added to the state run. When including define a list of sls formulas
to include:

.. code-block:: yaml

    include:
      - http
      - libvirt

The include statement will include sls formulas from the same environment
that the including sls formula is in. But the environment can be explicitly
defined in the configuration to override the running environment, therefore
if an sls formula needs to be included from an external environment named "dev"
the following syntax is used:

.. code-block:: yaml

    include:
      - dev: http

Relative Include
================

In Salt 0.16.0 the capability to include sls formulas which are relative to
the running sls formula was added, simply precede the formula name with a
`.`:

.. code-block:: yaml

    include:
      - .virt
      - .virt.hyper

Exclude
=======

The exclude statement, added in Salt 0.10.3 allows an sls to hard exclude
another sls file or a specific id. The component is excluded after the
high data has been compiled, so nothing should be able to override an
exclude.

Since the exclude can remove an id or an sls the type of component to
exclude needs to be defined. an exclude statement that verifies that the
running highstate does not contain the `http` sls and the `/etc/vimrc` id
would look like this:

.. code-block:: yaml

    exclude:
      - sls: http
      - id: /etc/vimrc