===================
Include and Exclude
===================

Salt SLS files can include other SLS files and exclude SLS files that have been
otherwise included. This allows for an SLS file to easily extend or manipulate
other SLS files.

Include
=======

When other SLS files are included, everything defined in the included SLS file
will be added to the state run. When including define a list of SLS formulas
to include:

.. code-block:: yaml

    include:
      - http
      - libvirt

The include statement will include SLS formulas from the same environment
that the including SLS formula is in. But the environment can be explicitly
defined in the configuration to override the running environment, therefore
if an SLS formula needs to be included from an external environment named "dev"
the following syntax is used:

.. code-block:: yaml

    include:
      - dev: http

**NOTE**: ``include`` does not simply inject the states where you place it
in the SLS file. If you need to guarantee order of execution, consider using 
requisites.

.. include:: ../../_incl/_incl/sls_filename_cant_contain_period.rst

Relative Include
================

In Salt 0.16.0, the capability to include SLS formulas which are relative to
the running SLS formula was added.  Simply precede the formula name with a
``.``:

.. code-block:: yaml

    include:
      - .virt
      - .virt.hyper

In Salt 2015.8, the ability to include SLS formulas which are relative to the
parents of the running SLS formula was added.  In order to achieve this,
precede the formula name with more than one ``.`` (dot). Much like Python's
relative import abilities, two or more leading dots represent a relative
include of the parent or parents of the current package, with each ``.``
representing one level after the first.

The following SLS configuration, if placed within ``example.dev.virtual``,
would result in ``example.http`` and ``base`` being included respectively:

.. code-block:: yaml

    include:
      - ..http
      - ...base


Exclude
=======

The exclude statement, added in Salt 0.10.3, allows an SLS to hard exclude
another SLS file or a specific id. The component is excluded after the
high data has been compiled, so nothing should be able to override an
exclude.

Since the exclude can remove an id or an SLS the type of component to exclude
needs to be defined. An exclude statement that verifies that the running
highstate does not contain the ``http`` SLS and the ``/etc/vimrc`` id would
look like this:

.. code-block:: yaml

    exclude:
      - sls: http
      - id: /etc/vimrc

.. note::
    The current state processing flow checks for duplicate IDs before
    processing excludes. An error occurs if duplicate IDs are present even if
    one of the IDs is targeted by an ``exclude``.
