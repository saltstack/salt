.. _states-include:

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

.. include:: ../../_incl/sls_filename_cant_contain_period.rst

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

Since the exclude can remove an id or an sls the type of component to exclude
needs to be defined. An exclude statement that verifies that the running
:ref:`highstate <running-highstate>` does not contain the ``http`` sls and the
``/etc/vimrc`` id would look like this:

.. code-block:: yaml

    exclude:
      - sls: http
      - id: /etc/vimrc

.. note::
    The current state processing flow checks for duplicate IDs before
    processing excludes. An error occurs if duplicate IDs are present even if
    one of the IDs is targeted by an ``exclude``.

.. _include-ordering:

Include resolution and ordering
===============================

``include`` controls SLS file *resolution*, not *execution order*. Two things
are important to understand:

1. **Recursion.** Each included SLS is itself processed for its own ``include``
   block before its states are merged into the run. The graph is walked
   depth-first, and each SLS is loaded exactly once even if it is referenced
   from multiple includes.
2. **Merge order.** States are added to the run in the order in which their
   containing SLS files are *first encountered* during this depth-first walk.
   The including SLS is processed last so that its states come after the
   included SLS files. This is the resolution order, not the execution order.

Execution order is determined by:

* :ref:`requisites <requisites>` (``require``, ``watch``, ``onchanges``,
  ``prereq``, ``listen``, etc.) — these set hard dependencies and override
  resolution order.
* The :ref:`order <ordering>` global state argument — explicit numeric
  ordering.
* The compiler's tie-breaker, which falls back to the resolution order
  described above when no requisite or ``order`` applies.

If you require a specific run order between states defined in different SLS
files, use a requisite. Relying on resolution order is fragile: rearranging
``include`` entries or restructuring a tree of includes can change the
resolved order without changing the YAML you're editing.

Worked example
--------------

Consider the following SLS tree under ``salt://``::

    top.sls
    web/init.sls
    web/config.sls
    db/init.sls

``top.sls``:

.. code-block:: yaml

    base:
      '*':
        - web

``web/init.sls``:

.. code-block:: yaml

    include:
      - db
      - web.config

    web-pkg:
      pkg.installed:
        - name: nginx

``web/config.sls``:

.. code-block:: yaml

    /etc/nginx/nginx.conf:
      file.managed:
        - source: salt://web/files/nginx.conf

``db/init.sls``:

.. code-block:: yaml

    db-pkg:
      pkg.installed:
        - name: postgresql

Salt resolves ``web`` as the top entry. It then walks ``include:`` depth-first:

1. ``db`` is loaded. ``db-pkg`` is added to the run.
2. ``web.config`` is loaded. ``/etc/nginx/nginx.conf`` is added to the run.
3. The states defined directly in ``web/init.sls`` are added: ``web-pkg``.

Without requisites the order is ``db-pkg``, ``/etc/nginx/nginx.conf``,
``web-pkg``. If ``web-pkg`` must run before ``/etc/nginx/nginx.conf``, do not
shuffle the ``include`` list; declare a ``require`` instead:

.. code-block:: yaml

    /etc/nginx/nginx.conf:
      file.managed:
        - source: salt://web/files/nginx.conf
        - require:
          - pkg: web-pkg

Cycles and duplicates
---------------------

* A cycle in ``include`` (``a`` includes ``b`` includes ``a``) is permitted at
  resolution time because each SLS is loaded at most once. A cycle in
  *requisites* is a hard error and is reported by the compiler.
* If two included SLS files both declare the same ID, the compiler raises a
  duplicate-ID error. Duplicate IDs are checked before ``exclude`` is applied,
  so you cannot use ``exclude`` to silence a duplicate-ID conflict.
