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
``Jinja + json`` and ``Mako + json``. But renderers can be written to support
anything. This means that the Salt states could be managed by xml files, html
files, puppet files, or any format that can be translated into the data
structure used by the state system.

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


Writing Renderers
-----------------

Writing a renderer is easy, all that is required is that a Python module
is placed in the rendered directory and that the module implements the
render function. The render function will be passed the path of the SLS file.
In the render function, parse the passed file and return the data structure
derived from the file.

Examples
--------

The best place to find examples of renderers is in the Salt source code. The
renderers included with Salt can be found here:

:blob:`salt/renderers`

Here is a simple Jinja + YAML example:

.. code-block:: python

    # Import Python libs
    import os

    # Import Third Party libs
    import yaml
    from jinja2 import Template

    def render(template):
        '''
        Render the data passing the functions and grains into the rendering system
        '''
        if not os.path.isfile(template):
            return {}
        passthrough = {}
        passthrough.update(__salt__)
        passthrough.update(__grains__)
        template = Template(open(template, 'r').read())
        yaml_data = template.render(**passthrough)
        return yaml.load(yaml_data)
