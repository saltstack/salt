"""
Managing python installations with pyenv
========================================

This module is used to install and manage python installations with pyenv.
Different versions of python can be installed, and uninstalled. pyenv will
be installed automatically the first time it is needed and can be updated
later. This module will *not* automatically install packages which pyenv
will need to compile the versions of python.

If pyenv is run as the root user then it will be installed to /usr/local/pyenv,
otherwise it will be installed to the users ~/.pyenv directory. To make
pyenv available in the shell you may need to add the pyenv/shims and pyenv/bin
directories to the users PATH. If you are installing as root and want other
users to be able to access pyenv then you will need to add pyenv_ROOT to
their environment.

This is how a state configuration could look like:

.. code-block:: yaml

    pyenv-deps:
      pkg.installed:
        - pkgs:
          - make
          - build-essential
          - libssl-dev
          - zlib1g-dev
          - libbz2-dev
          - libreadline-dev
          - libsqlite3-dev
          - wget
          - curl
          - llvm
    python-2.6:
      pyenv.absent:
        - require:
          - pkg: pyenv-deps

    python-2.7.6:
      pyenv.installed:
        - default: True
        - require:
          - pkg: pyenv-deps

.. note::
    Git needs to be installed and available via PATH if pyenv is to be
    installed automatically by the module.
"""

import re


def _check_pyenv(ret, user=None):
    """
    Check to see if pyenv is installed.
    """
    if not __salt__["pyenv.is_installed"](user):
        ret["result"] = False
        ret["comment"] = "pyenv is not installed."
    return ret


def _python_installed(ret, python, user=None):
    """
    Check to see if given python is installed.
    """
    default = __salt__["pyenv.default"](runas=user)
    for version in __salt__["pyenv.versions"](user):
        if version == python:
            ret["result"] = True
            ret["comment"] = "Requested python exists."
            ret["default"] = default == python
            break

    return ret


def _check_and_install_python(ret, python, default=False, user=None):
    """
    Verify that python is installed, install if unavailable
    """
    ret = _python_installed(ret, python, user=user)
    if not ret["result"]:
        if __salt__["pyenv.install_python"](python, runas=user):
            ret["result"] = True
            ret["changes"][python] = "Installed"
            ret["comment"] = "Successfully installed python"
            ret["default"] = default
        else:
            ret["result"] = False
            ret["comment"] = "Could not install python."
            return ret

    if default:
        __salt__["pyenv.default"](python, runas=user)

    return ret


def installed(name, default=False, user=None):
    """
    Verify that the specified python is installed with pyenv. pyenv is
    installed if necessary.

    name
        The version of python to install

    default : False
        Whether to make this python the default.

    user: None
        The user to run pyenv as.

        .. versionadded:: 0.17.0

    .. versionadded:: 0.16.0
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if name.startswith("python-"):
        name = re.sub(r"^python-", "", name)

    if __opts__["test"]:
        ret["comment"] = f"python {name} is set to be installed"
        return ret

    ret = _check_pyenv(ret, user)
    if ret["result"] is False:
        if not __salt__["pyenv.install"](user):
            ret["comment"] = "pyenv failed to install"
            return ret
        else:
            return _check_and_install_python(ret, name, default, user=user)
    else:
        return _check_and_install_python(ret, name, default, user=user)


def _check_and_uninstall_python(ret, python, user=None):
    """
    Verify that python is uninstalled
    """
    ret = _python_installed(ret, python, user=user)
    if ret["result"]:
        if ret["default"]:
            __salt__["pyenv.default"]("system", runas=user)

        if __salt__["pyenv.uninstall_python"](python, runas=user):
            ret["result"] = True
            ret["changes"][python] = "Uninstalled"
            ret["comment"] = "Successfully removed python"
            return ret
        else:
            ret["result"] = False
            ret["comment"] = "Failed to uninstall python"
            return ret
    else:
        ret["result"] = True
        ret["comment"] = f"python {python} is already absent"

    return ret


def absent(name, user=None):
    """
    Verify that the specified python is not installed with pyenv. pyenv
    is installed if necessary.

    name
        The version of python to uninstall

    user: None
        The user to run pyenv as.

        .. versionadded:: 0.17.0

    .. versionadded:: 0.16.0
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if name.startswith("python-"):
        name = re.sub(r"^python-", "", name)

    if __opts__["test"]:
        ret["comment"] = f"python {name} is set to be uninstalled"
        return ret

    ret = _check_pyenv(ret, user)
    if ret["result"] is False:
        ret["result"] = True
        ret["comment"] = f"pyenv not installed, {name} not either"
        return ret
    else:
        return _check_and_uninstall_python(ret, name, user=user)


def install_pyenv(name, user=None):
    """
    Install pyenv if not installed. Allows you to require pyenv be installed
    prior to installing the plugins. Useful if you want to install pyenv
    plugins via the git or file modules and need them installed before
    installing any rubies.

    Use the pyenv.root configuration option to set the path for pyenv if you
    want a system wide install that is not in a user home dir.

    user: None
        The user to run pyenv as.
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if __opts__["test"]:
        ret["comment"] = "pyenv is set to be installed"
        return ret

    return _check_and_install_python(ret, user)
