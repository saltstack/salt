# -*- coding: utf-8 -*-
'''
Utility functions for use with or in SLS files
'''
from __future__ import absolute_import

import salt.exceptions
import salt.loader
import salt.template
from salt.utils.dictupdate import merge, update

update.__doc__ = update.__doc__ + '''\

CLI Example:

.. code-block:: shell

    salt '*' slsutil.update '{foo: Foo}' '{bar: Bar}'

'''

merge.__doc__ = '''\
Merge a data structure into another by choosing a merge strategy

Strategies:

* aggregate
* list
* overwrite
* recurse
* smart

CLI Example:

.. code-block:: shell

    salt '*' slsutil.merge '{foo: Foo}' '{bar: Bar}'
'''


def renderer(path=None, string=None, default_renderer='jinja|yaml', **kwargs):
    '''
    Parse a string or file through Salt's renderer system

    This is an open-ended function and can be used for a variety of tasks. It
    makes use of Salt's "renderer pipes" system to run a string or file through
    a pipe of any of the loaded renderer modules.

    :param path: The path to a file on the filesystem.
    :param string: An inline string to be used as the file to send through the
        renderer system. Note, not all renderer modules can work with strings;
        the 'py' renderer requires a file, for example.
    :param default_renderer: The renderer pipe to send the file through; this
        is overridden by a "she-bang" at the top of the file.
    :param kwargs: Keyword args to pass to Salt's compile_template() function.

    Keep in mind the goal of each renderer when choosing a render-pipe; for
    example, the Jinja renderer processes a text file and produces a string,
    however the YAML renderer processes a text file and produces a data
    structure.

    One possible use is to allow writing "map files", as are commonly seen in
    Salt formulas, but without tying the renderer of the map file to the
    renderer used in the other sls files. In other words, a map file could use
    the Python renderer and still be included and used by an sls file that uses
    the default 'jinja|yaml' renderer.

    For example, the two following map files produce identical results but one
    is written using the normal 'jinja|yaml' and the other is using 'py':

    .. code-block:: jinja

        #!jinja|yaml
        {% set apache = salt.grains.filter_by({
            ...normal jinja map file here...
        }, merge=salt.pillar.get('apache:lookup')) %}
        {{ apache | yaml() }}

    .. code-block:: python

        #!py
        def run():
            apache = __salt__.grains.filter_by({
                ...normal map here but as a python dict...
            }, merge=__salt__.pillar.get('apache:lookup'))
            return apache

    Regardless of which of the above map files is used, it can be accessed from
    any other sls file by calling this function. The following is a usage
    example in Jinja:

    .. code-block:: jinja

        {% set apache = salt.slsutil.renderer('map.sls') %}

    CLI Example:

    .. code-block:: bash

        salt '*' slsutil.renderer /path/to/file
        salt '*' slsutil.renderer /path/to/file.jinja 'jinja'
        salt '*' slsutil.renderer /path/to/file.sls 'jinja|yaml'
        salt '*' slsutil.renderer string='Inline template! {{ saltenv }}'
        salt '*' slsutil.renderer string='Hello, {{ name }}.' name='world'
    '''
    if not path and not string:
        raise salt.exceptions.SaltInvocationError(
                'Must pass either path or string')

    renderers = salt.loader.render(__opts__, __salt__)

    if path:
        path_or_string = path
    elif string:
        path_or_string = ':string:'
        kwargs['input_data'] = string

    return salt.template.compile_template(
            path_or_string,
            renderers,
            default_renderer,
            __opts__['renderer_blacklist'],
            __opts__['renderer_whitelist'],
            **kwargs)
