"""
The sys module provides information about the available functions on the minion
"""

import fnmatch
import logging

import salt.loader
import salt.runner
import salt.state
import salt.utils.args
import salt.utils.doc
import salt.utils.schema

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "sys"

__proxyenabled__ = ["*"]


def __virtual__():
    """
    Return as sys
    """
    return __virtualname__


def doc(*args):
    """
    Return the docstrings for all modules. Optionally, specify a module or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    Multiple modules/functions can be specified.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.doc
        salt '*' sys.doc sys
        salt '*' sys.doc sys.doc
        salt '*' sys.doc network.traceroute user.info

    Modules can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.doc 'sys.*'
        salt '*' sys.doc 'sys.list_*'
    """
    docs = {}
    if not args:
        for fun in __salt__:
            docs[fun] = __salt__[fun].__doc__
        return salt.utils.doc.strip_rst(docs)

    for module in args:
        _use_fnmatch = False
        if "*" in module:
            target_mod = module
            _use_fnmatch = True
        elif module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            target_mod = module + "." if not module.endswith(".") else module
        else:
            target_mod = ""
        if _use_fnmatch:
            for fun in fnmatch.filter(__salt__, target_mod):
                docs[fun] = __salt__[fun].__doc__
        else:

            for fun in __salt__:
                if fun == module or fun.startswith(target_mod):
                    docs[fun] = __salt__[fun].__doc__
    return salt.utils.doc.strip_rst(docs)


def state_doc(*args):
    """
    Return the docstrings for all states. Optionally, specify a state or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    Multiple states/functions can be specified.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.state_doc
        salt '*' sys.state_doc service
        salt '*' sys.state_doc service.running
        salt '*' sys.state_doc service.running ipables.append

    State names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.state_doc 'service.*' 'iptables.*'

    """
    st_ = salt.state.State(__opts__)

    docs = {}
    if not args:
        for fun in st_.states:
            state = fun.split(".")[0]
            if state not in docs:
                if hasattr(st_.states[fun], "__globals__"):
                    docs[state] = st_.states[fun].__globals__["__doc__"]
            docs[fun] = st_.states[fun].__doc__
        return salt.utils.doc.strip_rst(docs)

    for module in args:
        _use_fnmatch = False
        if "*" in module:
            target_mod = module
            _use_fnmatch = True
        elif module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            target_mod = module + "." if not module.endswith(".") else module
        else:
            target_mod = ""
        if _use_fnmatch:
            for fun in fnmatch.filter(st_.states, target_mod):
                state = fun.split(".")[0]
                if hasattr(st_.states[fun], "__globals__"):
                    docs[state] = st_.states[fun].__globals__["__doc__"]
                docs[fun] = st_.states[fun].__doc__
        else:
            for fun in st_.states:
                if fun == module or fun.startswith(target_mod):
                    state = module.split(".")[0]
                    if state not in docs:
                        if hasattr(st_.states[fun], "__globals__"):
                            docs[state] = st_.states[fun].__globals__["__doc__"]
                    docs[fun] = st_.states[fun].__doc__
    return salt.utils.doc.strip_rst(docs)


def runner_doc(*args):
    """
    Return the docstrings for all runners. Optionally, specify a runner or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    Multiple runners/functions can be specified.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.runner_doc
        salt '*' sys.runner_doc cache
        salt '*' sys.runner_doc cache.grains
        salt '*' sys.runner_doc cache.grains mine.get

    Runner names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.runner_doc 'cache.clear_*'

    """
    run_ = salt.runner.Runner(__opts__)
    docs = {}
    if not args:
        for fun in run_.functions:
            docs[fun] = run_.functions[fun].__doc__
        return salt.utils.doc.strip_rst(docs)

    for module in args:
        _use_fnmatch = False
        if "*" in module:
            target_mod = module
            _use_fnmatch = True
        elif module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            target_mod = module + "." if not module.endswith(".") else module
        else:
            target_mod = ""
        if _use_fnmatch:
            for fun in fnmatch.filter(run_.functions, target_mod):
                docs[fun] = run_.functions[fun].__doc__
        else:
            for fun in run_.functions:
                if fun == module or fun.startswith(target_mod):
                    docs[fun] = run_.functions[fun].__doc__
    return salt.utils.doc.strip_rst(docs)


def returner_doc(*args):
    """
    Return the docstrings for all returners. Optionally, specify a returner or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    Multiple returners/functions can be specified.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.returner_doc
        salt '*' sys.returner_doc sqlite3
        salt '*' sys.returner_doc sqlite3.get_fun
        salt '*' sys.returner_doc sqlite3.get_fun etcd.get_fun

    Returner names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.returner_doc 'sqlite3.get_*'

    """

    returners_ = salt.loader.returners(__opts__, [])
    docs = {}
    if not args:
        for fun in returners_:
            docs[fun] = returners_[fun].__doc__
        return salt.utils.doc.strip_rst(docs)

    for module in args:
        _use_fnmatch = False
        if "*" in module:
            target_mod = module
            _use_fnmatch = True
        elif module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            target_mod = module + "." if not module.endswith(".") else module
        else:
            target_mod = ""
        if _use_fnmatch:
            for fun in returners_:
                if fun == module or fun.startswith(target_mod):
                    docs[fun] = returners_[fun].__doc__
        else:
            for fun in returners_.keys():
                if fun == module or fun.startswith(target_mod):
                    docs[fun] = returners_[fun].__doc__
    return salt.utils.doc.strip_rst(docs)


def renderer_doc(*args):
    """
    Return the docstrings for all renderers. Optionally, specify a renderer or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    Multiple renderers can be specified.

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.renderer_doc
        salt '*' sys.renderer_doc cheetah
        salt '*' sys.renderer_doc jinja json

    Renderer names can be specified as globs.

    .. code-block:: bash

        salt '*' sys.renderer_doc 'c*' 'j*'

    """
    renderers_ = salt.loader.render(__opts__, [])
    docs = {}
    if not args:
        for func in renderers_.keys():
            docs[func] = renderers_[func].__doc__
        return salt.utils.doc.strip_rst(docs)

    for module in args:
        if "*" in module or "." in module:
            for func in fnmatch.filter(renderers_, module):
                docs[func] = renderers_[func].__doc__
        else:
            moduledot = module + "."
            for func in renderers_.keys():
                if func.startswith(moduledot):
                    docs[func] = renderers_[func].__doc__
    return salt.utils.doc.strip_rst(docs)


def list_functions(*args, **kwargs):  # pylint: disable=unused-argument
    """
    List the functions for all modules. Optionally, specify a module or modules
    from which to list.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_functions
        salt '*' sys.list_functions sys
        salt '*' sys.list_functions sys user

    .. versionadded:: 0.12.0

    .. code-block:: bash

        salt '*' sys.list_functions 'module.specific_function'

    Function names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.list_functions 'sys.list_*'

    """
    # ## NOTE: **kwargs is used here to prevent a traceback when garbage
    # ##       arguments are tacked on to the end.

    if not args:
        # We're being asked for all functions
        return sorted(__salt__)

    names = set()
    for module in args:
        if "*" in module or "." in module:
            for func in fnmatch.filter(__salt__, module):
                names.add(func)
        else:
            # "sys" should just match sys without also matching sysctl
            moduledot = module + "."
            for func in __salt__:
                if func.startswith(moduledot):
                    names.add(func)
    return sorted(names)


def list_modules(*args):
    """
    List the modules loaded on the minion

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_modules

    Module names can be specified as globs.

    .. code-block:: bash

        salt '*' sys.list_modules 's*'

    """
    modules = set()
    if not args:
        for func in __salt__:
            modules.add(func.split(".")[0])
        return sorted(modules)

    for module in args:
        if "*" in module:
            for func in fnmatch.filter(__salt__, module):
                modules.add(func.split(".")[0])
        else:
            for func in __salt__:
                mod_test = func.split(".")[0]
                if mod_test == module:
                    modules.add(mod_test)
    return sorted(modules)


def reload_modules():
    """
    Tell the minion to reload the execution modules

    CLI Example:

    .. code-block:: bash

        salt '*' sys.reload_modules
    """
    # This function is actually handled inside the minion.py file, the function
    # is caught before it ever gets here. Therefore, the docstring above is
    # only for the online docs, and ANY CHANGES made to it must also be made in
    # each of the gen_modules() funcs in minion.py.
    return True


def argspec(module=""):
    """
    Return the argument specification of functions in Salt execution
    modules.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.argspec pkg.install
        salt '*' sys.argspec sys
        salt '*' sys.argspec

    Module names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.argspec 'pkg.*'

    """
    return salt.utils.args.argspec_report(__salt__, module)


def state_argspec(module=""):
    """
    Return the argument specification of functions in Salt state
    modules.

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.state_argspec pkg.installed
        salt '*' sys.state_argspec file
        salt '*' sys.state_argspec

    State names can be specified as globs.

    .. code-block:: bash

        salt '*' sys.state_argspec 'pkg.*'

    """
    st_ = salt.state.State(__opts__)
    return salt.utils.args.argspec_report(st_.states, module)


def returner_argspec(module=""):
    """
    Return the argument specification of functions in Salt returner
    modules.

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.returner_argspec xmpp
        salt '*' sys.returner_argspec xmpp smtp
        salt '*' sys.returner_argspec

    Returner names can be specified as globs.

    .. code-block:: bash

        salt '*' sys.returner_argspec 'sqlite3.*'

    """
    returners_ = salt.loader.returners(__opts__, [])
    return salt.utils.args.argspec_report(returners_, module)


def runner_argspec(module=""):
    """
    Return the argument specification of functions in Salt runner
    modules.

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.runner_argspec state
        salt '*' sys.runner_argspec http
        salt '*' sys.runner_argspec

    Runner names can be specified as globs.

    .. code-block:: bash

        salt '*' sys.runner_argspec 'winrepo.*'
    """
    run_ = salt.runner.Runner(__opts__)
    return salt.utils.args.argspec_report(run_.functions, module)


def list_state_functions(*args, **kwargs):  # pylint: disable=unused-argument
    """
    List the functions for all state modules. Optionally, specify a state
    module or modules from which to list.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_state_functions
        salt '*' sys.list_state_functions file
        salt '*' sys.list_state_functions pkg user

    State function names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.list_state_functions 'file.*'
        salt '*' sys.list_state_functions 'file.s*'

    .. versionadded:: 2016.9

    .. code-block:: bash

        salt '*' sys.list_state_functions 'module.specific_function'

    """
    # NOTE: **kwargs is used here to prevent a traceback when garbage
    #       arguments are tacked on to the end.

    st_ = salt.state.State(__opts__)
    if not args:
        # We're being asked for all functions
        return sorted(st_.states)

    names = set()
    for module in args:
        if "*" in module or "." in module:
            for func in fnmatch.filter(st_.states, module):
                names.add(func)
        else:
            # "sys" should just match sys without also matching sysctl
            moduledot = module + "."
            for func in st_.states:
                if func.startswith(moduledot):
                    names.add(func)
    return sorted(names)


def list_state_modules(*args):
    """
    List the modules loaded on the minion

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_state_modules

    State module names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.list_state_modules 'mysql_*'

    """
    st_ = salt.state.State(__opts__)
    modules = set()

    if not args:
        for func in st_.states:
            log.debug("func %s", func)
            modules.add(func.split(".")[0])
        return sorted(modules)

    for module in args:
        if "*" in module:
            for func in fnmatch.filter(st_.states, module):
                modules.add(func.split(".")[0])
        else:
            for func in st_.states:
                mod_test = func.split(".")[0]
                if mod_test == module:
                    modules.add(mod_test)
    return sorted(modules)


def list_runners(*args):
    """
    List the runners loaded on the minion

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_runners

    Runner names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.list_runners 'm*'

    """
    run_ = salt.runner.Runner(__opts__)
    runners = set()
    if not args:
        for func in run_.functions:
            runners.add(func.split(".")[0])
        return sorted(runners)

    for module in args:
        if "*" in module:
            for func in fnmatch.filter(run_.functions, module):
                runners.add(func.split(".")[0])
        else:
            for func in run_.functions:
                mod_test = func.split(".")[0]
                if mod_test == module:
                    runners.add(mod_test)
    return sorted(runners)


def list_runner_functions(*args, **kwargs):  # pylint: disable=unused-argument
    """
    List the functions for all runner modules. Optionally, specify a runner
    module or modules from which to list.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_runner_functions
        salt '*' sys.list_runner_functions state
        salt '*' sys.list_runner_functions state virt

    Runner function names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.list_runner_functions 'state.*' 'virt.*'

    """
    # ## NOTE: **kwargs is used here to prevent a traceback when garbage
    # ##       arguments are tacked on to the end.

    run_ = salt.runner.Runner(__opts__)
    if not args:
        # We're being asked for all functions
        return sorted(run_.functions)

    names = set()
    for module in args:
        if "*" in module or "." in module:
            for func in fnmatch.filter(run_.functions, module):
                names.add(func)
        else:
            # "sys" should just match sys without also matching sysctl
            moduledot = module + "."
            for func in run_.functions:
                if func.startswith(moduledot):
                    names.add(func)
    return sorted(names)


def list_returners(*args):
    """
    List the returners loaded on the minion

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_returners

    Returner names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.list_returners 's*'

    """
    returners_ = salt.loader.returners(__opts__, [])
    returners = set()

    if not args:
        for func in returners_.keys():
            returners.add(func.split(".")[0])
        return sorted(returners)

    for module in args:
        if "*" in module:
            for func in fnmatch.filter(returners_, module):
                returners.add(func.split(".")[0])
        else:
            for func in returners_:
                mod_test = func.split(".")[0]
                if mod_test == module:
                    returners.add(mod_test)
    return sorted(returners)


def list_returner_functions(*args, **kwargs):  # pylint: disable=unused-argument
    """
    List the functions for all returner modules. Optionally, specify a returner
    module or modules from which to list.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_returner_functions
        salt '*' sys.list_returner_functions mysql
        salt '*' sys.list_returner_functions mysql etcd

    Returner names can be specified as globs.

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' sys.list_returner_functions 'sqlite3.get_*'

    """
    # NOTE: **kwargs is used here to prevent a traceback when garbage
    #       arguments are tacked on to the end.

    returners_ = salt.loader.returners(__opts__, [])
    if not args:
        # We're being asked for all functions
        return sorted(returners_)

    names = set()
    for module in args:
        if "*" in module or "." in module:
            for func in fnmatch.filter(returners_, module):
                names.add(func)
        else:
            # "sys" should just match sys without also matching sysctl
            moduledot = module + "."
            for func in returners_:
                if func.startswith(moduledot):
                    names.add(func)
    return sorted(names)


def list_renderers(*args):
    """
    List the renderers loaded on the minion

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_renderers

    Render names can be specified as globs.

    .. code-block:: bash

        salt '*' sys.list_renderers 'yaml*'

    """
    renderers_ = salt.loader.render(__opts__, [])
    renderers = set()

    if not args:
        for rend in renderers_.keys():
            renderers.add(rend)
        return sorted(renderers)

    for module in args:
        for rend in fnmatch.filter(renderers_, module):
            renderers.add(rend)
    return sorted(renderers)


def _argspec_to_schema(mod, spec):
    args = spec["args"]
    defaults = spec["defaults"] or []

    args_req = args[: len(args) - len(defaults)]
    args_defaults = list(zip(args[-len(defaults) :], defaults))

    types = {
        "title": mod,
        "description": mod,
    }

    for i in args_req:
        types[i] = salt.utils.schema.OneOfItem(
            items=(
                salt.utils.schema.BooleanItem(title=i, description=i, required=True),
                salt.utils.schema.IntegerItem(title=i, description=i, required=True),
                salt.utils.schema.NumberItem(title=i, description=i, required=True),
                salt.utils.schema.StringItem(title=i, description=i, required=True),
                # S.ArrayItem(title=i, description=i, required=True),
                # S.DictItem(title=i, description=i, required=True),
            )
        )

    for i, j in args_defaults:
        types[i] = salt.utils.schema.OneOfItem(
            items=(
                salt.utils.schema.BooleanItem(title=i, description=i, default=j),
                salt.utils.schema.IntegerItem(title=i, description=i, default=j),
                salt.utils.schema.NumberItem(title=i, description=i, default=j),
                salt.utils.schema.StringItem(title=i, description=i, default=j),
                # S.ArrayItem(title=i, description=i, default=j),
                # S.DictItem(title=i, description=i, default=j),
            )
        )

    return type(mod, (salt.utils.schema.Schema,), types).serialize()


def state_schema(module=""):
    """
    Return a JSON Schema for the given state function(s)

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' sys.state_schema
        salt '*' sys.state_schema pkg.installed
    """
    specs = state_argspec(module)

    schemas = []
    for state_mod, state_spec in specs.items():
        schemas.append(_argspec_to_schema(state_mod, state_spec))

    return schemas
