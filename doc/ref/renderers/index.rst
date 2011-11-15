=========
Renderers
=========

The Salt state system operates by gathering information from simple data
structures. The state system was designed in this way to make interacting with
it generic and simple. This also means that state files (sls files) can be one
of many formats.

By default sls files are rendered as jinja templates and then parsed as yaml
documents. But since the only thing the state system cares about is raw data,
the sls files can be any structured format that can be dreamed up.

Currently there is support for ``jinja + yaml``, ``mako + yaml``,
``jinja + json`` and ``mako + json``. But renderers can be written to support
anything. This means that the Salt states could be managed by xml files, html
files, puppet files, or any format that can be translated into the data
structure used by the state system.

Writing Renderers
-----------------

Writing a renderer is easy, all that is required is that a python module
is placed in the rendered directory and that the module implements the
render function. The render function will be passed the path of the sls file.
In the render function, parse the passed file and return the data structure
derived from the file.

Examples
--------

The best place to find examples of renderers is in the Salt source code. The
renderers included with Salt can be found here:

:blob:`salt/renderers`

Here is a simple jinja + yaml example:

.. code-block:: python

    # Import python libs
    import os

    # Import Third Party libs
    import yaml
    from jinja2 import Template

    def render(template):
        """
        Render the data passing the functions and grains into the rendering system
        """
        if not os.path.isfile(template):
            return {}
        passthrough = {}
        passthrough.update(__salt__)
        passthrough.update(__grains__)
        template = Template(open(template, 'r').read())
        yaml_data = template.render(**passthrough)
        return yaml.load(yaml_data)
