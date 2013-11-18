===============================
SLS Template Variable Reference
===============================

The template engines available to sls files and file templates come loaded
with a number of context variables. These variables contain information and
functions to assist in the generation of templates.

Salt
====

The `salt` variable is available to abstract the salt library functions. This
variable is a python dictionary containing all of the functions available to
the running salt minion:

.. code-block:: jinja

    {% for file in salt['cmd.run'](ls /opt/to_remove) %}
    {{ file }}:
      file.absent
    {% endfor %}

Opts
====

The `opts` variable abstracts the contents of the minion's configuration file
directly to the template. The `opts` variable is a dictionary.

.. code-block:: jinja

    {{ opts['cachedir'] }}

The ``config.get`` function also searches for values in the `opts` dictionary.

Pillar
======

The `pillar` dictionary can be referenced directly:

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

The `grains` dictionary makes the minion's grains directly available:

.. code-block:: jinja

    {{ grains['os'] }}

The ``grains.get`` function can be used to traverse deeper grains and set
defaults:

.. code-block:: jinja

    {{ salt['grains.get']('os') }}

env
====

The `env` variable is available in sls files when gathering the sls from
an environment.

.. code-block:: jinja

    {{ env }}

sls
====

The `sls` variable contains the sls reference value. The sls reference value
is the value used to include the sls in top files or via the include option.

.. code-block:: jinja

    {{ sls }}
