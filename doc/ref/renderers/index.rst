=========
Renderers
=========

The Salt state system operates by gathering information from simple data
structures. The state system was designed in this way to make interacting with
it generic and simple. This also means that state files (SLS files) can be one
of many formats.

By default SLS files are rendered as Jinja templates and then parsed as YAML
documents. But since the only thing the state system cares about is raw data,
the SLS files can be any structured format that can be dreamed up.

Currently there is support for ``Jinja + YAML``, ``Mako + YAML``, 
``Wempy + YAML``, ``Jinja + json`` ``Mako + json`` and ``Wempy + json``. But
renderers can be written to support anything. This means that the Salt states
could be managed by xml files, html files, puppet files, or any format that
can be translated into the data structure used by the state system.

Multiple Renderers
------------------

When deploying a state tree a default renderer is selected in the master
configuration file with the renderer option. But multiple renderers can be
used inside the same state tree.

When rendering SLS files Salt checks for the presence of a Salt specific
shebang line. The shebang line syntax was chosen because it is familiar to
the target audience, the systems admin and systems engineer.

The shebang line directly calls the name of the renderer as it is specified
within Salt. One of the most common reasons to use multiple renderers in to
use the Python or ``py`` renderer:

.. code-block:: python

    #!py

    def run():
        '''
        Install the python-mako package
        '''
        return {'include': ['python'],
                'python-mako': {'pkg': ['installed']}}

The first line is a shebang that references the ``py`` renderer.

Composing Renderers
-------------------
A renderer can be composed from other renderers by connecting them in a series
of pipes(``|``). In fact, the default ``Jinja + YAML`` renderer is implemented
by combining a yaml renderer and a jinja renderer. Such renderer configuration
is specified as: ``jinja | yaml``.

Other renderer combinations are possible, here's a few examples:

  ``yaml``
      i.e, just YAML, no templating.

  ``mako | yaml``
      pass the input to the ``mako`` renderer, whose output is then fed into the
      ``yaml`` renderer.
  
  ``jinja | mako | yaml``
      This one allows you to use both jinja and mako templating syntax in the
      input and then parse the final rendererd output as YAML.

And here's a contrived example sls file using the ``jinja | mako | yaml`` renderer:

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

For backward compatibility, ``jinja | yaml``  can also be written as
``yaml_jinja``, and similarly, the ``yaml_mako``, ``yaml_wempy``,
``json_jinja``, ``json_mako``, and ``json_wempy`` renderers are all supported
as well.

Keep in mind that not all renderers can be used alone or with any other renderers.
For example, the template renderers shouldn't be used alone as their outputs are
just strings, which still need to be parsed by another renderer to turn them into
highstate data structures. Also, for example, it doesn't make sense to specify
``yaml | jinja`` either, because the output of the yaml renderer is a highstate
data structure(a dict in Python), which cannot be used as the input to a template
renderer. Therefore, when combining renderers, you should know what each renderer
accepts as input and what it returns as output.

Writing Renderers
-----------------

Writing a renderer is easy, all that is required is that a Python module
is placed in the rendered directory and that the module implements the
render function. The render function will be passed the path of the SLS file.
In the render function, parse the passed file and return the data structure
derived from the file. You can place your custom renderers in a ``_renderers``
directory in your file root (``/srv/salt/``).

Examples
--------

The best place to find examples of renderers is in the Salt source code. The
renderers included with Salt can be found here:

:blob:`salt/renderers`

Here is a simple YAML renderer example:

.. code-block:: python

    import yaml
    def render(yaml_data, env='', sls='', **kws):
        if not isinstance(yaml_data, basestring):
            yaml_data = yaml_data.read()
        data = yaml.load(yaml_data)
        return data if data else {}

