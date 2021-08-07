"""
Create virtualenv environments.

.. versionadded:: 0.17.0
"""


import glob
import logging
import os
import re
import shutil
import sys

import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.verify
from salt.exceptions import CommandExecutionError, SaltInvocationError

KNOWN_BINARY_NAMES = frozenset(
    [
        "virtualenv-{}.{}".format(*sys.version_info[:2]),
        "virtualenv{}".format(sys.version_info[0]),
        "virtualenv",
    ]
)

log = logging.getLogger(__name__)

__opts__ = {"venv_bin": salt.utils.path.which_bin(KNOWN_BINARY_NAMES) or "virtualenv"}

__pillar__ = {}

# Define the module's virtual name
__virtualname__ = "virtualenv"


def __virtual__():
    return __virtualname__


def virtualenv_ver(venv_bin, user=None, **kwargs):
    """
    return virtualenv version if exists
    """
    # Virtualenv package
    try:
        import virtualenv

        version = getattr(virtualenv, "__version__", None)
        if not version:
            version = virtualenv.virtualenv_version
    except ImportError:
        # Unable to import?? Let's parse the version from the console
        version_cmd = [venv_bin, "--version"]
        ret = __salt__["cmd.run_all"](
            version_cmd, runas=user, python_shell=False, redirect_stderr=True, **kwargs
        )
        if ret["retcode"] > 0 or not ret["stdout"].strip():
            raise CommandExecutionError(
                "Unable to get the virtualenv version output using '{}'. "
                "Returned data: {}".format(version_cmd, ret)
            )
        # 20.0.0 virtualenv changed the --version output. find version number
        version = "".join(
            [x for x in ret["stdout"].strip().split() if re.search(r"^\d.\d*", x)]
        )
    virtualenv_version_info = tuple(
        [int(i) for i in re.sub(r"(rc|\+ds).*$", "", version).split(".")]
    )
    return virtualenv_version_info


def create(
    path,
    venv_bin=None,
    system_site_packages=False,
    distribute=False,
    clear=False,
    python=None,
    extra_search_dir=None,
    never_download=None,
    prompt=None,
    pip=False,
    symlinks=None,
    upgrade=None,
    user=None,
    use_vt=False,
    saltenv="base",
    **kwargs
):
    """
    Create a virtualenv

    path
        The path to the virtualenv to be created

    venv_bin
        The name (and optionally path) of the virtualenv command. This can also
        be set globally in the minion config file as ``virtualenv.venv_bin``.
        Defaults to ``virtualenv``.

    system_site_packages : False
        Passthrough argument given to virtualenv or pyvenv

    distribute : False
        Passthrough argument given to virtualenv

    pip : False
        Install pip after creating a virtual environment. Implies
        ``distribute=True``

    clear : False
        Passthrough argument given to virtualenv or pyvenv

    python : None (default)
        Passthrough argument given to virtualenv

    extra_search_dir : None (default)
        Passthrough argument given to virtualenv

    never_download : None (default)
        Passthrough argument given to virtualenv if True

    prompt : None (default)
        Passthrough argument given to virtualenv if not None

    symlinks : None
        Passthrough argument given to pyvenv if True

    upgrade : None
        Passthrough argument given to pyvenv if True

    user : None
        Set ownership for the virtualenv

        .. note::
            On Windows you must also pass a ``password`` parameter. Additionally,
            the user must have permissions to the location where the virtual
            environment is being created

    runas : None
        Set ownership for the virtualenv

        .. deprecated:: 2014.1.0
            ``user`` should be used instead

    use_vt : False
        Use VT terminal emulation (see output while installing)

        .. versionadded:: 2015.5.0

    saltenv : 'base'
        Specify a different environment. The default environment is ``base``.

        .. versionadded:: 2014.1.0

    .. note::
        The ``runas`` argument is deprecated as of 2014.1.0. ``user`` should be
        used instead.

    CLI Example:

    .. code-block:: console

        salt '*' virtualenv.create /path/to/new/virtualenv

     Example of using --always-copy environment variable (in case your fs doesn't support symlinks).
     This will copy files into the virtualenv instead of symlinking them.

     .. code-block:: yaml

         - env:
           - VIRTUALENV_ALWAYS_COPY: 1
    """
    if venv_bin is None:
        venv_bin = __opts__.get("venv_bin") or __pillar__.get("venv_bin")

    cmd = [venv_bin]

    if "pyvenv" not in venv_bin:
        # ----- Stop the user if pyvenv only options are used --------------->
        # If any of the following values are not None, it means that the user
        # is actually passing a True or False value. Stop Him!
        if upgrade is not None:
            raise CommandExecutionError(
                "The `upgrade`(`--upgrade`) option is not supported by '{}'".format(
                    venv_bin
                )
            )
        elif symlinks is not None:
            raise CommandExecutionError(
                "The `symlinks`(`--symlinks`) option is not supported by '{}'".format(
                    venv_bin
                )
            )
        # <---- Stop the user if pyvenv only options are used ----------------

        virtualenv_version_info = virtualenv_ver(venv_bin, user=user, **kwargs)

        if distribute:
            if virtualenv_version_info >= (1, 10):
                log.info(
                    "The virtualenv '--distribute' option has been "
                    "deprecated in virtualenv(>=1.10), as such, the "
                    "'distribute' option to `virtualenv.create()` has "
                    "also been deprecated and it's not necessary anymore."
                )
            else:
                cmd.append("--distribute")

        if python is not None and python.strip() != "":
            if not salt.utils.path.which(python):
                raise CommandExecutionError(
                    "Cannot find requested python ({}).".format(python)
                )
            cmd.append("--python={}".format(python))
        if extra_search_dir is not None:
            if isinstance(extra_search_dir, str) and extra_search_dir.strip() != "":
                extra_search_dir = [e.strip() for e in extra_search_dir.split(",")]
            for entry in extra_search_dir:
                cmd.append("--extra-search-dir={}".format(entry))
        if never_download is True:
            if (1, 10) <= virtualenv_version_info < (14, 0, 0):
                log.info(
                    "--never-download was deprecated in 1.10.0, but reimplemented in"
                    " 14.0.0. If this feature is needed, please install a supported"
                    " virtualenv version."
                )
            else:
                cmd.append("--never-download")
        if prompt is not None and prompt.strip() != "":
            cmd.append("--prompt='{}'".format(prompt))
    else:
        # venv module from the Python >= 3.3 standard library

        # ----- Stop the user if virtualenv only options are being used ----->
        # If any of the following values are not None, it means that the user
        # is actually passing a True or False value. Stop Him!
        if python is not None and python.strip() != "":
            raise CommandExecutionError(
                "The `python`(`--python`) option is not supported by '{}'".format(
                    venv_bin
                )
            )
        elif extra_search_dir is not None and extra_search_dir.strip() != "":
            raise CommandExecutionError(
                "The `extra_search_dir`(`--extra-search-dir`) option is not "
                "supported by '{}'".format(venv_bin)
            )
        elif never_download is not None:
            raise CommandExecutionError(
                "The `never_download`(`--never-download`) option is not "
                "supported by '{}'".format(venv_bin)
            )
        elif prompt is not None and prompt.strip() != "":
            raise CommandExecutionError(
                "The `prompt`(`--prompt`) option is not supported by '{}'".format(
                    venv_bin
                )
            )
        # <---- Stop the user if virtualenv only options are being used ------

        if upgrade is True:
            cmd.append("--upgrade")
        if symlinks is True:
            cmd.append("--symlinks")

    # Common options to virtualenv and pyvenv
    if clear is True:
        cmd.append("--clear")
    if system_site_packages is True:
        cmd.append("--system-site-packages")

    # Finally the virtualenv path
    cmd.append(path)

    # Let's create the virtualenv
    ret = __salt__["cmd.run_all"](cmd, runas=user, python_shell=False, **kwargs)
    if ret["retcode"] != 0:
        # Something went wrong. Let's bail out now!
        return ret

    # Check if distribute and pip are already installed
    if salt.utils.platform.is_windows():
        venv_python = os.path.join(path, "Scripts", "python.exe")
        venv_pip = os.path.join(path, "Scripts", "pip.exe")
        venv_setuptools = os.path.join(path, "Scripts", "easy_install.exe")
    else:
        venv_python = os.path.join(path, "bin", "python")
        venv_pip = os.path.join(path, "bin", "pip")
        venv_setuptools = os.path.join(path, "bin", "easy_install")

    # Install setuptools
    if (pip or distribute) and not os.path.exists(venv_setuptools):
        _install_script(
            "https://bitbucket.org/pypa/setuptools/raw/default/ez_setup.py",
            path,
            venv_python,
            user,
            saltenv=saltenv,
            use_vt=use_vt,
        )

        # clear up the distribute archive which gets downloaded
        for fpath in glob.glob(os.path.join(path, "distribute-*.tar.gz*")):
            os.unlink(fpath)

    if ret["retcode"] != 0:
        # Something went wrong. Let's bail out now!
        return ret

    # Install pip
    if pip and not os.path.exists(venv_pip):
        _ret = _install_script(
            "https://bootstrap.pypa.io/get-pip.py",
            path,
            venv_python,
            user,
            saltenv=saltenv,
            use_vt=use_vt,
        )
        # Let's update the return dictionary with the details from the pip
        # installation
        ret.update(
            retcode=_ret["retcode"],
            stdout="{}\n{}".format(ret["stdout"], _ret["stdout"]).strip(),
            stderr="{}\n{}".format(ret["stderr"], _ret["stderr"]).strip(),
        )

    return ret


def get_site_packages(venv):
    """
    Return the path to the site-packages directory of a virtualenv

    venv
        Path to the virtualenv.

    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.get_site_packages /path/to/my/venv
    """
    bin_path = _verify_virtualenv(venv)

    ret = __salt__["cmd.exec_code_all"](
        bin_path,
        "from distutils import sysconfig; print(sysconfig.get_python_lib())",
    )

    if ret["retcode"] != 0:
        raise CommandExecutionError("{stdout}\n{stderr}".format(**ret))

    return ret["stdout"]


def get_distribution_path(venv, distribution):
    """
    Return the path to a distribution installed inside a virtualenv

    .. versionadded:: 2016.3.0

    venv
        Path to the virtualenv.
    distribution
        Name of the distribution. Note, all non-alphanumeric characters
        will be converted to dashes.

    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.get_distribution_path /path/to/my/venv my_distribution
    """
    _verify_safe_py_code(distribution)
    bin_path = _verify_virtualenv(venv)

    ret = __salt__["cmd.exec_code_all"](
        bin_path,
        "import pkg_resources; "
        "print(pkg_resources.get_distribution('{}').location)".format(distribution),
    )

    if ret["retcode"] != 0:
        raise CommandExecutionError("{stdout}\n{stderr}".format(**ret))

    return ret["stdout"]


def get_resource_path(venv, package=None, resource=None):
    """
    Return the path to a package resource installed inside a virtualenv

    .. versionadded:: 2015.5.0

    venv
        Path to the virtualenv

    package
        Name of the package in which the resource resides

        .. versionadded:: 2016.3.0

    resource
        Name of the resource of which the path is to be returned

        .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.get_resource_path /path/to/my/venv my_package my/resource.xml
    """
    _verify_safe_py_code(package, resource)
    bin_path = _verify_virtualenv(venv)

    ret = __salt__["cmd.exec_code_all"](
        bin_path,
        "import pkg_resources; "
        "print(pkg_resources.resource_filename('{}', '{}'))".format(package, resource),
    )

    if ret["retcode"] != 0:
        raise CommandExecutionError("{stdout}\n{stderr}".format(**ret))

    return ret["stdout"]


def get_resource_content(venv, package=None, resource=None):
    """
    Return the content of a package resource installed inside a virtualenv

    .. versionadded:: 2015.5.0

    venv
        Path to the virtualenv

    package
        Name of the package in which the resource resides

        .. versionadded:: 2016.3.0

    resource
        Name of the resource of which the content is to be returned

        .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.get_resource_content /path/to/my/venv my_package my/resource.xml
    """
    _verify_safe_py_code(package, resource)
    bin_path = _verify_virtualenv(venv)

    ret = __salt__["cmd.exec_code_all"](
        bin_path,
        "import pkg_resources; print(pkg_resources.resource_string('{}', '{}'))".format(
            package, resource
        ),
    )

    if ret["retcode"] != 0:
        raise CommandExecutionError("{stdout}\n{stderr}".format(**ret))

    return ret["stdout"]


def _install_script(source, cwd, python, user, saltenv="base", use_vt=False):
    if not salt.utils.platform.is_windows():
        tmppath = salt.utils.files.mkstemp(dir=cwd)
    else:
        tmppath = __salt__["cp.cache_file"](source, saltenv)

    if not salt.utils.platform.is_windows():
        fn_ = __salt__["cp.cache_file"](source, saltenv)
        shutil.copyfile(fn_, tmppath)
        os.chmod(tmppath, 0o500)
        os.chown(tmppath, __salt__["file.user_to_uid"](user), -1)
    try:
        return __salt__["cmd.run_all"](
            [python, tmppath],
            runas=user,
            cwd=cwd,
            env={"VIRTUAL_ENV": cwd},
            use_vt=use_vt,
            python_shell=False,
        )
    finally:
        os.remove(tmppath)


def _verify_safe_py_code(*args):
    for arg in args:
        if not salt.utils.verify.safe_py_code(arg):
            raise SaltInvocationError("Unsafe python code detected in '{}'".format(arg))


def _verify_virtualenv(venv_path):
    bin_path = os.path.join(venv_path, "bin/python")
    if not os.path.exists(bin_path):
        raise CommandExecutionError(
            "Path '{}' does not appear to be a virtualenv: bin/python not found.".format(
                venv_path
            )
        )
    return bin_path
