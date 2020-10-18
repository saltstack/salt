===============================
SLS Template Variable Reference
===============================


.. warning::
   In the 3002 release ``sls_path``, ``tplfile``, and ``tpldir`` have had some significant
   improvements which have the potential to break states that rely on old and
   broken functionality. These fixes can be enabled by setting the
   ``enable_slsvars_fixes`` feature flag to ``True`` in your minion's config file.
   This functionality will become the default in the 3005 release.

   .. code-block:: yaml

       features:
         enable_slsvars_fixes: True



The template engines available to sls files and file templates come loaded
with a number of context variables. These variables contain information and
functions to assist in the generation of templates.  See each variable below
for its availability -- not all variables are available in all templating
contexts.

Salt
====

The `salt` variable is available to abstract the salt library functions. This
variable is a python dictionary containing all of the functions available to
the running salt minion.  It is available in all salt templates.

.. code-block:: jinja

    {% for file in salt['cmd.run']('ls -1 /opt/to_remove').splitlines() %}
    /opt/to_remove/{{ file }}:
      file.absent
    {% endfor %}

Opts
====

The `opts` variable abstracts the contents of the minion's configuration file
directly to the template. The `opts` variable is a dictionary.  It is available
in all templates.

.. code-block:: jinja

    {{ opts['cachedir'] }}

The ``config.get`` function also searches for values in the `opts` dictionary.

Pillar
======

The `pillar` dictionary can be referenced directly, and is available in all
templates:

.. code-block:: jinja

    {{ pillar['key'] }}

Using the ``pillar.get`` function via the `salt` variable is generally
recommended since a default can be safely set in the event that the value
is not available in pillar and dictionaries can be traversed directly:

.. code-block:: jinja

    {{ salt['pillar.get']('key', 'failover_value') }}
    {{ salt['pillar.get']('stuff:more:deeper') }}

Grains
======

The `grains` dictionary makes the minion's grains directly available, and is
available in all templates:

.. code-block:: jinja

    {{ grains['os'] }}

The ``grains.get`` function can be used to traverse deeper grains and set
defaults:

.. code-block:: jinja

    {{ salt['grains.get']('os') }}

saltenv
=======

The `saltenv` variable is available in only in sls files when gathering the sls
from an environment.

.. code-block:: jinja

    {{ saltenv }}

SLS Only Variables
==================
The following are only available when processing sls files. If you need these
in other templates, you can usually pass them in as template context.

sls
---

The `sls` variable contains the sls reference value, and is only available in
the actual SLS file (not in any files referenced in that SLS). The sls
reference value is the value used to include the sls in top files or via the
include option.

.. code-block:: jinja

    {{ sls }}

slspath
-------

The `slspath` variable contains the path to the directory of the current sls
file. The value of `slspath` in files referenced in the current sls depends on
the reference method. For jinja includes `slspath` is the path to the current
directory of the file. For salt includes `slspath` is the path to the directory
of the included file. If current sls file is in root of the file roots, this
will return ""

.. code-block:: jinja

    {{ slspath }}


sls_path
--------

A version of `slspath` with underscores as path separators instead of slashes.
So, if `slspath` is `path/to/state` then `sls_path` is `path_to_state`

.. code-block:: jinja

    {{ sls_path }}

slsdotpath
----------

A version of `slspath` with dots as path separators instead of slashes. So, if
`slspath` is `path/to/state` then `slsdotpath` is `path.to.state`. This is same
as `sls` if `sls` points to a directory instead if a file.

.. code-block:: jinja

    {{ slsdotpath }}


slscolonpath
------------

A version of `slspath` with colons (`:`) as path separators instead of slashes.
So, if `slspath` is `path/to/state` then `slscolonpath` is `path:to:state`.

.. code-block:: jinja

    {{ slscolonpath }}

tplpath
-------

Full path to sls template file being process on local disk. This is usually
pointing to a copy of the sls file in a cache directory. This will be in OS
specific format (Windows vs POSIX). (It is probably best not to use this.)

.. code-block:: jinja

    {{ tplpath }}


tplfile
-------

Relative path to exact sls template file being processed relative to file
roots.

.. code-block:: jinja

    {{ tplfile }}

tpldir
------

Directory, relative to file roots, of the current sls file. If current sls file
is in root of the file roots, this will return ".". This is usually identical
to `slspath` except in case of root-level sls, where this will return a "`.`".

A Common use case for this variable is to generate relative salt urls like:
.. code-block:: jinja

    my-file:
      file.managed:
        source: salt://{{ tpldir }}/files/my-template


tpldot
------

A version of `tpldir` with dots as path separators instead of slashes. So, if
`tpldir` is `path/to/state` then `tpldot` is `path.to.state`. NOTE: if `tpldir`
is `.`, this will be set to ""

.. code-block:: jinja

    {{ tpldot }}
