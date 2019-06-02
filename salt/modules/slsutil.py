# -*- coding: utf-8 -*-
'''
Utility functions for use with or in SLS files
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import textwrap
import os

# Import Salt libs
import salt.exceptions
import salt.loader
import salt.template
import salt.utils.args
import salt.utils.dictupdate


def update(dest, upd, recursive_update=True, merge_lists=False):
    '''
    Merge ``upd`` recursively into ``dest``

    If ``merge_lists=True``, will aggregate list object types instead of
    replacing. This behavior is only activated when ``recursive_update=True``.

    CLI Example:

    .. code-block:: shell

        salt '*' slsutil.update '{foo: Foo}' '{bar: Bar}'

    '''
    return salt.utils.dictupdate.update(dest, upd, recursive_update,
            merge_lists)


def merge(obj_a, obj_b, strategy='smart', renderer='yaml', merge_lists=False):
    '''
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
    return salt.utils.dictupdate.merge(obj_a, obj_b, strategy, renderer,
            merge_lists)


def merge_all(lst, strategy='smart', renderer='yaml', merge_lists=False):
    '''
    .. versionadded:: 2019.2.0

    Merge a list of objects into each other in order

    :type lst: Iterable
    :param lst: List of objects to be merged.

    :type strategy: String
    :param strategy: Merge strategy. See utils.dictupdate.

    :type renderer: String
    :param renderer:
        Renderer type. Used to determine strategy when strategy is 'smart'.

    :type merge_lists: Bool
    :param merge_lists: Defines whether to merge embedded object lists.

    CLI Example:

    .. code-block:: shell

        $ salt-call --output=txt slsutil.merge_all '[{foo: Foo}, {foo: Bar}]'
        local: {u'foo': u'Bar'}
    '''

    ret = {}
    for obj in lst:
        ret = salt.utils.dictupdate.merge(
            ret, obj, strategy, renderer, merge_lists
        )

    return ret


def renderer(path=None, string=None, default_renderer='jinja|yaml', **kwargs):
    '''
    Parse a string or file through Salt's renderer system

    .. versionchanged:: 2018.3.0
       Add support for Salt fileserver URIs.

    This is an open-ended function and can be used for a variety of tasks. It
    makes use of Salt's "renderer pipes" system to run a string or file through
    a pipe of any of the loaded renderer modules.

    :param path: The path to a file on Salt's fileserver (any URIs supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`) or on the local file
        system.
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

        salt '*' slsutil.renderer salt://path/to/file
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
        path_or_string = __salt__['cp.get_url'](path, saltenv=kwargs.get('saltenv', 'base'))
    elif string:
        path_or_string = ':string:'
        kwargs['input_data'] = string

    ret = salt.template.compile_template(
        path_or_string,
        renderers,
        default_renderer,
        __opts__['renderer_blacklist'],
        __opts__['renderer_whitelist'],
        **kwargs
    )
    return ret.read() if __utils__['stringio.is_readable'](ret) else ret


def _get_serialize_fn(serializer, fn_name):
    serializers = salt.loader.serializers(__opts__)
    fns = getattr(serializers, serializer, None)
    fn = getattr(fns, fn_name, None)

    if not fns:
        raise salt.exceptions.CommandExecutionError(
            "Serializer '{0}' not found.".format(serializer))

    if not fn:
        raise salt.exceptions.CommandExecutionError(
            "Serializer '{0}' does not implement {1}.".format(serializer,
                fn_name))

    return fn


def serialize(serializer, obj, **mod_kwargs):
    '''
    Serialize a Python object using a :py:mod:`serializer module
    <salt.serializers>`

    CLI Example:

    .. code-block:: bash

        salt '*' --no-parse=obj slsutil.serialize 'json' obj="{'foo': 'Foo!'}

    Jinja Example:

    .. code-block:: jinja

        {% set json_string = salt.slsutil.serialize('json',
            {'foo': 'Foo!'}) %}
    '''
    kwargs = salt.utils.args.clean_kwargs(**mod_kwargs)
    return _get_serialize_fn(serializer, 'serialize')(obj, **kwargs)


def deserialize(serializer, stream_or_string, **mod_kwargs):
    '''
    Deserialize a Python object using a :py:mod:`serializer module
    <salt.serializers>`

    CLI Example:

    .. code-block:: bash

        salt '*' slsutil.deserialize 'json' '{"foo": "Foo!"}'
        salt '*' --no-parse=stream_or_string slsutil.deserialize 'json' \\
            stream_or_string='{"foo": "Foo!"}'

    Jinja Example:

    .. code-block:: jinja

        {% set python_object = salt.slsutil.deserialize('json',
            '{"foo": "Foo!"}') %}
    '''
    kwargs = salt.utils.args.clean_kwargs(**mod_kwargs)
    return _get_serialize_fn(serializer, 'deserialize')(stream_or_string,
            **kwargs)


def banner(width=72, commentchar='#', borderchar='#', blockstart=None, blockend=None,
           title=None, text=None, newline=False):
    '''
    Create a standardized comment block to include in a templated file.

    A common technique in configuration management is to include a comment
    block in managed files, warning users not to modify the file. This
    function simplifies and standardizes those comment blocks.

    :param width: The width, in characters, of the banner. Default is 72.
    :param commentchar: The character to be used in the starting position of
        each line. This value should be set to a valid line comment character
        for the syntax of the file in which the banner is being inserted.
        Multiple character sequences, like '//' are supported.
        If the file's syntax does not support line comments (such as XML),
        use the ``blockstart`` and ``blockend`` options.
    :param borderchar: The character to use in the top and bottom border of
        the comment box. Must be a single character.
    :param blockstart: The character sequence to use at the beginning of a
        block comment. Should be used in conjunction with ``blockend``
    :param blockend: The character sequence to use at the end of a
        block comment. Should be used in conjunction with ``blockstart``
    :param title: The first field of the comment block. This field appears
        centered at the top of the box.
    :param text: The second filed of the comment block. This field appears
        left-justifed at the bottom of the box.
    :param newline: Boolean value to indicate whether the comment block should
        end with a newline. Default is ``False``.

    This banner can be injected into any templated file, for example:

    .. code-block:: jinja

        {{ salt['slsutil.banner'](width=120, commentchar='//') }}

    The default banner:

    .. code-block:: none

        ########################################################################
        #                                                                      #
        #              THIS FILE IS MANAGED BY SALT - DO NOT EDIT              #
        #                                                                      #
        # The contents of this file are managed by Salt. Any changes to this   #
        # file may be overwritten automatically and without warning.           #
        ########################################################################
    '''

    if title is None:
        title = 'THIS FILE IS MANAGED BY SALT - DO NOT EDIT'

    if text is None:
        text = ('The contents of this file are managed by Salt. '
                'Any changes to this file may be overwritten '
                'automatically and without warning')

    # Set up some typesetting variables
    lgutter = commentchar.strip() + ' '
    rgutter = ' ' + commentchar.strip()
    textwidth = width - len(lgutter) - len(rgutter)
    border_line = commentchar + borderchar[:1] * (width - len(commentchar) * 2) + commentchar
    spacer_line = commentchar + ' ' * (width - len(commentchar) * 2) + commentchar
    wrapper = textwrap.TextWrapper(width=(width - len(lgutter) - len(rgutter)))
    block = list()

    # Create the banner
    if blockstart is not None:
        block.append(blockstart)
    block.append(border_line)
    block.append(spacer_line)
    for line in wrapper.wrap(title):
        block.append(lgutter + line.center(textwidth) + rgutter)
    block.append(spacer_line)
    for line in wrapper.wrap(text):
        block.append(lgutter + line + ' ' * (textwidth - len(line)) + rgutter)
    block.append(border_line)
    if blockend is not None:
        block.append(blockend)

    # Convert list to multi-line string
    result = os.linesep.join(block)

    # Add a newline character to the end of the banner
    if newline:
        return result + os.linesep

    return result


def boolstr(value, true='true', false='false'):
    '''
    Convert a boolean value into a string. This function is
    intended to be used from within file templates to provide
    an easy way to take boolean values stored in Pillars or
    Grains, and write them out in the appropriate syntax for
    a particular file template.

    :param value: The boolean value to be converted
    :param true: The value to return if ``value`` is ``True``
    :param false: The value to return if ``value`` is ``False``

    In this example, a pillar named ``smtp:encrypted`` stores a boolean
    value, but the template that uses that value needs ``yes`` or ``no``
    to be written, based on the boolean value.

    *Note: this is written on two lines for clarity. The same result
    could be achieved in one line.*

    .. code-block:: jinja

        {% set encrypted = salt[pillar.get]('smtp:encrypted', false) %}
        use_tls: {{ salt['slsutil.boolstr'](encrypted, 'yes', 'no') }}

    Result (assuming the value is ``True``):

    .. code-block:: none

        use_tls: yes

    '''

    if value:
        return true

    return false
