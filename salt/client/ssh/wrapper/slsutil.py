import os.path
import posixpath

import salt.exceptions
import salt.loader
import salt.template
import salt.utils.args
import salt.utils.dictupdate
import salt.utils.stringio

CONTEXT_BASE = "slsutil"


def update(dest, upd, recursive_update=True, merge_lists=False):
    """
    Merge ``upd`` recursively into ``dest``

    If ``merge_lists=True``, will aggregate list object types instead of
    replacing. This behavior is only activated when ``recursive_update=True``.

    CLI Example:

    .. code-block:: shell

        salt '*' slsutil.update '{foo: Foo}' '{bar: Bar}'

    """
    return salt.utils.dictupdate.update(dest, upd, recursive_update, merge_lists)


def merge(obj_a, obj_b, strategy="smart", renderer="yaml", merge_lists=False):
    """
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
    """
    return salt.utils.dictupdate.merge(obj_a, obj_b, strategy, renderer, merge_lists)


def merge_all(lst, strategy="smart", renderer="yaml", merge_lists=False):
    """
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
    """

    ret = {}
    for obj in lst:
        ret = salt.utils.dictupdate.merge(ret, obj, strategy, renderer, merge_lists)

    return ret


def renderer(path=None, string=None, default_renderer="jinja|yaml", **kwargs):
    """
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
        salt '*' slsutil.renderer /path/to/file.jinja default_renderer='jinja'
        salt '*' slsutil.renderer /path/to/file.sls default_renderer='jinja|yaml'
        salt '*' slsutil.renderer string='Inline template! {{ saltenv }}'
        salt '*' slsutil.renderer string='Hello, {{ name }}.' name='world'
    """
    if not path and not string:
        raise salt.exceptions.SaltInvocationError("Must pass either path or string")

    renderers = salt.loader.render(__opts__, __salt__)

    if path:
        path_or_string = __context__["fileclient"].get_url(
            path, "", saltenv=kwargs.get("saltenv", "base")
        )
    elif string:
        path_or_string = ":string:"
        kwargs["input_data"] = string

    ret = salt.template.compile_template(
        path_or_string,
        renderers,
        default_renderer,
        __opts__["renderer_blacklist"],
        __opts__["renderer_whitelist"],
        **kwargs,
    )
    return ret.read() if salt.utils.stringio.is_readable(ret) else ret


def _get_serialize_fn(serializer, fn_name):
    serializers = salt.loader.serializers(__opts__)
    fns = getattr(serializers, serializer, None)
    fn = getattr(fns, fn_name, None)

    if not fns:
        raise salt.exceptions.CommandExecutionError(
            f"Serializer '{serializer}' not found."
        )

    if not fn:
        raise salt.exceptions.CommandExecutionError(
            f"Serializer '{serializer}' does not implement {fn_name}."
        )

    return fn


def serialize(serializer, obj, **mod_kwargs):
    """
    Serialize a Python object using one of the available
    :ref:`all-salt.serializers`.

    CLI Example:

    .. code-block:: bash

        salt '*' --no-parse=obj slsutil.serialize 'json' obj="{'foo': 'Foo!'}

    Jinja Example:

    .. code-block:: jinja

        {% set json_string = salt.slsutil.serialize('json',
            {'foo': 'Foo!'}) %}
    """
    kwargs = salt.utils.args.clean_kwargs(**mod_kwargs)
    return _get_serialize_fn(serializer, "serialize")(obj, **kwargs)


def deserialize(serializer, stream_or_string, **mod_kwargs):
    """
    Deserialize a Python object using one of the available
    :ref:`all-salt.serializers`.

    CLI Example:

    .. code-block:: bash

        salt '*' slsutil.deserialize 'json' '{"foo": "Foo!"}'
        salt '*' --no-parse=stream_or_string slsutil.deserialize 'json' \\
            stream_or_string='{"foo": "Foo!"}'

    Jinja Example:

    .. code-block:: jinja

        {% set python_object = salt.slsutil.deserialize('json',
            '{"foo": "Foo!"}') %}
    """
    kwargs = salt.utils.args.clean_kwargs(**mod_kwargs)
    return _get_serialize_fn(serializer, "deserialize")(stream_or_string, **kwargs)


def boolstr(value, true="true", false="false"):
    """
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

    """

    if value:
        return true

    return false


def _set_context(keys, function, fun_args=None, fun_kwargs=None, force=False):
    """
    Convenience function to set a value in the ``__context__`` dictionary.

    .. versionadded:: 3004

    :param keys: The list of keys specifying the dictionary path to set. This
                 list can be of arbitrary length and the path will be created
                 in the dictionary if it does not exist.

    :param function: A python function to be called if the specified path does
                     not exist, if the force parameter is ``True``.

    :param fun_args: A list of positional arguments to the function.

    :param fun_kwargs: A dictionary of keyword arguments to the function.

    :param force: If ``True``, force the ```__context__`` path to be updated.
                  Otherwise, only create it if it does not exist.
    """

    target = __context__

    # Build each level of the dictionary as needed
    for key in keys[:-1]:
        if key not in target:
            target[key] = {}
        target = target[key]

    # Call the supplied function to populate the dictionary
    if force or keys[-1] not in target:
        if not fun_args:
            fun_args = []

        if not fun_kwargs:
            fun_kwargs = {}

        target[keys[-1]] = function(*fun_args, *fun_kwargs)


def file_exists(path, saltenv="base"):
    """
    Return ``True`` if a file exists in the state tree, ``False`` otherwise.

    .. versionadded:: 3004

    :param str path: The fully qualified path to a file in the state tree.
    :param str saltenv: The fileserver environment to search. Default: ``base``

    CLI Example:

    .. code-block:: bash

        salt '*' slsutil.file_exists nginx/defaults.yaml
    """

    _set_context(
        [CONTEXT_BASE, saltenv, "file_list"], __salt__["cp.list_master"], [saltenv]
    )
    return path in __context__[CONTEXT_BASE][saltenv]["file_list"]


def dir_exists(path, saltenv="base"):
    """
    Return ``True`` if a directory exists in the state tree, ``False`` otherwise.

    :param str path: The fully qualified path to a directory in the state tree.
    :param str saltenv: The fileserver environment to search. Default: ``base``

    .. versionadded:: 3004

    CLI Example:

    .. code-block:: bash

        salt '*' slsutil.dir_exists nginx/files
    """

    _set_context(
        [CONTEXT_BASE, saltenv, "dir_list"], __salt__["cp.list_master_dirs"], [saltenv]
    )
    return path in __context__[CONTEXT_BASE][saltenv]["dir_list"]


def path_exists(path, saltenv="base"):
    """
    Return ``True`` if a path exists in the state tree, ``False`` otherwise. The path
    could refer to a file or directory.

    .. versionadded:: 3004

    :param str path: The fully qualified path to a file or directory in the state tree.
    :param str saltenv: The fileserver environment to search. Default: ``base``

    CLI Example:

    .. code-block:: bash

        salt '*' slsutil.path_exists nginx/defaults.yaml
    """

    return file_exists(path, saltenv) or dir_exists(path, saltenv)


def findup(startpath, filenames, saltenv="base"):
    """
    Find the first path matching a filename or list of filenames in a specified
    directory or the nearest ancestor directory. Returns the full path to the
    first file found.

    .. versionadded:: 3004

    :param str startpath: The fileserver path from which to begin the search.
        An empty string refers to the state tree root.
    :param filenames: A filename or list of filenames to search for. Searching for
        directory names is also supported.
    :param str saltenv: The fileserver environment to search. Default: ``base``

    Example: return the path to ``defaults.yaml``, walking up the tree from the
    state file currently being processed.

    .. code-block:: jinja

        {{ salt["slsutil.findup"](tplfile, "defaults.yaml") }}

    CLI Example:

    .. code-block:: bash

        salt '*' slsutil.findup formulas/shared/nginx map.jinja
    """

    # Normalize the path
    if startpath:
        startpath = posixpath.normpath(startpath)

    # Verify the cwd is a valid path in the state tree
    if startpath and not path_exists(startpath, saltenv):
        raise salt.exceptions.SaltInvocationError(
            f"Starting path not found in the state tree: {startpath}"
        )

    # Ensure that patterns is a string or list of strings
    if isinstance(filenames, str):
        filenames = [filenames]
    if not isinstance(filenames, list):
        raise salt.exceptions.SaltInvocationError(
            "Filenames argument must be a string or list of strings"
        )

    while True:

        # Loop over filenames, looking for one at the current path level
        for filename in filenames:
            fullname = salt.utils.path.join(
                startpath or "", filename, use_posixpath=True
            )
            if path_exists(fullname, saltenv):
                return fullname

        # If the root path was just checked, raise an error
        if not startpath:
            raise salt.exceptions.CommandExecutionError(
                "File pattern(s) not found in path ancestry"
            )

        # Move up one level in the ancestry
        startpath = os.path.dirname(startpath)
