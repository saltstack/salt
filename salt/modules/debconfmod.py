"""
Support for Debconf
"""

import logging
import os
import re

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
import salt.utils.versions

log = logging.getLogger(__name__)

__func_alias__ = {"set_": "set"}

# Define the module's virtual name
__virtualname__ = "debconf"


def __virtual__():
    """
    Confirm this module is on a Debian based system and that debconf-utils
    is installed.
    """
    if __grains__["os_family"] != "Debian":
        return (
            False,
            "The debconfmod module could not be loaded: unsupported OS family",
        )

    if salt.utils.path.which("debconf-get-selections") is None:
        return (
            False,
            "The debconfmod module could not be loaded: "
            "debconf-utils is not installed.",
        )

    return __virtualname__


def _unpack_lines(out):
    """
    Unpack the debconf lines
    """
    rexp = (
        "(?ms)"
        "^(?P<package>[^#]\\S+)[\t ]+"
        "(?P<question>\\S+)[\t ]+"
        "(?P<type>\\S+)[\t ]+"
        "(?P<value>[^\n]*)$"
    )
    lines = re.findall(rexp, out)
    return lines


def get_selections(fetchempty=True):
    """
    Answers to debconf questions for all packages in the following format::

        {'package': [['question', 'type', 'value'], ...]}

    CLI Example:

    .. code-block:: bash

        salt '*' debconf.get_selections
    """
    selections = {}
    cmd = "debconf-get-selections"

    out = __salt__["cmd.run_stdout"](cmd)

    lines = _unpack_lines(out)

    for line in lines:
        package, question, type_, value = line
        if fetchempty or value:
            (selections.setdefault(package, []).append([question, type_, value]))

    return selections


def show(name):
    """
    Answers to debconf questions for a package in the following format::

        [['question', 'type', 'value'], ...]

    If debconf doesn't know about a package, we return None.

    CLI Example:

    .. code-block:: bash

        salt '*' debconf.show <package name>
    """
    selections = get_selections()

    result = selections.get(name)
    return result


def _set_file(path):
    """
    Execute the set selections command for debconf
    """
    cmd = "debconf-set-selections {}".format(path)

    __salt__["cmd.run_stdout"](cmd, python_shell=False)


def set_(package, question, type, value, *extra):
    """
    Set answers to debconf questions for a package.

    CLI Example:

    .. code-block:: bash

        salt '*' debconf.set <package> <question> <type> <value> [<value> ...]
    """

    if extra:
        value = " ".join((value,) + tuple(extra))

    fd_, fname = salt.utils.files.mkstemp(prefix="salt-", close_fd=False)

    line = "{} {} {} {}".format(package, question, type, value)
    os.write(fd_, salt.utils.stringutils.to_bytes(line))
    os.close(fd_)

    _set_file(fname)

    os.unlink(fname)

    return True


def set_template(path, template, context, defaults, saltenv="base", **kwargs):
    """
    Set answers to debconf questions from a template.

    path
        location of the file containing the package selections

    template
        template format

    context
        variables to add to the template environment

    default
        default values for the template environment

    CLI Example:

    .. code-block:: bash

        salt '*' debconf.set_template salt://pathto/pkg.selections.jinja jinja None None

    """

    path = __salt__["cp.get_template"](
        path=path,
        dest=None,
        template=template,
        saltenv=saltenv,
        context=context,
        defaults=defaults,
        **kwargs
    )

    return set_file(path, saltenv, **kwargs)


def set_file(path, saltenv="base", **kwargs):
    """
    Set answers to debconf questions from a file.

    CLI Example:

    .. code-block:: bash

        salt '*' debconf.set_file salt://pathto/pkg.selections
    """
    if "__env__" in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop("__env__")

    path = __salt__["cp.cache_file"](path, saltenv)
    if path:
        _set_file(path)
        return True

    return False
