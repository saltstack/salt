"""
Baredoc walks the installed module and state directories and generates
dictionaries and lists of the function names and their arguments.

.. versionadded:: 3001

"""

import ast
import itertools
import logging
import os
from typing import Dict, List

import salt.utils.doc
import salt.utils.files
from salt.exceptions import ArgumentValueError
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)


def _get_module_name(tree, filename: str) -> str:
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


def _get_func_aliases(tree) -> Dict:
    """
    Get __func_alias__ dict for mapping function names
    """
    fun_aliases = {}
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)]
    for assign in assignments:
        try:
            if assign.targets[0].id == "__func_alias__":
                for key, value in itertools.zip_longest(
                    assign.value.keys, assign.value.values
                ):
                    fun_aliases.update({key.s: value.s})
        except AttributeError:
            pass
    return fun_aliases


def _get_args(function: str) -> Dict:
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
            elif isinstance(arg_default, ast.Str):
                arg_default_strings.append(arg_default.s)
            elif isinstance(arg_default, ast.Num):
                arg_default_strings.append(arg_default.n)

    # Since only some args may have default values, need to zip in reverse order
    backwards_args = OrderedDict(
        itertools.zip_longest(reversed(arg_strings), reversed(arg_default_strings))
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


def _parse_module_docs(module_path, mod_name=None):
    """
    Gather module docstrings or module.function doc string if requested
    """
    ret = {}
    with salt.utils.files.fopen(module_path, "r", encoding="utf8") as cur_file:
        tree = ast.parse(cur_file.read())
        module_name = _get_module_name(tree, module_path)

        if not mod_name or "." not in mod_name:
            # Return top level docs for the module if a function is not requested
            ret[module_name] = ast.get_docstring(tree)

        fun_aliases = _get_func_aliases(tree)
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        for fn in functions:
            doc_string = ast.get_docstring(fn)
            if not fn.name.startswith("_"):
                function_name = fn.name
                if fun_aliases:
                    # Translate name to __func_alias__ version
                    for k, v in fun_aliases.items():
                        if fn.name == k:
                            function_name = v
                if mod_name and "." in mod_name:
                    if function_name == mod_name.split(".")[1]:
                        ret[f"{module_name}.{function_name}"] = doc_string
                else:
                    ret[f"{module_name}.{function_name}"] = doc_string
    return salt.utils.doc.strip_rst(ret)


def _parse_module_functions(module_py: str, return_type: str) -> Dict:
    """
    Parse module files for proper module_name and function name, then gather
    functions and possibly arguments
    """
    ret = {}
    with salt.utils.files.fopen(module_py, "r", encoding="utf8") as cur_file:
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
                if return_type == "names":
                    func_list.append(function_name)
                else:
                    # return_type == args so gather and return all args
                    fun_entry = {}
                    fun_entry[function_name] = args
                    func_list.append(fun_entry)
        ret[module_name] = func_list
    return ret


def _get_files(name=False, type="states", return_type="args") -> List:
    """
    Determine if modules/states directories or files are requested

    return_type = names ==  names_only=True
    return_type = args == names_only=Fals
    return_type = docs
    """
    dirs = []
    found_files = []

    if type == "modules":
        dirs.append(os.path.join(__opts__["extension_modules"], "modules"))
        dirs.append(os.path.join(__grains__["saltpath"], "modules"))
    elif type == "states":
        dirs.append(os.path.join(__opts__["extension_modules"], "states"))
        dirs.append(os.path.join(__grains__["saltpath"], "states"))

    if name:
        if "." in name:
            if return_type != "docs":
                # Only docs support module.function syntax
                raise ArgumentValueError("Function name given")
            else:
                name = name.split(".")[0]
        for dir in dirs:
            # Process custom dirs first so custom results are returned
            file_path = os.path.join(dir, name + ".py")
            if os.path.exists(file_path):
                found_files.append(file_path)
                return found_files
    else:
        for dir in reversed(dirs):
            # Process custom dirs last so they are displayed
            try:
                for module_py in os.listdir(dir):
                    if module_py.endswith(".py") and module_py != "__init__.py":
                        found_files.append(os.path.join(dir, module_py))
            except FileNotFoundError:
                pass
    return found_files


def list_states(name=False, names_only=False):
    """
    Walk the Salt install tree for state modules and return a
    dictionary or a list of their functions as well as their arguments.

    :param name: specify a specific module to list. If not specified, all modules will be listed.
    :param names_only: Return only a list of the callable functions instead of a dictionary with arguments

    CLI Example:

    (example truncated for brevity)

    .. code-block:: bash

        salt myminion baredoc.list_states

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
    ret = {}
    if names_only:
        return_type = "names"
    else:
        return_type = "args"
    found_files = _get_files(name, type="states", return_type=return_type)
    for file in found_files:
        ret.update(_parse_module_functions(file, return_type=return_type))
    return OrderedDict(sorted(ret.items()))


def list_modules(name=False, names_only=False):
    """
    Walk the Salt install tree for execution modules and return a
    dictionary or a list of their functions as well as their arguments.

    :param name: specify a specific module to list. If not specified, all modules will be listed.
    :param names_only: Return only a list of the callable functions instead of a dictionary with arguments

    CLI Example:

    .. code-block:: bash

        salt myminion baredoc.list_modules

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
    ret = {}
    if names_only:
        return_type = "names"
    else:
        return_type = "args"
    found_files = _get_files(name, type="modules", return_type=return_type)
    for file in found_files:
        ret.update(_parse_module_functions(file, return_type=return_type))
    return OrderedDict(sorted(ret.items()))


def state_docs(*names):
    """
    Return the docstrings for all state modules. Optionally, specify a state module or a
    function to narrow the selection.

    :param name: specify a specific module to list.

    CLI Example:

    .. code-block:: bash

        salt myminion baredoc.state_docs at
    """
    return_type = "docs"
    ret = {}
    if names:
        for name in names:
            file = _get_files(name, type="states", return_type=return_type)[0]
            ret.update(_parse_module_docs(file, name))
        return OrderedDict(sorted(ret.items()))
    else:
        found_files = []
        found_files.extend(_get_files(type="states", return_type=return_type))
    for file in found_files:
        ret.update(_parse_module_docs(file))
    return OrderedDict(sorted(ret.items()))


def module_docs(*names):
    """
    Return the docstrings for all modules. Optionally, specify a module or a
    function to narrow the selection.

    :param name: specify a specific module to list.

    CLI Example:

    .. code-block:: bash

        salt myminion baredoc.module_docs
    """
    return_type = "docs"
    ret = {}
    if names:
        for name in names:
            file = _get_files(name, type="modules", return_type=return_type)[0]
            ret.update(_parse_module_docs(file, name))
        return OrderedDict(sorted(ret.items()))
    else:
        found_files = []
        found_files.extend(_get_files(type="modules", return_type=return_type))
    for file in found_files:
        ret.update(_parse_module_docs(file))
    return OrderedDict(sorted(ret.items()))
