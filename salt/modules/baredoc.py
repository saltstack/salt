# -*- coding: utf-8 -*-
"""
Baredoc walks the installed module and state directories and generates
dictionaries and lists of the function names and their arguments.

.. versionadded:: Sodium

"""
from __future__ import absolute_import, print_function, unicode_literals

import ast

# Import python libs
import logging
import os

# Import salt libs
import salt.utils.files
from salt.ext.six.moves import zip_longest

# Import 3rd-party libs
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)


def _get_module_name(tree, filename):
    """
    Returns the value of __virtual__ if found.
    Otherwise, returns filename
    """
    module_name = os.path.basename(filename).split(".")[0]
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)]
    for assign in assignments:
        try:
            if assign.targets[0].id == "__virtualname__":
                module_name = assign.value.s
        except AttributeError:
            pass
    return module_name


def _get_func_aliases(tree):
    """
    Get __func_alias__ dict for mapping function names
    """
    fun_aliases = {}
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)]
    for assign in assignments:
        try:
            if assign.targets[0].id == "__func_alias__":
                for key, value in zip_longest(assign.value.keys, assign.value.values):
                    fun_aliases.update({key.s: value.s})
        except AttributeError:
            pass
    return fun_aliases


def _get_args(function):
    """
    Given a function def, returns arguments and defaults
    """
    # Generate list of arguments
    arg_strings = []
    list_of_arguments = function.args.args
    if list_of_arguments:
        for arg in list_of_arguments:
            arg_strings.append(arg.arg)

    # Generate list of arg defaults
    # Values are only returned for populated items
    arg_default_strings = []
    list_arg_defaults = function.args.defaults
    if list_arg_defaults:
        for arg_default in list_arg_defaults:
            if isinstance(arg_default, ast.NameConstant):
                arg_default_strings.append(arg_default.value)
            elif isinstance(arg_default, ast.Num):
                arg_default_strings.append(arg_default.n)

    # Since only some args may have default values, need to zip in reverse order
    backwards_args = OrderedDict(
        zip_longest(reversed(arg_strings), reversed(arg_default_strings))
    )
    ordered_args = OrderedDict(reversed(list(backwards_args.items())))

    try:
        ordered_args["args"] = function.args.vararg.arg
    except AttributeError:
        pass
    try:
        ordered_args["kwargs"] = function.args.kwarg.arg
    except AttributeError:
        pass

    return ordered_args


def _mods_with_args(module_py, names_only):
    """
    Start ast parsing of modules
    """
    ret = {}
    with salt.utils.files.fopen(module_py, "r") as cur_file:
        tree = ast.parse(cur_file.read())
        module_name = _get_module_name(tree, module_py)
        fun_aliases = _get_func_aliases(tree)

        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        func_list = []
        for fn in functions:
            if not fn.name.startswith("_"):
                function_name = fn.name
                if fun_aliases:
                    # Translate name to __func_alias__ version
                    for k, v in fun_aliases.items():
                        if fn.name == k:
                            function_name = v
                args = _get_args(fn)
                if names_only:
                    func_list.append(function_name)
                else:
                    fun_entry = {}
                    fun_entry[function_name] = args
                    func_list.append(fun_entry)
        ret[module_name] = func_list
    return ret


def _modules_and_args(name=False, type="states", names_only=False):
    """
    Determine if modules or states directories or files are requested
    """
    ret = {}
    dirs = ""
    module_dir = os.path.dirname(os.path.realpath(__file__))
    state_dir = os.path.join(os.path.dirname(module_dir), "states")

    if name:
        if type == "modules":
            module_py = os.path.join(module_dir, name + ".py")
        else:
            module_py = os.path.join(state_dir, name + ".py")
        return _mods_with_args(module_py, names_only)
    else:
        if type == "modules":
            dirs = module_dir
        if type == "states":
            dirs = state_dir

    for module_py in os.listdir(dirs):
        if module_py.endswith(".py") and module_py != "__init__.py":
            ret.update(_mods_with_args(os.path.join(dirs, module_py), names_only))
    return ret


def list_states(name=False, names_only=False):
    """
    Walk the Salt install tree for state modules and return a
    dictionary or a list of their functions as well as their arguments.

    :param name: specify a specific module to list. If not specified, all modules will be listed.
    :param names_only: Return only a list of the callable functions instead of a dictionary with arguments
    :return: An OrderedDict with callable function names as keys and lists of arguments as
             values (if ``names_only``==False) or simply an ordered list of callable
             function nanes (if ``names_only``==True).

    CLI Example:
    (example truncated for brevity)

    .. code-block:: bash

        salt myminion baredoc.modules_and_args

        myminion:
            ----------
        [...]
          at:
          - present:
              name: null
              timespec: null
              tag: null
              user: null
              job: null
              unique_tag: false
           - absent:
              name: null
              jobid: null
              kwargs: kwargs
           - watch:
              name: null
              timespec: null
              tag: null
              user: null
              job: null
              unique_tag: false
           - mod_watch:
              name: null
              kwargs: kwargs
        [...]
    """
    ret = _modules_and_args(name, type="states", names_only=names_only)
    if names_only:
        return OrderedDict(sorted(ret.items()))
    else:
        return OrderedDict(sorted(ret.items()))


def list_modules(name=False, names_only=False):
    """
    Walk the Salt install tree for execution modules and return a
    dictionary or a list of their functions as well as their arguments.

    :param name: specify a specific module to list. If not specified, all modules will be listed.
    :param names_only: Return only a list of the callable functions instead of a dictionary with arguments
    :return: An OrderedDict with callable function names as keys and lists of arguments as
             values (if ``names_only``==False) or simply an ordered list of callable
             function nanes (if ``names_only``==True).

    CLI Example:
    (example truncated for brevity)

    .. code-block:: bash

        salt myminion baredoc.modules_and_args

        myminion:
            ----------
        [...]
          at:
        - atq:
            tag: null
          - atrm:
            args: args
          - at:
            args: args
            kwargs: kwargs
          - atc:
            jobid: null
          - jobcheck:
            kwargs: kwargs
        [...]
    """
    ret = _modules_and_args(name, type="modules", names_only=names_only)
    if names_only:
        return OrderedDict(sorted(ret.items()))
    else:
        return OrderedDict(sorted(ret.items()))
