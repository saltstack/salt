.. _renderers:

=========
Renderers
=========

The Salt state system operates by gathering information from common data
types such as lists, dictionaries, and strings that would be familiar
to any developer.

SLS files are translated from whatever data templating format they are written
in back into Python data types to be consumed by Salt.

By default SLS files are rendered as Jinja templates and then parsed as YAML
documents. But since the only thing the state system cares about is raw data,
the SLS files can be any structured format that can be dreamed up.

Currently there is support for ``Jinja + YAML``, ``Mako + YAML``,
``Wempy + YAML``, ``Jinja + json``, ``Mako + json`` and ``Wempy + json``.

Renderers can be written to support any template type. This means that the
Salt states could be managed by XML files, HTML files, Puppet files, or any
format that can be translated into the Pythonic data structure used by the state
system.

Multiple Renderers
------------------

A default renderer is selected in the master configuration file by providing
a value to the ``renderer`` key.

When evaluating an SLS, more than one renderer can be used.

When rendering SLS files, Salt checks for the presence of a Salt-specific
shebang line.

The shebang line directly calls the name of the renderer as it is specified
within Salt. One of the most common reasons to use multiple renderers is to
use the Python or ``py`` renderer.

Below, the first line is a shebang that references the ``py`` renderer.

.. code-block:: python

    #!py

    def run():
        '''
        Install the python-mako package
        '''
        return {'include': ['python'],
                'python-mako': {'pkg': ['installed']}}


.. _renderers-composing:

Composing Renderers
-------------------
A renderer can be composed from other renderers by connecting them in a series
of pipes(``|``).

In fact, the default ``Jinja + YAML`` renderer is implemented by connecting a YAML
renderer to a Jinja renderer. Such renderer configuration is specified as: ``jinja | yaml``.

Other renderer combinations are possible:

  ``yaml``
      i.e, just YAML, no templating.

  ``mako | yaml``
      pass the input to the ``mako`` renderer, whose output is then fed into the
      ``yaml`` renderer.

  ``jinja | mako | yaml``
      This one allows you to use both jinja and mako templating syntax in the
      input and then parse the final rendered output as YAML.

The following is a contrived example SLS file using the ``jinja | mako | yaml`` renderer:

.. code-block:: python

    #!jinja|mako|yaml

    An_Example:
      cmd.run:
        - name: |
            echo "Using Salt ${grains['saltversion']}" \
                 "from path {{grains['saltpath']}}."
        - cwd: /

    <%doc> ${...} is Mako's notation, and so is this comment. </%doc>
    {#     Similarly, {{...}} is Jinja's notation, and so is this comment. #}

For backward compatibility, ``jinja | yaml`` can also be written as
``yaml_jinja``, and similarly, the ``yaml_mako``, ``yaml_wempy``,
``json_jinja``, ``json_mako``, and ``json_wempy`` renderers are all supported.

Keep in mind that not all renderers can be used alone or with any other renderers.
For example, the template renderers shouldn't be used alone as their outputs are
just strings, which still need to be parsed by another renderer to turn them into
highstate data structures.

For example, it doesn't make sense to specify ``yaml | jinja`` because the
output of the YAML renderer is a highstate data structure (a dict in Python), which
cannot be used as the input to a template renderer. Therefore, when combining
renderers, you should know what each renderer accepts as input and what it returns
as output.

Writing Renderers
-----------------

A custom renderer must be a Python module placed in the renderers directory and the
module implement the ``render`` function.

The ``render`` function will be passed the path of the SLS file as an argument.

The purpose of of ``render`` function is to  parse the passed file and to return
the Python data structure derived from the file.

Custom renderers must be placed in a ``_renderers`` directory within the
:conf_master:`file_roots` specified by the master config file.

Custom renderers are distributed when any of the following are run:

- :py:func:`state.apply <salt.modules.state.apply_>`
- :py:func:`saltutil.sync_renderers <salt.modules.saltutil.sync_renderers>`
- :py:func:`saltutil.sync_all <salt.modules.saltutil.sync_all>`

Any custom renderers which have been synced to a minion, that are named the
same as one of Salt's default set of renderers, will take the place of the
default renderer with the same name.


Examples
--------

The best place to find examples of renderers is in the Salt source code.

Documentation for renderers included with Salt can be found here:

:blob:`salt/renderers`

Here is a simple YAML renderer example:

.. code-block:: python

    import yaml
    def render(yaml_data, saltenv='', sls='', **kws):
        if not isinstance(yaml_data, basestring):
            yaml_data = yaml_data.read()
        data = yaml.load(yaml_data)
        return data if data else {}

Full List of Renderers
----------------------
.. toctree::

    all/index
