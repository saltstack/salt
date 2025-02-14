"""
Management of Docker Containers

.. versionadded:: 2015.8.0
.. versionchanged:: 2017.7.0
    This module has replaced the legacy docker execution module.

:depends: docker_ Python module

.. _`create_container()`: http://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_container
.. _`create_host_config()`: http://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_host_config
.. _`connect_container_to_network()`: http://docker-py.readthedocs.io/en/stable/api.html#docker.api.network.NetworkApiMixin.connect_container_to_network
.. _`create_network()`: http://docker-py.readthedocs.io/en/stable/api.html#docker.api.network.NetworkApiMixin.create_network
.. _`logs()`: http://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.logs
.. _`IPAM pool`: http://docker-py.readthedocs.io/en/stable/api.html#docker.types.IPAMPool
.. _docker: https://pypi.python.org/pypi/docker
.. _docker-py: https://pypi.python.org/pypi/docker-py
.. _lxc-attach: https://linuxcontainers.org/lxc/manpages/man1/lxc-attach.1.html
.. _nsenter: http://man7.org/linux/man-pages/man1/nsenter.1.html
.. _docker-exec: http://docs.docker.com/reference/commandline/cli/#exec
.. _`docker-py Low-level API`: http://docker-py.readthedocs.io/en/stable/api.html
.. _timelib: https://pypi.python.org/pypi/timelib
.. _`trusted builds`: https://blog.docker.com/2013/11/introducing-trusted-builds/
.. _`Docker Engine API`: https://docs.docker.com/engine/api/v1.33/#operation/ContainerCreate

.. note::
    Older releases of the Python bindings for Docker were called docker-py_ in
    PyPI. All releases of docker_, and releases of docker-py_ >= 1.6.0 are
    supported. These python bindings can easily be installed using
    :py:func:`pip.install <salt.modules.pip.install>`:

    .. code-block:: bash

        salt myminion pip.install docker

    To upgrade from docker-py_ to docker_, you must first uninstall docker-py_,
    and then install docker_:

    .. code-block:: bash

        salt myminion pip.uninstall docker-py
        salt myminion pip.install docker

.. _docker-authentication:

Authentication
--------------

If you have previously performed a ``docker login`` from the minion, then the
credentials saved in ``~/.docker/config.json`` will be used for any actions
which require authentication. If not, then credentials can be configured in
any of the following locations:

- Minion config file
- Grains
- Pillar data
- Master config file (requires :conf_minion:`pillar_opts` to be set to ``True``
  in Minion config file in order to work)

.. important::
    Versions prior to 3000 require that Docker credentials are configured in
    Pillar data. Be advised that Pillar data is still recommended though,
    because this keeps the configuration from being stored on the Minion.

    Also, keep in mind that if one gets your ``~/.docker/config.json``, the
    password can be decoded from its contents.

The configuration schema is as follows:

.. code-block:: yaml

    docker-registries:
      <registry_url>:
        username: <username>
        password: <password>

For example:

.. code-block:: yaml

    docker-registries:
      hub:
        username: foo
        password: s3cr3t

.. note::
    As of the 2016.3.7, 2016.11.4, and 2017.7.0 releases of Salt, credentials
    for the Docker Hub can be configured simply by specifying ``hub`` in place
    of the registry URL. In earlier releases, it is necessary to specify the
    actual registry URL for the Docker Hub (i.e.
    ``https://index.docker.io/v1/``).

More than one registry can be configured. Salt will look for Docker credentials
in the ``docker-registries`` Pillar key, as well as any key ending in
``-docker-registries``. For example:

.. code-block:: yaml

    docker-registries:
      'https://mydomain.tld/registry:5000':
        username: foo
        password: s3cr3t

    foo-docker-registries:
      https://index.foo.io/v1/:
        username: foo
        password: s3cr3t

    bar-docker-registries:
      https://index.bar.io/v1/:
        username: foo
        password: s3cr3t

To login to the configured registries, use the :py:func:`docker.login
<salt.modules.dockermod.login>` function. This only needs to be done once for a
given registry, and it will store/update the credentials in
``~/.docker/config.json``.

.. note::
    For Salt releases before 2016.3.7 and 2016.11.4, :py:func:`docker.login
    <salt.modules.dockermod.login>` is not available. Instead, Salt will try to
    authenticate using each of your configured registries for each push/pull,
    behavior which is not correct and has been resolved in newer releases.


Configuration Options
---------------------

The following configuration options can be set to fine-tune how Salt uses
Docker:

- ``docker.url``: URL to the docker service (default: local socket).
- ``docker.version``: API version to use (should not need to be set manually in
  the vast majority of cases)
- ``docker.exec_driver``: Execution driver to use, one of ``nsenter``,
  ``lxc-attach``, or ``docker-exec``. See the :ref:`Executing Commands Within a
  Running Container <docker-execution-driver>` section for more details on how
  this config parameter is used.

These configuration options are retrieved using :py:mod:`config.get
<salt.modules.config.get>` (click the link for further information).

.. _docker-execution-driver:

Executing Commands Within a Running Container
---------------------------------------------

.. note::
    With the release of Docker 1.13.1, the Execution Driver has been removed.
    Starting in versions 2016.3.6, 2016.11.4, and 2017.7.0, Salt defaults to
    using ``docker exec`` to run commands in containers, however for older Salt
    releases it will be necessary to set the ``docker.exec_driver`` config
    option to either ``docker-exec`` or ``nsenter`` for Docker versions 1.13.1
    and newer.

Multiple methods exist for executing commands within Docker containers:

- lxc-attach_: Default for older versions of docker
- nsenter_: Enters container namespace to run command
- docker-exec_: Native support for executing commands in Docker containers
  (added in Docker 1.3)

Adding a configuration option (see :py:func:`config.get
<salt.modules.config.get>`) called ``docker.exec_driver`` will tell Salt which
execution driver to use:

.. code-block:: yaml

    docker.exec_driver: docker-exec

If this configuration option is not found, Salt will use the appropriate
interface (either nsenter_ or lxc-attach_) based on the ``Execution Driver``
value returned from ``docker info``. docker-exec_ will not be used by default,
as it is presently (as of version 1.6.2) only able to execute commands as the
effective user of the container. Thus, if a ``USER`` directive was used to run
as a non-privileged user, docker-exec_ would be unable to perform the action as
root. Salt can still use docker-exec_ as an execution driver, but must be
explicitly configured (as in the example above) to do so at this time.

If possible, try to manually specify the execution driver, as it will save Salt
a little work.

This execution module provides functions that shadow those from the :mod:`cmd
<salt.modules.cmdmod>` module. They are as follows:

- :py:func:`docker.retcode <salt.modules.dockermod.retcode>`
- :py:func:`docker.run <salt.modules.dockermod.run>`
- :py:func:`docker.run_all <salt.modules.dockermod.run_all>`
- :py:func:`docker.run_stderr <salt.modules.dockermod.run_stderr>`
- :py:func:`docker.run_stdout <salt.modules.dockermod.run_stdout>`
- :py:func:`docker.script <salt.modules.dockermod.script>`
- :py:func:`docker.script_retcode <salt.modules.dockermod.script_retcode>`


Detailed Function Documentation
-------------------------------
"""

import bz2
import copy
import fnmatch
import functools
import gzip
import json
import logging
import os
import re
import shlex
import shutil
import string
import subprocess
import time
import uuid

import salt.client.ssh.state
import salt.exceptions
import salt.fileclient
import salt.pillar
import salt.utils.dockermod.translate.container
import salt.utils.dockermod.translate.network
import salt.utils.functools
import salt.utils.json
import salt.utils.path
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.loader.dunder import __file_client__
from salt.state import HighState

__docformat__ = "restructuredtext en"


# pylint: disable=import-error
try:
    import docker

    HAS_DOCKER_PY = True
except ImportError:
    HAS_DOCKER_PY = False

try:
    import lzma

    HAS_LZMA = True
except ImportError:
    HAS_LZMA = False

try:
    import timelib

    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False
# pylint: enable=import-error

HAS_NSENTER = bool(salt.utils.path.which("nsenter"))

log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {
    "import_": "import",
    "ps_": "ps",
    "rm_": "rm",
    "signal_": "signal",
    "start_": "start",
    "tag_": "tag",
    "apply_": "apply",
}

# Minimum supported versions
MIN_DOCKER = (1, 9, 0)
MIN_DOCKER_PY = (1, 6, 0)

VERSION_RE = r"([\d.]+)"

NOTSET = object()

# Define the module's virtual name and alias
__virtualname__ = "docker"
__virtual_aliases__ = ("dockerng", "moby")

__proxyenabled__ = ["docker"]
__outputter__ = {
    "sls": "highstate",
    "apply_": "highstate",
    "highstate": "highstate",
}


def __virtual__():
    """
    Only load if docker libs are present
    """
    if HAS_DOCKER_PY:
        try:
            docker_py_versioninfo = _get_docker_py_versioninfo()
        except Exception:  # pylint: disable=broad-except
            # May fail if we try to connect to a docker daemon but can't
            return (False, "Docker module found, but no version could be extracted")
        # Don't let a failure to interpret the version keep this module from
        # loading. Log a warning (log happens in _get_docker_py_versioninfo()).
        if docker_py_versioninfo is None:
            return (False, "Docker module found, but no version could be extracted")
        if docker_py_versioninfo >= MIN_DOCKER_PY:
            try:
                docker_versioninfo = version().get("VersionInfo")
            except Exception:  # pylint: disable=broad-except
                docker_versioninfo = None

            if docker_versioninfo is None or docker_versioninfo >= MIN_DOCKER:
                return __virtualname__
            else:
                return (
                    False,
                    "Insufficient Docker version (required: {}, installed: {})".format(
                        ".".join(map(str, MIN_DOCKER)),
                        ".".join(map(str, docker_versioninfo)),
                    ),
                )
        return (
            False,
            "Insufficient docker-py version (required: {}, installed: {})".format(
                ".".join(map(str, MIN_DOCKER_PY)),
                ".".join(map(str, docker_py_versioninfo)),
            ),
        )
    return (False, "Could not import docker module, is docker-py installed?")


def _file_client():
    """
    Return a file client

    If the __file_client__ context is set return it, otherwize create a new
    file client using __opts__.
    """
    if __file_client__:
        return __file_client__.value()
    return salt.fileclient.get_file_client(__opts__)


class DockerJSONDecoder(json.JSONDecoder):
    def decode(self, s, _w=None):
        objs = []
        for line in s.splitlines():
            if not line:
                continue
            obj, _ = self.raw_decode(line)
            objs.append(obj)
        return objs


def _get_docker_py_versioninfo():
    """
    Returns the version_info tuple from docker-py
    """
    try:
        return docker.version_info
    except AttributeError:
        # docker 6.0.0+ exposes version from __version__ attribute
        try:
            docker_version = docker.__version__.split(".")
            return tuple(int(n) for n in docker_version)
        except AttributeError:
            pass


def _get_client(timeout=NOTSET, **kwargs):
    client_kwargs = {}
    if timeout is not NOTSET:
        client_kwargs["timeout"] = timeout
    for key, val in (("base_url", "docker.url"), ("version", "docker.version")):
        param = __salt__["config.option"](val, NOTSET)
        if param is not NOTSET:
            client_kwargs[key] = param

    if "base_url" not in client_kwargs and "DOCKER_HOST" in os.environ:
        # Check if the DOCKER_HOST environment variable has been set
        client_kwargs["base_url"] = os.environ.get("DOCKER_HOST")

    if "version" not in client_kwargs:
        # Let docker-py auto detect docker version in case
        # it's not defined by user.
        client_kwargs["version"] = "auto"

    docker_machine = __salt__["config.option"]("docker.machine", NOTSET)

    if docker_machine is not NOTSET:
        docker_machine_json = __salt__["cmd.run"](
            ["docker-machine", "inspect", docker_machine], python_shell=False
        )
        try:
            docker_machine_json = salt.utils.json.loads(docker_machine_json)
            docker_machine_tls = docker_machine_json["HostOptions"]["AuthOptions"]
            docker_machine_ip = docker_machine_json["Driver"]["IPAddress"]
            client_kwargs["base_url"] = "https://" + docker_machine_ip + ":2376"
            client_kwargs["tls"] = docker.tls.TLSConfig(
                client_cert=(
                    docker_machine_tls["ClientCertPath"],
                    docker_machine_tls["ClientKeyPath"],
                ),
                ca_cert=docker_machine_tls["CaCertPath"],
                verify=True,
            )
        except Exception as exc:  # pylint: disable=broad-except
            raise CommandExecutionError(
                f"Docker machine {docker_machine} failed: {exc}"
            )
    try:
        # docker-py 2.0 renamed this client attribute
        ret = docker.APIClient(**client_kwargs)
    except AttributeError:
        # pylint: disable=not-callable
        ret = docker.Client(**client_kwargs)
        # pylint: enable=not-callable

    log.debug("docker-py API version: %s", getattr(ret, "api_version", None))
    return ret


def _get_state(inspect_results):
    """
    Helper for deriving the current state of the container from the inspect
    results.
    """
    if inspect_results.get("State", {}).get("Paused", False):
        return "paused"
    elif inspect_results.get("State", {}).get("Running", False):
        return "running"
    else:
        return "stopped"


# Decorators
def _docker_client(wrapped):
    """
    Decorator to run a function that requires the use of a docker.Client()
    instance.
    """

    @functools.wraps(wrapped)
    def wrapper(*args, **kwargs):
        """
        Ensure that the client is present
        """
        kwargs = __utils__["args.clean_kwargs"](**kwargs)
        timeout = kwargs.pop("client_timeout", NOTSET)
        if "docker.client" not in __context__ or not hasattr(
            __context__["docker.client"], "timeout"
        ):
            __context__["docker.client"] = _get_client(timeout=timeout, **kwargs)
        orig_timeout = None
        if (
            timeout is not NOTSET
            and hasattr(__context__["docker.client"], "timeout")
            and __context__["docker.client"].timeout != timeout
        ):
            # Temporarily override timeout
            orig_timeout = __context__["docker.client"].timeout
            __context__["docker.client"].timeout = timeout
        ret = wrapped(*args, **kwargs)
        if orig_timeout is not None:
            __context__["docker.client"].timeout = orig_timeout
        return ret

    return wrapper


def _refresh_mine_cache(wrapped):
    """
    Decorator to trigger a refresh of salt mine data.
    """

    @functools.wraps(wrapped)
    def wrapper(*args, **kwargs):
        """
        refresh salt mine on exit.
        """
        returned = wrapped(*args, **__utils__["args.clean_kwargs"](**kwargs))
        if _check_update_mine():
            __salt__["mine.send"]("docker.ps", verbose=True, all=True, host=True)
        return returned

    return wrapper


def _check_update_mine():
    try:
        ret = __context__["docker.update_mine"]
    except KeyError:
        ret = __context__["docker.update_mine"] = __salt__["config.option"](
            "docker.update_mine", default=True
        )
    return ret


# Helper functions
def _change_state(name, action, expected, *args, **kwargs):
    """
    Change the state of a container
    """
    pre = state(name)
    if action != "restart" and pre == expected:
        return {
            "result": False,
            "state": {"old": expected, "new": expected},
            "comment": f"Container '{name}' already {expected}",
        }
    _client_wrapper(action, name, *args, **kwargs)
    _clear_context()
    try:
        post = state(name)
    except CommandExecutionError:
        # Container doesn't exist anymore
        post = None
    ret = {"result": post == expected, "state": {"old": pre, "new": post}}
    return ret


def _clear_context():
    """
    Clear the state/exists values stored in context
    """
    # Can't use 'for key in __context__' because an exception will be raised if
    # the size of the dict is modified during iteration.
    keep_context = (
        "docker.client",
        "docker.exec_driver",
        "docker._pull_status",
        "docker.docker_version",
        "docker.docker_py_version",
    )
    for key in list(__context__):
        try:
            if key.startswith("docker.") and key not in keep_context:
                __context__.pop(key)
        except AttributeError:
            pass


def _get_sha256(name, path):
    """
    Get the sha256 checksum of a file from a container
    """
    output = run_stdout(name, f"sha256sum {shlex.quote(path)}", ignore_retcode=True)
    try:
        return output.split()[0]
    except IndexError:
        # Destination file does not exist or could not be accessed
        return None


def _get_exec_driver():
    """
    Get the method to be used in shell commands
    """
    contextkey = "docker.exec_driver"
    if contextkey not in __context__:
        from_config = __salt__["config.option"](contextkey, None)
        # This if block can be removed once we make docker-exec a default
        # option, as it is part of the logic in the commented block above.
        if from_config is not None:
            __context__[contextkey] = from_config
            return from_config

        # The execution driver was removed in Docker 1.13.1, docker-exec is now
        # the default.
        driver = info().get("ExecutionDriver", "docker-exec")
        if driver == "docker-exec":
            __context__[contextkey] = driver
        elif driver.startswith("lxc-"):
            __context__[contextkey] = "lxc-attach"
        elif driver.startswith("native-") and HAS_NSENTER:
            __context__[contextkey] = "nsenter"
        elif not driver.strip() and HAS_NSENTER:
            log.warning(
                "ExecutionDriver from 'docker info' is blank, falling "
                "back to using 'nsenter'. To squelch this warning, set "
                "docker.exec_driver. See the Salt documentation for the "
                "docker module for more information."
            )
            __context__[contextkey] = "nsenter"
        else:
            raise NotImplementedError(
                "Unknown docker ExecutionDriver '{}', or didn't find "
                "command to attach to the container".format(driver)
            )
    return __context__[contextkey]


def _get_top_level_images(imagedata, subset=None):
    """
    Returns a list of the top-level images (those which are not parents). If
    ``subset`` (an iterable) is passed, the top-level images in the subset will
    be returned, otherwise all top-level images will be returned.
    """
    try:
        parents = [imagedata[x]["ParentId"] for x in imagedata]
        filter_ = subset if subset is not None else imagedata
        return [x for x in filter_ if x not in parents]
    except (KeyError, TypeError):
        raise CommandExecutionError(
            "Invalid image data passed to _get_top_level_images(). Please "
            "report this issue. Full image data: {}".format(imagedata)
        )


def _prep_pull():
    """
    Populate __context__ with the current (pre-pull) image IDs (see the
    docstring for _pull_status for more information).
    """
    __context__["docker._pull_status"] = [x[:12] for x in images(all=True)]


def _scrub_links(links, name):
    """
    Remove container name from HostConfig:Links values to enable comparing
    container configurations correctly.
    """
    if isinstance(links, list):
        ret = []
        for l in links:
            ret.append(l.replace(f"/{name}/", "/", 1))
    else:
        ret = links

    return ret


def _ulimit_sort(ulimit_val):
    if isinstance(ulimit_val, list):
        return sorted(
            ulimit_val,
            key=lambda x: (x.get("Name"), x.get("Hard", 0), x.get("Soft", 0)),
        )
    return ulimit_val


def _size_fmt(num):
    """
    Format bytes as human-readable file sizes
    """
    try:
        num = int(num)
        if num < 1024:
            return f"{num} bytes"
        num /= 1024.0
        for unit in ("KiB", "MiB", "GiB", "TiB", "PiB"):
            if num < 1024.0:
                return f"{num:3.1f} {unit}"
            num /= 1024.0
    except Exception:  # pylint: disable=broad-except
        log.error("Unable to format file size for '%s'", num)
        return "unknown"


@_docker_client
def _client_wrapper(attr, *args, **kwargs):
    """
    Common functionality for running low-level API calls
    """
    catch_api_errors = kwargs.pop("catch_api_errors", True)
    func = getattr(__context__["docker.client"], attr, None)
    if func is None or not hasattr(func, "__call__"):
        raise SaltInvocationError(f"Invalid client action '{attr}'")
    if attr in ("push", "pull"):
        try:
            # Refresh auth config from config.json
            __context__["docker.client"].reload_config()
        except AttributeError:
            pass
    err = ""
    try:
        log.debug(
            'Attempting to run docker-py\'s "%s" function with args=%s and kwargs=%s',
            attr,
            args,
            kwargs,
        )
        ret = func(*args, **kwargs)
    except docker.errors.APIError as exc:
        if catch_api_errors:
            # Generic handling of Docker API errors
            raise CommandExecutionError(
                f"Error {exc.response.status_code}: {exc.explanation}"
            )
        else:
            # Allow API errors to be caught further up the stack
            raise
    except docker.errors.DockerException as exc:
        # More general docker exception (catches InvalidVersion, etc.)
        raise CommandExecutionError(str(exc))
    except Exception as exc:  # pylint: disable=broad-except
        err = str(exc)
    else:
        return ret

    # If we're here, it's because an exception was caught earlier, and the
    # API command failed.
    msg = f"Unable to perform {attr}"
    if err:
        msg += f": {err}"
    raise CommandExecutionError(msg)


def _build_status(data, item):
    """
    Process a status update from a docker build, updating the data structure
    """
    stream = item["stream"]
    if "Running in" in stream:
        data.setdefault("Intermediate_Containers", []).append(
            stream.rstrip().split()[-1]
        )
    if "Successfully built" in stream:
        data["Id"] = stream.rstrip().split()[-1]


def _import_status(data, item, repo_name, repo_tag):
    """
    Process a status update from docker import, updating the data structure
    """
    status = item["status"]
    try:
        if "Downloading from" in status:
            return
        elif all(x in string.hexdigits for x in status):
            # Status is an image ID
            data["Image"] = f"{repo_name}:{repo_tag}"
            data["Id"] = status
    except (AttributeError, TypeError):
        pass


def _pull_status(data, item):
    """
    Process a status update from a docker pull, updating the data structure.

    For containers created with older versions of Docker, there is no
    distinction in the status updates between layers that were already present
    (and thus not necessary to download), and those which were actually
    downloaded. Because of this, any function that needs to invoke this
    function needs to pre-fetch the image IDs by running _prep_pull() in any
    function that calls _pull_status(). It is important to grab this
    information before anything is pulled so we aren't looking at the state of
    the images post-pull.

    We can't rely on the way that __context__ is utilized by the images()
    function, because by design we clear the relevant context variables once
    we've made changes to allow the next call to images() to pick up any
    changes that were made.
    """

    def _already_exists(id_):
        """
        Layer already exists
        """
        already_pulled = data.setdefault("Layers", {}).setdefault("Already_Pulled", [])
        if id_ not in already_pulled:
            already_pulled.append(id_)

    def _new_layer(id_):
        """
        Pulled a new layer
        """
        pulled = data.setdefault("Layers", {}).setdefault("Pulled", [])
        if id_ not in pulled:
            pulled.append(id_)

    if "docker._pull_status" not in __context__:
        log.warning(
            "_pull_status context variable was not populated, information on "
            "downloaded layers may be inaccurate. Please report this to the "
            "SaltStack development team, and if possible include the image "
            "(and tag) that was being pulled."
        )
        __context__["docker._pull_status"] = NOTSET
    status = item["status"]
    if status == "Already exists":
        _already_exists(item["id"])
    elif status in "Pull complete":
        _new_layer(item["id"])
    elif status.startswith("Status: "):
        data["Status"] = status[8:]
    elif status == "Download complete":
        if __context__["docker._pull_status"] is not NOTSET:
            id_ = item["id"]
            if id_ in __context__["docker._pull_status"]:
                _already_exists(id_)
            else:
                _new_layer(id_)


def _push_status(data, item):
    """
    Process a status update from a docker push, updating the data structure
    """
    status = item["status"].lower()
    if "id" in item:
        if "already pushed" in status or "already exists" in status:
            # Layer already exists
            already_pushed = data.setdefault("Layers", {}).setdefault(
                "Already_Pushed", []
            )
            already_pushed.append(item["id"])
        elif "successfully pushed" in status or status == "pushed":
            # Pushed a new layer
            pushed = data.setdefault("Layers", {}).setdefault("Pushed", [])
            pushed.append(item["id"])


def _error_detail(data, item):
    """
    Process an API error, updating the data structure
    """
    err = item["errorDetail"]
    if "code" in err:
        try:
            msg = ": ".join(
                (item["errorDetail"]["code"], item["errorDetail"]["message"])
            )
        except TypeError:
            msg = "{}: {}".format(
                item["errorDetail"]["code"],
                item["errorDetail"]["message"],
            )
    else:
        msg = item["errorDetail"]["message"]
    data.append(msg)


# Functions to handle docker-py client args
def get_client_args(limit=None):
    """
    .. versionadded:: 2016.3.6,2016.11.4,2017.7.0
    .. versionchanged:: 2017.7.0
        Replaced the container config args with the ones from the API's
        ``create_container`` function.
    .. versionchanged:: 2018.3.0
        Added ability to limit the input to specific client functions

    Many functions in Salt have been written to support the full list of
    arguments for a given function in the `docker-py Low-level API`_. However,
    depending on the version of docker-py installed on the minion, the
    available arguments may differ. This function will get the arguments for
    various functions in the installed version of docker-py, to be used as a
    reference.

    limit
        An optional list of categories for which to limit the return. This is
        useful if only a specific set of arguments is desired, and also keeps
        other function's argspecs from needlessly being examined.

    **AVAILABLE LIMITS**

    - ``create_container`` - arguments accepted by `create_container()`_ (used
      by :py:func:`docker.create <salt.modules.dockermod.create>`)
    - ``host_config`` - arguments accepted by `create_host_config()`_ (used to
      build the host config for :py:func:`docker.create
      <salt.modules.dockermod.create>`)
    - ``connect_container_to_network`` - arguments used by
      `connect_container_to_network()`_ to construct an endpoint config when
      connecting to a network (used by
      :py:func:`docker.connect_container_to_network
      <salt.modules.dockermod.connect_container_to_network>`)
    - ``create_network`` - arguments accepted by `create_network()`_ (used by
      :py:func:`docker.create_network <salt.modules.dockermod.create_network>`)
    - ``ipam_config`` - arguments used to create an `IPAM pool`_ (used by
      :py:func:`docker.create_network <salt.modules.dockermod.create_network>`
      in the process of constructing an IPAM config dictionary)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.get_client_args
        salt myminion docker.get_client_args logs
        salt myminion docker.get_client_args create_container,connect_container_to_network
    """
    return __utils__["docker.get_client_args"](limit=limit)


def _get_create_kwargs(
    skip_translate=None,
    ignore_collisions=False,
    validate_ip_addrs=True,
    client_args=None,
    **kwargs,
):
    """
    Take input kwargs and return a kwargs dict to pass to docker-py's
    create_container() function.
    """

    networks = kwargs.pop("networks", {})
    if kwargs.get("network_mode", "") in networks:
        networks = {kwargs["network_mode"]: networks[kwargs["network_mode"]]}
    else:
        networks = {}

    kwargs = __utils__["docker.translate_input"](
        salt.utils.dockermod.translate.container,
        skip_translate=skip_translate,
        ignore_collisions=ignore_collisions,
        validate_ip_addrs=validate_ip_addrs,
        **__utils__["args.clean_kwargs"](**kwargs),
    )

    if networks:
        kwargs["networking_config"] = _create_networking_config(networks)

    if client_args is None:
        try:
            client_args = get_client_args(["create_container", "host_config"])
        except CommandExecutionError as exc:
            log.error(
                "docker.create: Error getting client args: '%s'", exc, exc_info=True
            )
            raise CommandExecutionError(f"Failed to get client args: {exc}")

    full_host_config = {}
    host_kwargs = {}
    create_kwargs = {}
    # Using list() becausee we'll be altering kwargs during iteration
    for arg in list(kwargs):
        if arg in client_args["host_config"]:
            host_kwargs[arg] = kwargs.pop(arg)
            continue
        if arg in client_args["create_container"]:
            if arg == "host_config":
                full_host_config.update(kwargs.pop(arg))
            else:
                create_kwargs[arg] = kwargs.pop(arg)
            continue
    create_kwargs["host_config"] = _client_wrapper("create_host_config", **host_kwargs)
    # In the event that a full host_config was passed, overlay it on top of the
    # one we just created.
    create_kwargs["host_config"].update(full_host_config)
    # The "kwargs" dict at this point will only contain unused args
    return create_kwargs, kwargs


def compare_containers(first, second, ignore=None):
    """
    .. versionadded:: 2017.7.0
    .. versionchanged:: 2018.3.0
        Renamed from ``docker.compare_container`` to
        ``docker.compare_containers`` (old function name remains as an alias)

    Compare two containers' Config and and HostConfig and return any
    differences between the two.

    first
        Name or ID of first container

    second
        Name or ID of second container

    ignore
        A comma-separated list (or Python list) of keys to ignore when
        comparing. This is useful when comparing two otherwise identical
        containers which have different hostnames.

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.compare_containers foo bar
        salt myminion docker.compare_containers foo bar ignore=Hostname
    """
    ignore = __utils__["args.split_input"](ignore or [])
    result1 = inspect_container(first)
    result2 = inspect_container(second)
    ret = {}
    for conf_dict in ("Config", "HostConfig"):
        for item in result1[conf_dict]:
            if item in ignore:
                continue
            val1 = result1[conf_dict][item]
            val2 = result2[conf_dict].get(item)
            if item in ("OomKillDisable",) or (val1 is None or val2 is None):
                if bool(val1) != bool(val2):
                    ret.setdefault(conf_dict, {})[item] = {"old": val1, "new": val2}
            elif item == "Image":
                image1 = inspect_image(val1)["Id"]
                image2 = inspect_image(val2)["Id"]
                if image1 != image2:
                    ret.setdefault(conf_dict, {})[item] = {"old": image1, "new": image2}
            else:
                if item == "Links":
                    val1 = sorted(_scrub_links(val1, first))
                    val2 = sorted(_scrub_links(val2, second))
                if item == "Ulimits":
                    val1 = _ulimit_sort(val1)
                    val2 = _ulimit_sort(val2)
                if item == "Env":
                    val1 = sorted(val1)
                    val2 = sorted(val2)
                if val1 != val2:
                    ret.setdefault(conf_dict, {})[item] = {"old": val1, "new": val2}
        # Check for optionally-present items that were in the second container
        # and not the first.
        for item in result2[conf_dict]:
            if item in ignore or item in ret.get(conf_dict, {}):
                # We're either ignoring this or we already processed this
                # when iterating through result1. Either way, skip it.
                continue
            val1 = result1[conf_dict].get(item)
            val2 = result2[conf_dict][item]
            if item in ("OomKillDisable",) or (val1 is None or val2 is None):
                if bool(val1) != bool(val2):
                    ret.setdefault(conf_dict, {})[item] = {"old": val1, "new": val2}
            elif item == "Image":
                image1 = inspect_image(val1)["Id"]
                image2 = inspect_image(val2)["Id"]
                if image1 != image2:
                    ret.setdefault(conf_dict, {})[item] = {"old": image1, "new": image2}
            else:
                if item == "Links":
                    val1 = sorted(_scrub_links(val1, first))
                    val2 = sorted(_scrub_links(val2, second))
                if item == "Ulimits":
                    val1 = _ulimit_sort(val1)
                    val2 = _ulimit_sort(val2)
                if item == "Env":
                    val1 = sorted(val1)
                    val2 = sorted(val2)
                if val1 != val2:
                    ret.setdefault(conf_dict, {})[item] = {"old": val1, "new": val2}
    return ret


compare_container = salt.utils.functools.alias_function(
    compare_containers, "compare_container"
)


def compare_container_networks(first, second):
    """
    .. versionadded:: 2018.3.0

    Returns the differences between two containers' networks. When a network is
    only present one of the two containers, that network's diff will simply be
    represented with ``True`` for the side of the diff in which the network is
    present) and ``False`` for the side of the diff in which the network is
    absent.

    This function works by comparing the contents of both containers'
    ``Networks`` keys (under ``NetworkSettings``) in the return data from
    :py:func:`docker.inspect_container
    <salt.modules.dockermod.inspect_container>`. Because each network contains
    some items that either A) only set at runtime, B) naturally varying from
    container to container, or both, by default the following keys in each
    network are examined:

    - **Aliases**
    - **Links**
    - **IPAMConfig**

    The exception to this is if ``IPAMConfig`` is unset (i.e. null) in one
    container but not the other. This happens when no static IP configuration
    is set, and automatic IP configuration is in effect. So, in order to report
    on changes between automatic IP configuration in one container and static
    IP configuration in another container (as we need to do for the
    :py:func:`docker_container.running <salt.states.docker_container.running>`
    state), automatic IP configuration will also be checked in these cases.

    This function uses the :conf_minion:`docker.compare_container_networks`
    minion config option to determine which keys to examine. This provides
    flexibility in the event that features added in a future Docker release
    necessitate changes to how Salt compares networks. In these cases, rather
    than waiting for a new Salt release one can just set
    :conf_minion:`docker.compare_container_networks`.

    .. versionchanged:: 3000
        This config option can now also be set in pillar data and grains.
        Additionally, it can be set in the master config file, provided that
        :conf_minion:`pillar_opts` is enabled on the minion.

    .. note::
        The checks for automatic IP configuration described above only apply if
        ``IPAMConfig`` is among the keys set for static IP checks in
        :conf_minion:`docker.compare_container_networks`.

    first
        Name or ID of first container (old)

    second
        Name or ID of second container (new)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.compare_container_networks foo bar
    """

    def _get_nets(data):
        return data.get("NetworkSettings", {}).get("Networks", {})

    compare_keys = __salt__["config.option"]("docker.compare_container_networks")

    result1 = inspect_container(first) if not isinstance(first, dict) else first
    result2 = inspect_container(second) if not isinstance(second, dict) else second
    nets1 = _get_nets(result1)
    nets2 = _get_nets(result2)
    state1 = state(first)
    state2 = state(second)

    # When you attempt and fail to set a static IP (for instance, because the
    # IP is not in the network's subnet), Docker will raise an exception but
    # will (incorrectly) leave the record for that network in the inspect
    # results for the container. Work around this behavior (bug?) by checking
    # which containers are actually connected.
    all_nets = set(nets1)
    all_nets.update(nets2)
    for net_name in all_nets:
        try:
            connected_containers = inspect_network(net_name).get("Containers", {})
        except Exception as exc:  # pylint: disable=broad-except
            # Shouldn't happen unless a network was removed outside of Salt
            # between the time that a docker_container.running state started
            # and when this comparison took place.
            log.warning("Failed to inspect Docker network %s: %s", net_name, exc)
            continue
        else:
            if (
                state1 == "running"
                and net_name in nets1
                and result1["Id"] not in connected_containers
            ):
                del nets1[net_name]
            if (
                state2 == "running"
                and net_name in nets2
                and result2["Id"] not in connected_containers
            ):
                del nets2[net_name]

    ret = {}

    def _check_ipconfig(ret, net_name, **kwargs):
        # Make some variables to make the logic below easier to understand
        nets1_missing = "old" not in kwargs
        if nets1_missing:
            nets1_static = False
        else:
            nets1_static = bool(kwargs["old"])
        nets1_autoip = not nets1_static and not nets1_missing
        nets2_missing = "new" not in kwargs
        if nets2_missing:
            nets2_static = False
        else:
            nets2_static = bool(kwargs["new"])
        nets2_autoip = not nets2_static and not nets2_missing

        autoip_keys = compare_keys.get("automatic", [])

        if nets1_autoip and (nets2_static or nets2_missing):
            for autoip_key in autoip_keys:
                autoip_val = nets1[net_name].get(autoip_key)
                if autoip_val:
                    ret.setdefault(net_name, {})[autoip_key] = {
                        "old": autoip_val,
                        "new": None,
                    }
            if nets2_static:
                ret.setdefault(net_name, {})["IPAMConfig"] = {
                    "old": None,
                    "new": kwargs["new"],
                }
            if not any(x in ret.get(net_name, {}) for x in autoip_keys):
                ret.setdefault(net_name, {})["IPConfiguration"] = {
                    "old": "automatic",
                    "new": "static" if nets2_static else "not connected",
                }
        elif nets2_autoip and (nets1_static or nets1_missing):
            for autoip_key in autoip_keys:
                autoip_val = nets2[net_name].get(autoip_key)
                if autoip_val:
                    ret.setdefault(net_name, {})[autoip_key] = {
                        "old": None,
                        "new": autoip_val,
                    }
            if not any(x in ret.get(net_name, {}) for x in autoip_keys):
                ret.setdefault(net_name, {})["IPConfiguration"] = {
                    "old": "static" if nets1_static else "not connected",
                    "new": "automatic",
                }
            if nets1_static:
                ret.setdefault(net_name, {})["IPAMConfig"] = {
                    "old": kwargs["old"],
                    "new": None,
                }
        else:
            old_val = kwargs.get("old")
            new_val = kwargs.get("new")
            if old_val != new_val:
                # Static IP configuration present in both containers and there
                # are differences, so report them
                ret.setdefault(net_name, {})["IPAMConfig"] = {
                    "old": old_val,
                    "new": new_val,
                }

    for net_name in (x for x in nets1 if x not in nets2):
        # Network is not in the network_settings, but the container is attached
        # to the network
        for key in compare_keys.get("static", []):
            val = nets1[net_name].get(key)
            if key == "IPAMConfig":
                _check_ipconfig(ret, net_name, old=val)
            if val:
                if key == "Aliases":
                    try:
                        val.remove(result1["Config"]["Hostname"])
                    except (ValueError, AttributeError):
                        pass
                    else:
                        if not val:
                            # The only alias was the default one for the
                            # hostname
                            continue
                ret.setdefault(net_name, {})[key] = {"old": val, "new": None}

    for net_name in nets2:
        if net_name not in nets1:
            # Container is not attached to the network, but network is present
            # in the network_settings
            for key in compare_keys.get("static", []):
                val = nets2[net_name].get(key)
                if key == "IPAMConfig":
                    _check_ipconfig(ret, net_name, new=val)
                    continue
                elif val:
                    if key == "Aliases":
                        try:
                            val.remove(result2["Config"]["Hostname"])
                        except (ValueError, AttributeError):
                            pass
                        else:
                            if not val:
                                # The only alias was the default one for the
                                # hostname
                                continue
                    ret.setdefault(net_name, {})[key] = {"old": None, "new": val}
        else:
            for key in compare_keys.get("static", []):
                old_val = nets1[net_name][key]
                new_val = nets2[net_name][key]
                for item in (old_val, new_val):
                    # Normalize for list order
                    try:
                        item.sort()
                    except AttributeError:
                        pass
                if key == "Aliases":
                    # Normalize for hostname alias
                    try:
                        old_val.remove(result1["Config"]["Hostname"])
                    except (AttributeError, ValueError):
                        pass
                    try:
                        old_val.remove(result1["Id"][:12])
                    except (AttributeError, ValueError):
                        pass
                    if not old_val:
                        old_val = None
                    try:
                        new_val.remove(result2["Config"]["Hostname"])
                    except (AttributeError, ValueError):
                        pass
                    try:
                        new_val.remove(result2["Id"][:12])
                    except (AttributeError, ValueError):
                        pass
                    if not new_val:
                        new_val = None
                elif key == "IPAMConfig":
                    _check_ipconfig(ret, net_name, old=old_val, new=new_val)
                    # We don't need the final check since it's included in the
                    # _check_ipconfig helper
                    continue
                if bool(old_val) is bool(new_val) is False:
                    continue
                elif old_val != new_val:
                    ret.setdefault(net_name, {})[key] = {"old": old_val, "new": new_val}
    return ret


def compare_networks(first, second, ignore="Name,Id,Created,Containers"):
    """
    .. versionadded:: 2018.3.0

    Compare two networks and return any differences between the two

    first
        Name or ID of first container

    second
        Name or ID of second container

    ignore : Name,Id,Created,Containers
        A comma-separated list (or Python list) of keys to ignore when
        comparing.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.compare_network foo bar
    """
    ignore = __utils__["args.split_input"](ignore or [])
    net1 = inspect_network(first) if not isinstance(first, dict) else first
    net2 = inspect_network(second) if not isinstance(second, dict) else second
    ret = {}

    for item in net1:
        if item in ignore:
            continue
        else:
            # Don't re-examine this item when iterating through net2 below
            ignore.append(item)
        val1 = net1[item]
        val2 = net2.get(item)
        if bool(val1) is bool(val2) is False:
            continue
        elif item == "IPAM":
            for subkey in val1:
                subval1 = val1[subkey]
                subval2 = val2.get(subkey)
                if bool(subval1) is bool(subval2) is False:
                    continue
                elif subkey == "Config":

                    def kvsort(x):
                        return (list(x.keys()), list(x.values()))

                    config1 = sorted(val1["Config"], key=kvsort)
                    config2 = sorted(val2.get("Config", []), key=kvsort)
                    if config1 != config2:
                        ret.setdefault("IPAM", {})["Config"] = {
                            "old": config1,
                            "new": config2,
                        }
                elif subval1 != subval2:
                    ret.setdefault("IPAM", {})[subkey] = {
                        "old": subval1,
                        "new": subval2,
                    }
        elif item == "Options":
            for subkey in val1:
                subval1 = val1[subkey]
                subval2 = val2.get(subkey)
                if subkey == "com.docker.network.bridge.name":
                    continue
                elif subval1 != subval2:
                    ret.setdefault("Options", {})[subkey] = {
                        "old": subval1,
                        "new": subval2,
                    }
        elif val1 != val2:
            ret[item] = {"old": val1, "new": val2}

    # Check for optionally-present items that were in the second network
    # and not the first.
    for item in (x for x in net2 if x not in ignore):
        val1 = net1.get(item)
        val2 = net2[item]
        if bool(val1) is bool(val2) is False:
            continue
        elif val1 != val2:
            ret[item] = {"old": val1, "new": val2}

    return ret


def connected(name, verbose=False):
    """
    .. versionadded:: 2018.3.0

    Return a list of running containers attached to the specified network

    name
        Network name

    verbose : False
        If ``True``, return extended info about each container (IP
        configuration, etc.)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.connected net_name
    """
    containers = inspect_network(name).get("Containers", {})
    ret = {}
    for cid, cinfo in containers.items():
        # The Containers dict is keyed by container ID, but we want the results
        # to be keyed by container name, so we need to pop off the Name and
        # then add the Id key to the cinfo dict.
        try:
            name = cinfo.pop("Name")
        except (KeyError, AttributeError):
            # Should never happen
            log.warning(
                "'Name' key not present in container definition for "
                "container ID '%s' within inspect results for Docker "
                "network '%s'. Full container definition: %s",
                cid,
                name,
                cinfo,
            )
            continue
        else:
            cinfo["Id"] = cid
            ret[name] = cinfo
    if not verbose:
        return list(ret)
    return ret


def login(*registries):
    """
    .. versionadded:: 2016.3.7,2016.11.4,2017.7.0

    Performs a ``docker login`` to authenticate to one or more configured
    repositories. See the documentation at the top of this page to configure
    authentication credentials.

    Multiple registry URLs (matching those configured in Pillar) can be passed,
    and Salt will attempt to login to *just* those registries. If no registry
    URLs are provided, Salt will attempt to login to *all* configured
    registries.

    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Results`` - A dictionary mapping registry URLs to the authentication
      result. ``True`` means a successful login, ``False`` means a failed
      login.
    - ``Errors`` - A list of errors encountered during the course of this
      function.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.login
        salt myminion docker.login hub
        salt myminion docker.login hub https://mydomain.tld/registry/
    """
    # NOTE: This function uses the "docker login" CLI command so that login
    # information is added to the config.json, since docker-py isn't designed
    # to do so.
    registry_auth = __salt__["config.get"]("docker-registries", {})
    ret = {"retcode": 0}
    errors = ret.setdefault("Errors", [])
    if not isinstance(registry_auth, dict):
        errors.append("'docker-registries' Pillar value must be a dictionary")
        registry_auth = {}
    for reg_name, reg_conf in __salt__["config.option"](
        "*-docker-registries", wildcard=True
    ).items():
        try:
            registry_auth.update(reg_conf)
        except TypeError:
            errors.append(
                "Docker registry '{}' was not specified as a dictionary".format(
                    reg_name
                )
            )

    # If no registries passed, we will auth to all of them
    if not registries:
        registries = list(registry_auth)

    results = ret.setdefault("Results", {})
    for registry in registries:
        if registry not in registry_auth:
            errors.append(f"No match found for registry '{registry}'")
            continue
        try:
            username = registry_auth[registry]["username"]
            password = registry_auth[registry]["password"]
        except TypeError:
            errors.append(f"Invalid configuration for registry '{registry}'")
        except KeyError as exc:
            errors.append(f"Missing {exc} for registry '{registry}'")
        else:
            cmd = ["docker", "login", "-u", username, "-p", password]
            if registry.lower() != "hub":
                cmd.append(registry)
            log.debug(
                "Attempting to login to docker registry '%s' as user '%s'",
                registry,
                username,
            )
            login_cmd = __salt__["cmd.run_all"](
                cmd,
                python_shell=False,
                output_loglevel="quiet",
            )
            results[registry] = login_cmd["retcode"] == 0
            if not results[registry]:
                if login_cmd["stderr"]:
                    errors.append(login_cmd["stderr"])
                elif login_cmd["stdout"]:
                    errors.append(login_cmd["stdout"])
    if errors:
        ret["retcode"] = 1
    return ret


def logout(*registries):
    """
    .. versionadded:: 3001

    Performs a ``docker logout`` to remove the saved authentication details for
    one or more configured repositories.

    Multiple registry URLs (matching those configured in Pillar) can be passed,
    and Salt will attempt to logout of *just* those registries. If no registry
    URLs are provided, Salt will attempt to logout of *all* configured
    registries.

    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Results`` - A dictionary mapping registry URLs to the authentication
      result. ``True`` means a successful logout, ``False`` means a failed
      logout.
    - ``Errors`` - A list of errors encountered during the course of this
      function.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.logout
        salt myminion docker.logout hub
        salt myminion docker.logout hub https://mydomain.tld/registry/
    """
    # NOTE: This function uses the "docker logout" CLI command to remove
    # authentication information from config.json. docker-py does not support
    # this usecase (see https://github.com/docker/docker-py/issues/1091)

    # To logout of all known (to Salt) docker registries, they have to be collected first
    registry_auth = __salt__["config.get"]("docker-registries", {})
    ret = {"retcode": 0}
    errors = ret.setdefault("Errors", [])
    if not isinstance(registry_auth, dict):
        errors.append("'docker-registries' Pillar value must be a dictionary")
        registry_auth = {}
    for reg_name, reg_conf in __salt__["config.option"](
        "*-docker-registries", wildcard=True
    ).items():
        try:
            registry_auth.update(reg_conf)
        except TypeError:
            errors.append(
                "Docker registry '{}' was not specified as a dictionary".format(
                    reg_name
                )
            )

    # If no registries passed, we will logout of all known registries
    if not registries:
        registries = list(registry_auth)

    results = ret.setdefault("Results", {})
    for registry in registries:
        if registry not in registry_auth:
            errors.append(f"No match found for registry '{registry}'")
            continue
        else:
            cmd = ["docker", "logout"]
            if registry.lower() != "hub":
                cmd.append(registry)
            log.debug("Attempting to logout of docker registry '%s'", registry)
            logout_cmd = __salt__["cmd.run_all"](
                cmd,
                python_shell=False,
                output_loglevel="quiet",
            )
            results[registry] = logout_cmd["retcode"] == 0
            if not results[registry]:
                if logout_cmd["stderr"]:
                    errors.append(logout_cmd["stderr"])
                elif logout_cmd["stdout"]:
                    errors.append(logout_cmd["stdout"])
    if errors:
        ret["retcode"] = 1
    return ret


# Functions for information gathering
def depends(name):
    """
    Returns the containers and images, if any, which depend on the given image

    name
        Name or ID of image


    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Containers`` - A list of containers which depend on the specified image
    - ``Images`` - A list of IDs of images which depend on the specified image

    CLI Example:

    .. code-block:: bash

        salt myminion docker.depends myimage
        salt myminion docker.depends 0123456789ab
    """
    # Resolve tag or short-SHA to full SHA
    image_id = inspect_image(name)["Id"]

    container_depends = []
    for container in ps_(all=True, verbose=True).values():
        if container["Info"]["Image"] == image_id:
            container_depends.extend([x.lstrip("/") for x in container["Names"]])

    return {
        "Containers": container_depends,
        "Images": [
            x[:12] for x, y in images(all=True).items() if y["ParentId"] == image_id
        ],
    }


def diff(name):
    """
    Get information on changes made to container's filesystem since it was
    created. Equivalent to running the ``docker diff`` Docker CLI command.

    name
        Container name or ID


    **RETURN DATA**

    A dictionary containing any of the following keys:

    - ``Added`` - A list of paths that were added.
    - ``Changed`` - A list of paths that were changed.
    - ``Deleted`` - A list of paths that were deleted.

    These keys will only be present if there were changes, so if the container
    has no differences the return dict will be empty.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.diff mycontainer
    """
    changes = _client_wrapper("diff", name)
    kind_map = {0: "Changed", 1: "Added", 2: "Deleted"}
    ret = {}
    for change in changes:
        key = kind_map.get(change["Kind"], "Unknown")
        ret.setdefault(key, []).append(change["Path"])
    if "Unknown" in ret:
        log.error(
            "Unknown changes detected in docker.diff of container %s. "
            "This is probably due to a change in the Docker API. Please "
            "report this to the SaltStack developers",
            name,
        )
    return ret


def exists(name):
    """
    Check if a given container exists

    name
        Container name or ID


    **RETURN DATA**

    A boolean (``True`` if the container exists, otherwise ``False``)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.exists mycontainer
    """
    contextkey = f"docker.exists.{name}"
    if contextkey in __context__:
        return __context__[contextkey]
    try:
        c_info = _client_wrapper("inspect_container", name, catch_api_errors=False)
    except docker.errors.APIError:
        __context__[contextkey] = False
    else:
        __context__[contextkey] = True
    return __context__[contextkey]


def history(name, quiet=False):
    """
    Return the history for an image. Equivalent to running the ``docker
    history`` Docker CLI command.

    name
        Container name or ID

    quiet : False
        If ``True``, the return data will simply be a list of the commands run
        to build the container.

        .. code-block:: bash

            $ salt myminion docker.history nginx:latest quiet=True
            myminion:
                - FROM scratch
                - ADD file:ef063ed0ae9579362871b9f23d2bc0781ef7cd4de6ac822052cf6c9c5a12b1e2 in /
                - CMD [/bin/bash]
                - MAINTAINER NGINX Docker Maintainers "docker-maint@nginx.com"
                - apt-key adv --keyserver pgp.mit.edu --recv-keys 573BFD6B3D8FBC641079A6ABABF5BD827BD9BF62
                - echo "deb http://nginx.org/packages/mainline/debian/ wheezy nginx" >> /etc/apt/sources.list
                - ENV NGINX_VERSION=1.7.10-1~wheezy
                - apt-get update &&     apt-get install -y ca-certificates nginx=${NGINX_VERSION} &&     rm -rf /var/lib/apt/lists/*
                - ln -sf /dev/stdout /var/log/nginx/access.log
                - ln -sf /dev/stderr /var/log/nginx/error.log
                - VOLUME [/var/cache/nginx]
                - EXPOSE map[80/tcp:{} 443/tcp:{}]
                - CMD [nginx -g daemon off;]
                        https://github.com/saltstack/salt/pull/22421


    **RETURN DATA**

    If ``quiet=False``, the return value will be a list of dictionaries
    containing information about each step taken to build the image. The keys
    in each step include the following:

    - ``Command`` - The command executed in this build step
    - ``Id`` - Layer ID
    - ``Size`` - Cumulative image size, in bytes
    - ``Size_Human`` - Cumulative image size, in human-readable units
    - ``Tags`` - Tag(s) assigned to this layer
    - ``Time_Created_Epoch`` - Time this build step was completed (Epoch
      time)
    - ``Time_Created_Local`` - Time this build step was completed (Minion's
      local timezone)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.exists mycontainer
    """
    response = _client_wrapper("history", name)
    key_map = {
        "CreatedBy": "Command",
        "Created": "Time_Created_Epoch",
    }
    command_prefix = re.compile(r"^/bin/sh -c (?:#\(nop\) )?")
    ret = []
    # history is most-recent first, reverse this so it is ordered top-down
    for item in reversed(response):
        step = {}
        for key, val in item.items():
            step_key = key_map.get(key, key)
            if step_key == "Command":
                if not val:
                    # We assume that an empty build step is 'FROM scratch'
                    val = "FROM scratch"
                else:
                    val = command_prefix.sub("", val)
            step[step_key] = val
        if "Time_Created_Epoch" in step:
            step["Time_Created_Local"] = time.strftime(
                "%Y-%m-%d %H:%M:%S %Z", time.localtime(step["Time_Created_Epoch"])
            )
        for param in ("Size",):
            if param in step:
                step[f"{param}_Human"] = _size_fmt(step[param])
        ret.append(copy.deepcopy(step))
    if quiet:
        return [x.get("Command") for x in ret]
    return ret


def images(verbose=False, **kwargs):
    """
    Returns information about the Docker images on the Minion. Equivalent to
    running the ``docker images`` Docker CLI command.

    all : False
        If ``True``, untagged images will also be returned

    verbose : False
        If ``True``, a ``docker inspect`` will be run on each image returned.


    **RETURN DATA**

    A dictionary with each key being an image ID, and each value some general
    info about that image (time created, size, tags associated with the image,
    etc.)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.images
        salt myminion docker.images all=True
    """
    if "docker.images" not in __context__:
        response = _client_wrapper("images", all=kwargs.get("all", False))
        key_map = {
            "Created": "Time_Created_Epoch",
        }
        for img in response:
            img_id = img.pop("Id", None)
            if img_id is None:
                continue
            for item in img:
                img_state = (
                    "untagged"
                    if img["RepoTags"]
                    in (
                        ["<none>:<none>"],  # docker API <1.24
                        None,  # docker API >=1.24
                    )
                    else "tagged"
                )
                bucket = __context__.setdefault("docker.images", {})
                bucket = bucket.setdefault(img_state, {})
                img_key = key_map.get(item, item)
                bucket.setdefault(img_id, {})[img_key] = img[item]
            if "Time_Created_Epoch" in bucket.get(img_id, {}):
                bucket[img_id]["Time_Created_Local"] = time.strftime(
                    "%Y-%m-%d %H:%M:%S %Z",
                    time.localtime(bucket[img_id]["Time_Created_Epoch"]),
                )
            for param in ("Size", "VirtualSize"):
                if param in bucket.get(img_id, {}):
                    bucket[img_id][f"{param}_Human"] = _size_fmt(bucket[img_id][param])

    context_data = __context__.get("docker.images", {})
    ret = copy.deepcopy(context_data.get("tagged", {}))
    if kwargs.get("all", False):
        ret.update(copy.deepcopy(context_data.get("untagged", {})))

    # If verbose info was requested, go get it
    if verbose:
        for img_id in ret:
            ret[img_id]["Info"] = inspect_image(img_id)

    return ret


def info():
    """
    Returns a dictionary of system-wide information. Equivalent to running
    the ``docker info`` Docker CLI command.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.info
    """
    return _client_wrapper("info")


def inspect(name):
    """
    .. versionchanged:: 2017.7.0
        Volumes and networks are now checked, in addition to containers and
        images.

    This is a generic container/image/volume/network inspecton function. It
    will run the following functions in order:

    - :py:func:`docker.inspect_container
      <salt.modules.dockermod.inspect_container>`
    - :py:func:`docker.inspect_image <salt.modules.dockermod.inspect_image>`
    - :py:func:`docker.inspect_volume <salt.modules.dockermod.inspect_volume>`
    - :py:func:`docker.inspect_network <salt.modules.dockermod.inspect_network>`

    The first of these to find a match will be returned.

    name
        Container/image/volume/network name or ID


    **RETURN DATA**

    A dictionary of container/image/volume/network information

    CLI Example:

    .. code-block:: bash

        salt myminion docker.inspect mycontainer
        salt myminion docker.inspect busybox
    """
    try:
        return inspect_container(name)
    except CommandExecutionError as exc:
        if "does not exist" not in exc.strerror:
            raise
    try:
        return inspect_image(name)
    except CommandExecutionError as exc:
        if not exc.strerror.startswith("Error 404"):
            raise
    try:
        return inspect_volume(name)
    except CommandExecutionError as exc:
        if not exc.strerror.startswith("Error 404"):
            raise
    try:
        return inspect_network(name)
    except CommandExecutionError as exc:
        if not exc.strerror.startswith("Error 404"):
            raise

    raise CommandExecutionError(
        f"Error 404: No such image/container/volume/network: {name}"
    )


def inspect_container(name):
    """
    Retrieves container information. Equivalent to running the ``docker
    inspect`` Docker CLI command, but will only look for container information.

    name
        Container name or ID


    **RETURN DATA**

    A dictionary of container information

    CLI Example:

    .. code-block:: bash

        salt myminion docker.inspect_container mycontainer
        salt myminion docker.inspect_container 0123456789ab
    """
    return _client_wrapper("inspect_container", name)


def inspect_image(name):
    """
    Retrieves image information. Equivalent to running the ``docker inspect``
    Docker CLI command, but will only look for image information.

    .. note::
        To inspect an image, it must have been pulled from a registry or built
        locally. Images on a Docker registry which have not been pulled cannot
        be inspected.

    name
        Image name or ID


    **RETURN DATA**

    A dictionary of image information

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.inspect_image busybox
        salt myminion docker.inspect_image centos:6
        salt myminion docker.inspect_image 0123456789ab
    """
    ret = _client_wrapper("inspect_image", name)
    for param in ("Size", "VirtualSize"):
        if param in ret:
            ret[f"{param}_Human"] = _size_fmt(ret[param])
    return ret


def list_containers(**kwargs):
    """
    Returns a list of containers by name. This is different from
    :py:func:`docker.ps <salt.modules.dockermod.ps_>` in that
    :py:func:`docker.ps <salt.modules.dockermod.ps_>` returns its results
    organized by container ID.

    all : False
        If ``True``, stopped containers will be included in return data

    CLI Example:

    .. code-block:: bash

        salt myminion docker.list_containers
    """
    ret = set()
    for item in ps_(all=kwargs.get("all", False)).values():
        names = item.get("Names")
        if not names:
            continue
        for c_name in [x.lstrip("/") for x in names or []]:
            ret.add(c_name)
    return sorted(ret)


def list_tags():
    """
    Returns a list of tagged images

    CLI Example:

    .. code-block:: bash

        salt myminion docker.list_tags
    """
    ret = set()
    for item in images().values():
        if not item.get("RepoTags"):
            continue
        ret.update(set(item["RepoTags"]))
    return sorted(ret)


def resolve_image_id(name):
    """
    .. versionadded:: 2018.3.0

    Given an image name (or partial image ID), return the full image ID. If no
    match is found among the locally-pulled images, then ``False`` will be
    returned.

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.resolve_image_id foo
        salt myminion docker.resolve_image_id foo:bar
        salt myminion docker.resolve_image_id 36540f359ca3
    """
    try:
        inspect_result = inspect_image(name)
        return inspect_result["Id"]
    except CommandExecutionError:
        # No matching image pulled locally, or inspect_image otherwise failed
        pass
    except KeyError:
        log.error(
            "Inspecting docker image '%s' returned an unexpected data structure: %s",
            name,
            inspect_result,
        )
    return False


def resolve_tag(name, **kwargs):
    """
    .. versionadded:: 2017.7.2
    .. versionchanged:: 2018.3.0
        Instead of matching against pulled tags using
        :py:func:`docker.list_tags <salt.modules.dockermod.list_tags>`, this
        function now simply inspects the passed image name using
        :py:func:`docker.inspect_image <salt.modules.dockermod.inspect_image>`
        and returns the first matching tag. If no matching tags are found, it
        is assumed that the passed image is an untagged image ID, and the full
        ID is returned.

    Inspects the specified image name and returns the first matching tag in the
    inspect results. If the specified image is not pulled locally, this
    function will return ``False``.

    name
        Image name to resolve. If the image is found but there are no tags,
        this means that the image name passed was an untagged image. In this
        case the image ID will be returned.

    all : False
        If ``True``, a list of all matching tags will be returned. If the image
        is found but there are no tags, then a list will still be returned, but
        it will simply contain the image ID.

        .. versionadded:: 2018.3.0

    tags
        .. deprecated:: 2018.3.0

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.resolve_tag busybox
        salt myminion docker.resolve_tag centos:7 all=True
        salt myminion docker.resolve_tag c9f378ac27d9
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)
    all_ = kwargs.pop("all", False)
    if kwargs:
        __utils__["args.invalid_kwargs"](kwargs)

    try:
        inspect_result = inspect_image(name)
        tags = inspect_result["RepoTags"]
        if all_:
            if tags:
                return tags
                # If the image is untagged, don't return an empty list, return
                # back the resolved ID at he end of this function.
        else:
            return tags[0]
    except CommandExecutionError:
        # No matching image pulled locally, or inspect_image otherwise failed
        return False
    except KeyError:
        log.error(
            "Inspecting docker image '%s' returned an unexpected data structure: %s",
            name,
            inspect_result,
        )
    except IndexError:
        # The image passed is an untagged image ID
        pass
    return [inspect_result["Id"]] if all_ else inspect_result["Id"]


def logs(name, **kwargs):
    """
    .. versionchanged:: 2018.3.0
        Support for all of docker-py's `logs()`_ function's arguments, with the
        exception of ``stream``.

    Returns the logs for the container. An interface to docker-py's `logs()`_
    function.

    name
        Container name or ID

    stdout : True
        Return stdout lines

    stderr : True
        Return stdout lines

    timestamps : False
        Show timestamps

    tail : all
        Output specified number of lines at the end of logs. Either an integer
        number of lines or the string ``all``.

    since
        Show logs since the specified time, passed as a UNIX epoch timestamp.
        Optionally, if timelib_ is installed on the minion the timestamp can be
        passed as a string which will be resolved to a date using
        ``timelib.strtodatetime()``.

    follow : False
        If ``True``, this function will block until the container exits and
        return the logs when it does. The default behavior is to return what is
        in the log at the time this function is executed.

        .. note:
            Since it blocks, this option should be used with caution.

    CLI Examples:

    .. code-block:: bash

        # All logs
        salt myminion docker.logs mycontainer
        # Last 100 lines of log
        salt myminion docker.logs mycontainer tail=100
        # Just stderr
        salt myminion docker.logs mycontainer stdout=False
        # Logs since a specific UNIX timestamp
        salt myminion docker.logs mycontainer since=1511688459
        # Flexible format for "since" argument (requires timelib)
        salt myminion docker.logs mycontainer since='1 hour ago'
        salt myminion docker.logs mycontainer since='1 week ago'
        salt myminion docker.logs mycontainer since='1 fortnight ago'
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)
    if "stream" in kwargs:
        raise SaltInvocationError("The 'stream' argument is not supported")

    try:
        kwargs["since"] = int(kwargs["since"])
    except KeyError:
        pass
    except (ValueError, TypeError):
        # Try to resolve down to a datetime.datetime object using timelib. If
        # it's not installed, pass the value as-is and let docker-py throw an
        # APIError.
        if HAS_TIMELIB:
            try:
                kwargs["since"] = timelib.strtodatetime(kwargs["since"])
            except Exception as exc:  # pylint: disable=broad-except
                log.warning(
                    "docker.logs: Failed to parse '%s' using timelib: %s",
                    kwargs["since"],
                    exc,
                )

    # logs() returns output as bytestrings
    return salt.utils.stringutils.to_unicode(_client_wrapper("logs", name, **kwargs))


def pid(name):
    """
    Returns the PID of a container

    name
        Container name or ID

    CLI Example:

    .. code-block:: bash

        salt myminion docker.pid mycontainer
        salt myminion docker.pid 0123456789ab
    """
    return inspect_container(name)["State"]["Pid"]


def port(name, private_port=None):
    """
    Returns port mapping information for a given container. Equivalent to
    running the ``docker port`` Docker CLI command.

    name
        Container name or ID

        .. versionchanged:: 2019.2.0
            This value can now be a pattern expression (using the
            pattern-matching characters defined in fnmatch_). If a pattern
            expression is used, this function will return a dictionary mapping
            container names which match the pattern to the mappings for those
            containers. When no pattern expression is used, a dictionary of the
            mappings for the specified container name will be returned.

        .. _fnmatch: https://docs.python.org/2/library/fnmatch.html

    private_port : None
        If specified, get information for that specific port. Can be specified
        either as a port number (i.e. ``5000``), or as a port number plus the
        protocol (i.e. ``5000/udp``).

        If this argument is omitted, all port mappings will be returned.


    **RETURN DATA**

    A dictionary of port mappings, with the keys being the port and the values
    being the mapping(s) for that port.

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.port mycontainer
        salt myminion docker.port mycontainer 5000
        salt myminion docker.port mycontainer 5000/udp
    """
    pattern_used = bool(re.search(r"[*?\[]", name))
    names = fnmatch.filter(list_containers(all=True), name) if pattern_used else [name]

    if private_port is None:
        pattern = "*"
    else:
        # Sanity checks
        if isinstance(private_port, int):
            pattern = f"{private_port}/*"
        else:
            err = (
                "Invalid private_port '{}'. Must either be a port number, "
                "or be in port/protocol notation (e.g. 5000/tcp)".format(private_port)
            )
            try:
                port_num, _, protocol = private_port.partition("/")
                protocol = protocol.lower()
                if not port_num.isdigit() or protocol not in ("tcp", "udp"):
                    raise SaltInvocationError(err)
                pattern = port_num + "/" + protocol
            except AttributeError:
                raise SaltInvocationError(err)

    ret = {}
    for c_name in names:
        # docker.client.Client.port() doesn't do what we need, so just inspect
        # the container and get the information from there. It's what they're
        # already doing (poorly) anyway.
        mappings = inspect_container(c_name).get("NetworkSettings", {}).get("Ports", {})
        ret[c_name] = {x: mappings[x] for x in fnmatch.filter(mappings, pattern)}

    return ret.get(name, {}) if not pattern_used else ret


def ps_(filters=None, **kwargs):
    """
    Returns information about the Docker containers on the Minion. Equivalent
    to running the ``docker ps`` Docker CLI command.

    all : False
        If ``True``, stopped containers will also be returned

    host: False
        If ``True``, local host's network topology will be included

    verbose : False
        If ``True``, a ``docker inspect`` will be run on each container
        returned.

    filters: None
        A dictionary of filters to be processed on the container list.
        Available filters:

          - exited (int): Only containers with specified exit code
          - status (str): One of restarting, running, paused, exited
          - label (str): format either "key" or "key=value"

    **RETURN DATA**

    A dictionary with each key being an container ID, and each value some
    general info about that container (time created, name, command, etc.)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.ps
        salt myminion docker.ps all=True
        salt myminion docker.ps filters="{'label': 'role=web'}"
    """
    response = _client_wrapper("containers", all=True, filters=filters)
    key_map = {
        "Created": "Time_Created_Epoch",
    }
    context_data = {}
    for container in response:
        c_id = container.pop("Id", None)
        if c_id is None:
            continue
        for item in container:
            c_state = (
                "running"
                if container.get("Status", "").lower().startswith("up ")
                else "stopped"
            )
            bucket = context_data.setdefault(c_state, {})
            c_key = key_map.get(item, item)
            bucket.setdefault(c_id, {})[c_key] = container[item]
        if "Time_Created_Epoch" in bucket.get(c_id, {}):
            bucket[c_id]["Time_Created_Local"] = time.strftime(
                "%Y-%m-%d %H:%M:%S %Z",
                time.localtime(bucket[c_id]["Time_Created_Epoch"]),
            )

    ret = copy.deepcopy(context_data.get("running", {}))
    if kwargs.get("all", False):
        ret.update(copy.deepcopy(context_data.get("stopped", {})))

    # If verbose info was requested, go get it
    if kwargs.get("verbose", False):
        for c_id in ret:
            ret[c_id]["Info"] = inspect_container(c_id)

    if kwargs.get("host", False):
        ret.setdefault("host", {}).setdefault("interfaces", {}).update(
            __salt__["network.interfaces"]()
        )
    return ret


def state(name):
    """
    Returns the state of the container

    name
        Container name or ID


    **RETURN DATA**

    A string representing the current state of the container (either
    ``running``, ``paused``, or ``stopped``)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.state mycontainer
    """
    contextkey = f"docker.state.{name}"
    if contextkey in __context__:
        return __context__[contextkey]
    __context__[contextkey] = _get_state(inspect_container(name))
    return __context__[contextkey]


def search(name, official=False, trusted=False):
    """
    Searches the registry for an image

    name
        Search keyword

    official : False
        Limit results to official builds

    trusted : False
        Limit results to `trusted builds`_

    **RETURN DATA**

    A dictionary with each key being the name of an image, and the following
    information for each image:

    - ``Description`` - Image description
    - ``Official`` - A boolean (``True`` if an official build, ``False`` if
      not)
    - ``Stars`` - Number of stars the image has on the registry
    - ``Trusted`` - A boolean (``True`` if a trusted build, ``False`` if not)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.search centos
        salt myminion docker.search centos official=True
    """
    response = _client_wrapper("search", name)
    if not response:
        raise CommandExecutionError(f"No images matched the search string '{name}'")

    key_map = {
        "description": "Description",
        "is_official": "Official",
        "is_trusted": "Trusted",
        "star_count": "Stars",
    }
    limit = []
    if official:
        limit.append("Official")
    if trusted:
        limit.append("Trusted")

    results = {}
    for item in response:
        c_name = item.pop("name", None)
        if c_name is not None:
            for key in item:
                mapped_key = key_map.get(key, key)
                results.setdefault(c_name, {})[mapped_key] = item[key]

    if not limit:
        return results

    ret = {}
    for key, val in results.items():
        for item in limit:
            if val.get(item, False):
                ret[key] = val
                break
    return ret


def top(name):
    """
    Runs the `docker top` command on a specific container

    name
        Container name or ID

    CLI Example:

    **RETURN DATA**

    A list of dictionaries containing information about each process


    .. code-block:: bash

        salt myminion docker.top mycontainer
        salt myminion docker.top 0123456789ab
    """
    response = _client_wrapper("top", name)

    # Read in column names
    columns = {}
    for idx, col_name in enumerate(response["Titles"]):
        columns[idx] = col_name

    # Build return dict
    ret = []
    for process in response["Processes"]:
        cur_proc = {}
        for idx, val in enumerate(process):
            cur_proc[columns[idx]] = val
        ret.append(cur_proc)
    return ret


def version():
    """
    Returns a dictionary of Docker version information. Equivalent to running
    the ``docker version`` Docker CLI command.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.version
    """
    ret = _client_wrapper("version")
    version_re = re.compile(VERSION_RE)
    if "Version" in ret:
        match = version_re.match(str(ret["Version"]))
        if match:
            ret["VersionInfo"] = tuple(int(x) for x in match.group(1).split("."))
    if "ApiVersion" in ret:
        match = version_re.match(str(ret["ApiVersion"]))
        if match:
            ret["ApiVersionInfo"] = tuple(int(x) for x in match.group(1).split("."))
    return ret


def _create_networking_config(networks):
    log.debug("creating networking config from %s", networks)
    return _client_wrapper(
        "create_networking_config",
        {
            k: _client_wrapper("create_endpoint_config", **v)
            for k, v in networks.items()
        },
    )


# Functions to manage containers
@_refresh_mine_cache
def create(
    image,
    name=None,
    start=False,
    skip_translate=None,
    ignore_collisions=False,
    validate_ip_addrs=True,
    client_timeout=salt.utils.dockermod.CLIENT_TIMEOUT,
    **kwargs,
):
    """
    Create a new container

    image
        Image from which to create the container

    name
        Name for the new container. If not provided, Docker will randomly
        generate one for you (it will be included in the return data).

    start : False
        If ``True``, start container after creating it

        .. versionadded:: 2018.3.0

    skip_translate
        This function translates Salt CLI or SLS input into the format which
        docker-py expects. However, in the event that Salt's translation logic
        fails (due to potential changes in the Docker Remote API, or to bugs in
        the translation code), this argument can be used to exert granular
        control over which arguments are translated and which are not.

        Pass this argument as a comma-separated list (or Python list) of
        arguments, and translation for each passed argument name will be
        skipped. Alternatively, pass ``True`` and *all* translation will be
        skipped.

        Skipping tranlsation allows for arguments to be formatted directly in
        the format which docker-py expects. This allows for API changes and
        other issues to be more easily worked around. An example of using this
        option to skip translation would be:

        .. code-block:: bash

            salt myminion docker.create image=centos:7.3.1611 skip_translate=environment environment="{'FOO': 'bar'}"

        See the following links for more information:

        - `docker-py Low-level API`_
        - `Docker Engine API`_

    ignore_collisions : False
        Since many of docker-py's arguments differ in name from their CLI
        counterparts (with which most Docker users are more familiar), Salt
        detects usage of these and aliases them to the docker-py version of
        that argument. However, if both the alias and the docker-py version of
        the same argument (e.g. ``env`` and ``environment``) are used, an error
        will be raised. Set this argument to ``True`` to suppress these errors
        and keep the docker-py version of the argument.

    validate_ip_addrs : True
        For parameters which accept IP addresses as input, IP address
        validation will be performed. To disable, set this to ``False``

    client_timeout : 60
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.

        .. note::

            This is only used if Salt needs to pull the requested image.

    **CONTAINER CONFIGURATION ARGUMENTS**

    auto_remove (or *rm*) : False
        Enable auto-removal of the container on daemon side when the
        container’s process exits (analogous to running a docker container with
        ``--rm`` on the CLI).

        Examples:

        - ``auto_remove=True``
        - ``rm=True``

    binds
        Files/directories to bind mount. Each bind mount should be passed in
        one of the following formats:

        - ``<host_path>:<container_path>`` - ``host_path`` is mounted within
          the container as ``container_path`` with read-write access.
        - ``<host_path>:<container_path>:<selinux_context>`` - ``host_path`` is
          mounted within the container as ``container_path`` with read-write
          access. Additionally, the specified selinux context will be set
          within the container.
        - ``<host_path>:<container_path>:<read_only>`` - ``host_path`` is
          mounted within the container as ``container_path``, with the
          read-only or read-write setting explicitly defined.
        - ``<host_path>:<container_path>:<read_only>,<selinux_context>`` -
          ``host_path`` is mounted within the container as ``container_path``,
          with the read-only or read-write setting explicitly defined.
          Additionally, the specified selinux context will be set within the
          container.

        ``<read_only>`` can be either ``ro`` for read-write access, or ``ro``
        for read-only access. When omitted, it is assumed to be read-write.

        ``<selinux_context>`` can be ``z`` if the volume is shared between
        multiple containers, or ``Z`` if the volume should be private.

        .. note::
            When both ``<read_only>`` and ``<selinux_context>`` are specified,
            there must be a comma before ``<selinux_context>``.

        Binds can be expressed as a comma-separated list or a Python list,
        however in cases where both ro/rw and an selinux context are specified,
        the binds *must* be specified as a Python list.

        Examples:

        - ``binds=/srv/www:/var/www:ro``
        - ``binds=/srv/www:/var/www:rw``
        - ``binds=/srv/www:/var/www``
        - ``binds="['/srv/www:/var/www:ro,Z']"``
        - ``binds="['/srv/www:/var/www:rw,Z']"``
        - ``binds=/srv/www:/var/www:Z``

        .. note::
            The second and third examples above are equivalent to each other,
            as are the last two examples.

    blkio_weight
        Block IO weight (relative weight), accepts a weight value between 10
        and 1000.

        Example: ``blkio_weight=100``

    blkio_weight_device
        Block IO weight (relative device weight), specified as a list of
        expressions in the format ``PATH:WEIGHT``

        Example: ``blkio_weight_device=/dev/sda:100``

    cap_add
        List of capabilities to add within the container. Can be passed as a
        comma-separated list or a Python list. Requires Docker 1.2.0 or
        newer.

        Examples:

        - ``cap_add=SYS_ADMIN,MKNOD``
        - ``cap_add="[SYS_ADMIN, MKNOD]"``

    cap_drop
        List of capabilities to drop within the container. Can be passed as a
        comma-separated string or a Python list. Requires Docker 1.2.0 or
        newer.

        Examples:

        - ``cap_drop=SYS_ADMIN,MKNOD``,
        - ``cap_drop="[SYS_ADMIN, MKNOD]"``

    command (or *cmd*)
        Command to run in the container

        Example: ``command=bash`` or ``cmd=bash``

        .. versionchanged:: 2015.8.1
            ``cmd`` is now also accepted

    cpuset_cpus (or *cpuset*)
        CPUs on which which to allow execution, specified as a string
        containing a range (e.g. ``0-3``) or a comma-separated list of CPUs
        (e.g. ``0,1``).

        Examples:

        - ``cpuset_cpus="0-3"``
        - ``cpuset="0,1"``

    cpuset_mems
        Memory nodes on which which to allow execution, specified as a string
        containing a range (e.g. ``0-3``) or a comma-separated list of MEMs
        (e.g. ``0,1``). Only effective on NUMA systems.

        Examples:

        - ``cpuset_mems="0-3"``
        - ``cpuset_mems="0,1"``

    cpu_group
        The length of a CPU period in microseconds

        Example: ``cpu_group=100000``

    cpu_period
        Microseconds of CPU time that the container can get in a CPU period

        Example: ``cpu_period=50000``

    cpu_shares
        CPU shares (relative weight), specified as an integer between 2 and 1024.

        Example: ``cpu_shares=512``

    detach : False
        If ``True``, run the container's command in the background (daemon
        mode)

        Example: ``detach=True``

    devices
        List of host devices to expose within the container

        Examples:

        - ``devices="/dev/net/tun,/dev/xvda1:/dev/xvda1,/dev/xvdb1:/dev/xvdb1:r"``
        - ``devices="['/dev/net/tun', '/dev/xvda1:/dev/xvda1', '/dev/xvdb1:/dev/xvdb1:r']"``

    device_read_bps
        Limit read rate (bytes per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is either an
        integer number of bytes, or a string ending in ``kb``, ``mb``, or
        ``gb``.

        Examples:

        - ``device_read_bps="/dev/sda:1mb,/dev/sdb:5mb"``
        - ``device_read_bps="['/dev/sda:100mb', '/dev/sdb:5mb']"``

    device_read_iops
        Limit read rate (I/O per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is a number
        of I/O operations.

        Examples:

        - ``device_read_iops="/dev/sda:1000,/dev/sdb:500"``
        - ``device_read_iops="['/dev/sda:1000', '/dev/sdb:500']"``

    device_write_bps
        Limit write rate (bytes per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is either an
        integer number of bytes, or a string ending in ``kb``, ``mb`` or
        ``gb``.


        Examples:

        - ``device_write_bps="/dev/sda:100mb,/dev/sdb:50mb"``
        - ``device_write_bps="['/dev/sda:100mb', '/dev/sdb:50mb']"``

    device_write_iops
        Limit write rate (I/O per second) from a device, specified as a list
        of expressions in the format ``PATH:RATE``, where ``RATE`` is a number
        of I/O operations.

        Examples:

        - ``device_write_iops="/dev/sda:1000,/dev/sdb:500"``
        - ``device_write_iops="['/dev/sda:1000', '/dev/sdb:500']"``

    dns
        List of DNS nameservers. Can be passed as a comma-separated list or a
        Python list.

        Examples:

        - ``dns=8.8.8.8,8.8.4.4``
        - ``dns="['8.8.8.8', '8.8.4.4']"``

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

    dns_opt
        Additional options to be added to the container’s ``resolv.conf`` file

        Example: ``dns_opt=ndots:9``

    dns_search
        List of DNS search domains. Can be passed as a comma-separated list
        or a Python list.

        Examples:

        - ``dns_search=foo1.domain.tld,foo2.domain.tld``
        - ``dns_search="[foo1.domain.tld, foo2.domain.tld]"``

    domainname
        The domain name to use for the container

        Example: ``domainname=domain.tld``

    entrypoint
        Entrypoint for the container. Either a string (e.g. ``"mycmd --arg1
        --arg2"``) or a Python list (e.g.  ``"['mycmd', '--arg1', '--arg2']"``)

        Examples:

        - ``entrypoint="cat access.log"``
        - ``entrypoint="['cat', 'access.log']"``

    environment (or *env*)
        Either a dictionary of environment variable names and their values, or
        a Python list of strings in the format ``VARNAME=value``.

        Examples:

        - ``environment='VAR1=value,VAR2=value'``
        - ``environment="['VAR1=value', 'VAR2=value']"``
        - ``environment="{'VAR1': 'value', 'VAR2': 'value'}"``

    extra_hosts
        Additional hosts to add to the container's /etc/hosts file. Can be
        passed as a comma-separated list or a Python list. Requires Docker
        1.3.0 or newer.

        Examples:

        - ``extra_hosts=web1:10.9.8.7,web2:10.9.8.8``
        - ``extra_hosts="['web1:10.9.8.7', 'web2:10.9.8.8']"``
        - ``extra_hosts="{'web1': '10.9.8.7', 'web2': '10.9.8.8'}"``

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

    group_add
        List of additional group names and/or IDs that the container process
        will run as

        Examples:

        - ``group_add=web,network``
        - ``group_add="['web', 'network']"``

    hostname
        Hostname of the container. If not provided, and if a ``name`` has been
        provided, the ``hostname`` will default to the ``name`` that was
        passed.

        Example: ``hostname=web1``

        .. warning::

            If the container is started with ``network_mode=host``, the
            hostname will be overridden by the hostname of the Minion.

    interactive (or *stdin_open*): False
        Leave stdin open, even if not attached

        Examples:

        - ``interactive=True``
        - ``stdin_open=True``

    ipc_mode (or *ipc*)
        Set the IPC mode for the container. The default behavior is to create a
        private IPC namespace for the container, but this option can be
        used to change that behavior:

        - ``container:<container_name_or_id>`` reuses another container shared
          memory, semaphores and message queues
        - ``host``: use the host's shared memory, semaphores and message queues

        Examples:

        - ``ipc_mode=container:foo``
        - ``ipc=host``

        .. warning::
            Using ``host`` gives the container full access to local shared
            memory and is therefore considered insecure.

    isolation
        Specifies the type of isolation technology used by containers

        Example: ``isolation=hyperv``

        .. note::
            The default value on Windows server is ``process``, while the
            default value on Windows client is ``hyperv``. On Linux, only
            ``default`` is supported.

    labels (or *label*)
        Add metadata to the container. Labels can be set both with and without
        values:

        Examples:

        - ``labels=foo,bar=baz``
        - ``labels="['foo', 'bar=baz']"``

        .. versionchanged:: 2018.3.0
            Labels both with and without values can now be mixed. Earlier
            releases only permitted one method or the other.

    links
        Link this container to another. Links should be specified in the format
        ``<container_name_or_id>:<link_alias>``. Multiple links can be passed,
        ether as a comma separated list or a Python list.

        Examples:

        - ``links=web1:link1,web2:link2``,
        - ``links="['web1:link1', 'web2:link2']"``
        - ``links="{'web1': 'link1', 'web2': 'link2'}"``

    log_driver
        Set container's logging driver. Requires Docker 1.6 or newer.

        Example:

        - ``log_driver=syslog``

        .. note::
            The logging driver feature was improved in Docker 1.13 introducing
            option name changes. Please see Docker's `Configure logging
            drivers`_ documentation for more information.

        .. _`Configure logging drivers`: https://docs.docker.com/engine/admin/logging/overview/

    log_opt
        Config options for the ``log_driver`` config option. Requires Docker
        1.6 or newer.

        Example:

        - ``log_opt="syslog-address=tcp://192.168.0.42,syslog-facility=daemon"``
        - ``log_opt="['syslog-address=tcp://192.168.0.42', 'syslog-facility=daemon']"``
        - ``log_opt="{'syslog-address': 'tcp://192.168.0.42', 'syslog-facility': 'daemon'}"``

    lxc_conf
        Additional LXC configuration parameters to set before starting the
        container.

        Examples:

        - ``lxc_conf="lxc.utsname=docker,lxc.arch=x86_64"``
        - ``lxc_conf="['lxc.utsname=docker', 'lxc.arch=x86_64']"``
        - ``lxc_conf="{'lxc.utsname': 'docker', 'lxc.arch': 'x86_64'}"``

        .. note::

            These LXC configuration parameters will only have the desired
            effect if the container is using the LXC execution driver, which
            has been deprecated for some time.

    mac_address
        MAC address to use for the container. If not specified, a random MAC
        address will be used.

        Example: ``mac_address=01:23:45:67:89:0a``

    mem_limit (or *memory*) : 0
        Memory limit. Can be specified in bytes or using single-letter units
        (i.e. ``512M``, ``2G``, etc.). A value of ``0`` (the default) means no
        memory limit.

        Examples:

        - ``mem_limit=512M``
        - ``memory=1073741824``

    mem_swappiness
        Tune a container's memory swappiness behavior. Accepts an integer
        between 0 and 100.

        Example: ``mem_swappiness=60``

    memswap_limit (or *memory_swap*) : -1
        Total memory limit (memory plus swap). Set to ``-1`` to disable swap. A
        value of ``0`` means no swap limit.

        Examples:

        - ``memswap_limit=1G``
        - ``memory_swap=2147483648``

    network_disabled : False
        If ``True``, networking will be disabled within the container

        Example: ``network_disabled=True``

    network_mode : bridge
        One of the following:

        - ``bridge`` - Creates a new network stack for the container on the
          docker bridge
        - ``none`` - No networking (equivalent of the Docker CLI argument
          ``--net=none``). Not to be confused with Python's ``None``.
        - ``container:<name_or_id>`` - Reuses another container's network stack
        - ``host`` - Use the host's network stack inside the container

          .. warning::
              Using ``host`` mode gives the container full access to the hosts
              system's services (such as D-Bus), and is therefore considered
              insecure.

        Examples:

        - ``network_mode=null``
        - ``network_mode=container:web1``

    oom_kill_disable
        Whether to disable OOM killer

        Example: ``oom_kill_disable=False``

    oom_score_adj
        An integer value containing the score given to the container in order
        to tune OOM killer preferences

        Example: ``oom_score_adj=500``

    pid_mode
        Set to ``host`` to use the host container's PID namespace within the
        container. Requires Docker 1.5.0 or newer.

        Example: ``pid_mode=host``

    pids_limit
        Set the container's PID limit. Set to ``-1`` for unlimited.

        Example: ``pids_limit=2000``

    port_bindings (or *publish*)
        Bind exposed ports which were exposed using the ``ports`` argument to
        :py:func:`docker.create <salt.modules.dockermod.create>`. These
        should be passed in the same way as the ``--publish`` argument to the
        ``docker run`` CLI command:

        - ``ip:hostPort:containerPort`` - Bind a specific IP and port on the
          host to a specific port within the container.
        - ``ip::containerPort`` - Bind a specific IP and an ephemeral port to a
          specific port within the container.
        - ``hostPort:containerPort`` - Bind a specific port on all of the
          host's interfaces to a specific port within the container.
        - ``containerPort`` - Bind an ephemeral port on all of the host's
          interfaces to a specific port within the container.

        Multiple bindings can be separated by commas, or passed as a Python
        list. The below two examples are equivalent:

        - ``port_bindings="5000:5000,2123:2123/udp,8080"``
        - ``port_bindings="['5000:5000', '2123:2123/udp', 8080]"``

        Port bindings can also include ranges:

        - ``port_bindings="14505-14506:4505-4506"``

        .. note::
            When specifying a protocol, it must be passed in the
            ``containerPort`` value, as seen in the examples above.

    ports
        A list of ports to expose on the container. Can be passed as
        comma-separated list or a Python list. If the protocol is omitted, the
        port will be assumed to be a TCP port.

        Examples:

        - ``ports=1111,2222/udp``
        - ``ports="[1111, '2222/udp']"``

    privileged : False
        If ``True``, runs the exec process with extended privileges

        Example: ``privileged=True``

    publish_all_ports (or *publish_all*): False
        Publish all ports to the host

        Example: ``publish_all_ports=True``

    read_only : False
        If ``True``, mount the container’s root filesystem as read only

        Example: ``read_only=True``

    restart_policy (or *restart*)
        Set a restart policy for the container. Must be passed as a string in
        the format ``policy[:retry_count]`` where ``policy`` is one of
        ``always``, ``unless-stopped``, or ``on-failure``, and ``retry_count``
        is an optional limit to the number of retries. The retry count is ignored
        when using the ``always`` or ``unless-stopped`` restart policy.

        Examples:

        - ``restart_policy=on-failure:5``
        - ``restart_policy=always``

    security_opt
        Security configuration for MLS systems such as SELinux and AppArmor.
        Can be passed as a comma-separated list or a Python list.

        Examples:

        - ``security_opt=apparmor:unconfined,param2:value2``
        - ``security_opt='["apparmor:unconfined", "param2:value2"]'``

        .. important::
            Some security options can contain commas. In these cases, this
            argument *must* be passed as a Python list, as splitting by comma
            will result in an invalid configuration.

        .. note::
            See the documentation for security_opt at
            https://docs.docker.com/engine/reference/run/#security-configuration

    shm_size
        Size of /dev/shm

        Example: ``shm_size=128M``

    stop_signal
        The signal used to stop the container. The default is ``SIGTERM``.

        Example: ``stop_signal=SIGRTMIN+3``

    stop_timeout
        Timeout to stop the container, in seconds

        Example: ``stop_timeout=5``

    storage_opt
        Storage driver options for the container

        Examples:

        - ``storage_opt='dm.basesize=40G'``
        - ``storage_opt="['dm.basesize=40G']"``
        - ``storage_opt="{'dm.basesize': '40G'}"``

    sysctls (or *sysctl*)
        Set sysctl options for the container

        Examples:

        - ``sysctl='fs.nr_open=1048576,kernel.pid_max=32768'``
        - ``sysctls="['fs.nr_open=1048576', 'kernel.pid_max=32768']"``
        - ``sysctls="{'fs.nr_open': '1048576', 'kernel.pid_max': '32768'}"``

    tmpfs
        A map of container directories which should be replaced by tmpfs
        mounts, and their corresponding mount options. Can be passed as Python
        list of PATH:VALUE mappings, or a Python dictionary. However, since
        commas usually appear in the values, this option *cannot* be passed as
        a comma-separated list.

        Examples:

        - ``tmpfs="['/run:rw,noexec,nosuid,size=65536k', '/var/lib/mysql:rw,noexec,nosuid,size=600m']"``
        - ``tmpfs="{'/run': 'rw,noexec,nosuid,size=65536k', '/var/lib/mysql': 'rw,noexec,nosuid,size=600m'}"``

    tty : False
        Attach TTYs

        Example: ``tty=True``

    ulimits (or *ulimit*)
        List of ulimits. These limits should be passed in the format
        ``<ulimit_name>:<soft_limit>:<hard_limit>``, with the hard limit being
        optional. Can be passed as a comma-separated list or a Python list.

        Examples:

        - ``ulimits="nofile=1024:1024,nproc=60"``
        - ``ulimits="['nofile=1024:1024', 'nproc=60']"``

    user
        User under which to run exec process

        Example: ``user=foo``

    userns_mode (or *user_ns_mode*)
        Sets the user namsepace mode, when the user namespace remapping option
        is enabled.

        Example: ``userns_mode=host``

    volumes (or *volume*)
        List of directories to expose as volumes. Can be passed as a
        comma-separated list or a Python list.

        Examples:

        - ``volumes=/mnt/vol1,/mnt/vol2``
        - ``volume="['/mnt/vol1', '/mnt/vol2']"``

    volumes_from
        Container names or IDs from which the container will get volumes. Can
        be passed as a comma-separated list or a Python list.

        Example: ``volumes_from=foo``, ``volumes_from=foo,bar``,
        ``volumes_from="[foo, bar]"``

    volume_driver
        Sets the container's volume driver

        Example: ``volume_driver=foobar``

    working_dir (or *workdir*)
        Working directory inside the container

        Examples:

        - ``working_dir=/var/log/nginx``
        - ``workdir=/var/www/myapp``

    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Id`` - ID of the newly-created container
    - ``Name`` - Name of the newly-created container

    CLI Example:

    .. code-block:: bash

        # Create a data-only container
        salt myminion docker.create myuser/mycontainer volumes="/mnt/vol1,/mnt/vol2"
        # Create a CentOS 7 container that will stay running once started
        salt myminion docker.create centos:7 name=mycent7 interactive=True tty=True command=bash
    """
    if kwargs.pop("inspect", True) and not resolve_image_id(image):
        pull(image, client_timeout=client_timeout)

    kwargs, unused_kwargs = _get_create_kwargs(
        skip_translate=skip_translate,
        ignore_collisions=ignore_collisions,
        validate_ip_addrs=validate_ip_addrs,
        **kwargs,
    )

    if unused_kwargs:
        log.warning(
            "The following arguments were ignored because they are not "
            "recognized by docker-py: %s",
            sorted(unused_kwargs),
        )

    log.debug(
        "docker.create: creating container %susing the following arguments: %s",
        f"with name '{name}' " if name is not None else "",
        kwargs,
    )
    time_started = time.time()
    response = _client_wrapper("create_container", image, name=name, **kwargs)
    response["Time_Elapsed"] = time.time() - time_started
    _clear_context()

    if name is None:
        name = inspect_container(response["Id"])["Name"].lstrip("/")
    response["Name"] = name

    if start:
        try:
            start_(name)
        except CommandExecutionError as exc:
            raise CommandExecutionError(
                "Failed to start container after creation",
                info={"response": response, "error": str(exc)},
            )
        else:
            response["Started"] = True

    return response


@_refresh_mine_cache
def run_container(
    image,
    name=None,
    skip_translate=None,
    ignore_collisions=False,
    validate_ip_addrs=True,
    client_timeout=salt.utils.dockermod.CLIENT_TIMEOUT,
    bg=False,
    replace=False,
    force=False,
    networks=None,
    **kwargs,
):
    """
    .. versionadded:: 2018.3.0

    Equivalent to ``docker run`` on the Docker CLI. Runs the container, waits
    for it to exit, and returns the container's logs when complete.

    .. note::
        Not to be confused with :py:func:`docker.run
        <salt.modules.dockermod.run>`, which provides a :py:func:`cmd.run
        <salt.modules.cmdmod.run>`-like interface for executing commands in a
        running container.

    This function accepts the same arguments as :py:func:`docker.create
    <salt.modules.dockermod.create>`, with the exception of ``start``. In
    addition, it accepts the arguments from :py:func:`docker.logs
    <salt.modules.dockermod.logs>`, with the exception of ``follow``, to
    control how logs are returned. Finally, the ``bg`` argument described below
    can be used to optionally run the container in the background (the default
    behavior is to block until the container exits).

    bg : False
        If ``True``, this function will not wait for the container to exit and
        will not return its logs. It will however return the container's name
        and ID, allowing for :py:func:`docker.logs
        <salt.modules.dockermod.logs>` to be used to view the logs.

        .. note::
            The logs will be inaccessible once the container exits if
            ``auto_remove`` is set to ``True``, so keep this in mind.

    replace : False
        If ``True``, and if the named container already exists, this will
        remove the existing container. The default behavior is to return a
        ``False`` result when the container already exists.

    force : False
        If ``True``, and the named container already exists, *and* ``replace``
        is also set to ``True``, then the container will be forcibly removed.
        Otherwise, the state will not proceed and will return a ``False``
        result.

    networks
        Networks to which the container should be connected. If automatic IP
        configuration is being used, the networks can be a simple list of
        network names. If custom IP configuration is being used, then this
        argument must be passed as a dictionary.

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.run_container myuser/myimage command=/usr/local/bin/myscript.sh
        # Run container in the background
        salt myminion docker.run_container myuser/myimage command=/usr/local/bin/myscript.sh bg=True
        # Connecting to two networks using automatic IP configuration
        salt myminion docker.run_container myuser/myimage command='perl /scripts/sync.py' networks=net1,net2
        # net1 using automatic IP, net2 using static IPv4 address
        salt myminion docker.run_container myuser/myimage command='perl /scripts/sync.py' networks='{"net1": {}, "net2": {"ipv4_address": "192.168.27.12"}}'
    """
    if kwargs.pop("inspect", True) and not resolve_image_id(image):
        pull(image, client_timeout=client_timeout)

    removed_ids = None
    if name is not None:
        try:
            pre_state = __salt__["docker.state"](name)
        except CommandExecutionError:
            pass
        else:
            if pre_state == "running" and not (replace and force):
                raise CommandExecutionError(
                    "Container '{}' exists and is running. Run with "
                    "replace=True and force=True to force removal of the "
                    "existing container.".format(name)
                )
            elif not replace:
                raise CommandExecutionError(
                    "Container '{}' exists. Run with replace=True to "
                    "remove the existing container".format(name)
                )
            else:
                # We don't have to try/except this, we want it to raise a
                # CommandExecutionError if we fail to remove the existing
                # container so that we gracefully abort before attempting to go
                # any further.
                removed_ids = rm_(name, force=force)

    log_kwargs = {}
    for argname in get_client_args("logs")["logs"]:
        try:
            log_kwargs[argname] = kwargs.pop(argname)
        except KeyError:
            pass
    # Ignore the stream argument if passed
    log_kwargs.pop("stream", None)

    kwargs, unused_kwargs = _get_create_kwargs(
        skip_translate=skip_translate,
        ignore_collisions=ignore_collisions,
        validate_ip_addrs=validate_ip_addrs,
        **kwargs,
    )

    # _get_create_kwargs() will have processed auto_remove and put it into the
    # host_config, so check the host_config to see whether or not auto_remove
    # was enabled.
    auto_remove = kwargs.get("host_config", {}).get("AutoRemove", False)

    if unused_kwargs:
        log.warning(
            "The following arguments were ignored because they are not "
            "recognized by docker-py: %s",
            sorted(unused_kwargs),
        )

    if networks:
        if isinstance(networks, str):
            networks = {x: {} for x in networks.split(",")}
        if not isinstance(networks, dict) or not all(
            isinstance(x, dict) for x in networks.values()
        ):
            raise SaltInvocationError("Invalid format for networks argument")

    log.debug(
        "docker.create: creating container %susing the following arguments: %s",
        f"with name '{name}' " if name is not None else "",
        kwargs,
    )

    time_started = time.time()
    # Create the container
    ret = _client_wrapper("create_container", image, name=name, **kwargs)

    if removed_ids:
        ret["Replaces"] = removed_ids

    if name is None:
        name = inspect_container(ret["Id"])["Name"].lstrip("/")
    ret["Name"] = name

    def _append_warning(ret, msg):
        warnings = ret.pop("Warnings", None)
        if warnings is None:
            warnings = [msg]
        elif isinstance(ret, list):
            warnings.append(msg)
        else:
            warnings = [warnings, msg]
        ret["Warnings"] = warnings

    exc_info = {"return": ret}
    try:
        if networks:
            try:
                for net_name, net_conf in networks.items():
                    __salt__["docker.connect_container_to_network"](
                        ret["Id"], net_name, **net_conf
                    )
            except CommandExecutionError as exc:
                # Make an effort to remove the container if auto_remove was enabled
                if auto_remove:
                    try:
                        rm_(name)
                    except CommandExecutionError as rm_exc:
                        exc_info.setdefault("other_errors", []).append(
                            f"Failed to auto_remove container: {rm_exc}"
                        )
                # Raise original exception with additional info
                raise CommandExecutionError(str(exc), info=exc_info)

        # Start the container
        output = []
        start_(ret["Id"])
        if not bg:
            # Can't use logs() here because we've disabled "stream" in that
            # function.  Also, note that if you want to troubleshoot this for loop
            # in a debugger like pdb or pudb, you'll want to use auto_remove=False
            # when running the function, since the container will likely exit
            # before you finish stepping through with a debugger. If the container
            # exits during iteration, the next iteration of the generator will
            # raise an exception since the container will no longer exist.
            try:
                for line in _client_wrapper(
                    "logs", ret["Id"], stream=True, timestamps=False
                ):
                    output.append(salt.utils.stringutils.to_unicode(line))
            except CommandExecutionError:
                msg = (
                    "Failed to get logs from container. This may be because "
                    "the container exited before Salt was able to attach to "
                    "it to retrieve the logs. Consider setting auto_remove "
                    "to False."
                )
                _append_warning(ret, msg)
        # Container has exited, note the elapsed time
        ret["Time_Elapsed"] = time.time() - time_started
        _clear_context()

        if not bg:
            ret["Logs"] = "".join(output)
            if not auto_remove:
                try:
                    cinfo = inspect_container(ret["Id"])
                except CommandExecutionError:
                    _append_warning(ret, "Failed to inspect container after running")
                else:
                    cstate = cinfo.get("State", {})
                    cstatus = cstate.get("Status")
                    if cstatus != "exited":
                        _append_warning(ret, "Container state is not 'exited'")
                    ret["ExitCode"] = cstate.get("ExitCode")

    except CommandExecutionError as exc:
        try:
            exc_info.update(exc.info)
        except (TypeError, ValueError):
            # In the event exc.info wasn't a dict (extremely unlikely), append
            # it to other_errors as a fallback.
            exc_info.setdefault("other_errors", []).append(exc.info)
        # Re-raise with all of the available additional info
        raise CommandExecutionError(str(exc), info=exc_info)

    return ret


def copy_from(name, source, dest, overwrite=False, makedirs=False):
    """
    Copy a file from inside a container to the Minion

    name
        Container name

    source
        Path of the file on the container's filesystem

    dest
        Destination on the Minion. Must be an absolute path. If the destination
        is a directory, the file will be copied into that directory.

    overwrite : False
        Unless this option is set to ``True``, then if a file exists at the
        location specified by the ``dest`` argument, an error will be raised.

    makedirs : False
        Create the parent directory on the container if it does not already
        exist.


    **RETURN DATA**

    A boolean (``True`` if successful, otherwise ``False``)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.copy_from mycontainer /var/log/nginx/access.log /home/myuser
    """
    c_state = state(name)
    if c_state != "running":
        raise CommandExecutionError(f"Container '{name}' is not running")

    # Destination file sanity checks
    if not os.path.isabs(dest):
        raise SaltInvocationError("Destination path must be absolute")
    if os.path.isdir(dest):
        # Destination is a directory, full path to dest file will include the
        # basename of the source file.
        dest = os.path.join(dest, os.path.basename(source))
        dest_dir = dest
    else:
        # Destination was not a directory. We will check to see if the parent
        # dir is a directory, and then (if makedirs=True) attempt to create the
        # parent directory.
        dest_dir = os.path.split(dest)[0]
        if not os.path.isdir(dest_dir):
            if makedirs:
                try:
                    os.makedirs(dest_dir)
                except OSError as exc:
                    raise CommandExecutionError(
                        "Unable to make destination directory {}: {}".format(
                            dest_dir, exc
                        )
                    )
            else:
                raise SaltInvocationError(f"Directory {dest_dir} does not exist")
    if not overwrite and os.path.exists(dest):
        raise CommandExecutionError(
            "Destination path {} already exists. Use overwrite=True to "
            "overwrite it".format(dest)
        )

    # Source file sanity checks
    if not os.path.isabs(source):
        raise SaltInvocationError("Source path must be absolute")
    else:
        if retcode(name, f"test -e {shlex.quote(source)}", ignore_retcode=True) == 0:
            if (
                retcode(name, f"test -f {shlex.quote(source)}", ignore_retcode=True)
                != 0
            ):
                raise SaltInvocationError("Source must be a regular file")
        else:
            raise SaltInvocationError(f"Source file {source} does not exist")

    # Before we try to replace the file, compare checksums.
    source_sha256 = _get_sha256(name, source)
    if source_sha256 == __salt__["file.get_sum"](dest, "sha256"):
        log.debug("%s:%s and %s are the same file, skipping copy", name, source, dest)
        return True

    log.debug("Copying %s from container '%s' to local path %s", source, name, dest)

    try:
        src_path = ":".join((name, source))
    except TypeError:
        src_path = f"{name}:{source}"
    cmd = ["docker", "cp", src_path, dest_dir]
    __salt__["cmd.run"](cmd, python_shell=False)
    return source_sha256 == __salt__["file.get_sum"](dest, "sha256")


# Docker cp gets a file from the container, alias this to copy_from
cp = salt.utils.functools.alias_function(copy_from, "cp")


def copy_to(name, source, dest, exec_driver=None, overwrite=False, makedirs=False):
    """
    Copy a file from the host into a container

    name
        Container name

    source
        File to be copied to the container. Can be a local path on the Minion
        or a remote file from the Salt fileserver.

    dest
        Destination on the container. Must be an absolute path. If the
        destination is a directory, the file will be copied into that
        directory.

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

    overwrite : False
        Unless this option is set to ``True``, then if a file exists at the
        location specified by the ``dest`` argument, an error will be raised.

    makedirs : False
        Create the parent directory on the container if it does not already
        exist.


    **RETURN DATA**

    A boolean (``True`` if successful, otherwise ``False``)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.copy_to mycontainer /tmp/foo /root/foo
    """
    if exec_driver is None:
        exec_driver = _get_exec_driver()
    return __salt__["container_resource.copy_to"](
        name,
        __salt__["container_resource.cache_file"](source),
        dest,
        container_type=__virtualname__,
        exec_driver=exec_driver,
        overwrite=overwrite,
        makedirs=makedirs,
    )


def export(name, path, overwrite=False, makedirs=False, compression=None, **kwargs):
    """
    Exports a container to a tar archive. It can also optionally compress that
    tar archive, and push it up to the Master.

    name
        Container name or ID

    path
        Absolute path on the Minion where the container will be exported

    overwrite : False
        Unless this option is set to ``True``, then if a file exists at the
        location specified by the ``path`` argument, an error will be raised.

    makedirs : False
        If ``True``, then if the parent directory of the file specified by the
        ``path`` argument does not exist, Salt will attempt to create it.

    compression : None
        Can be set to any of the following:

        - ``gzip`` or ``gz`` for gzip compression
        - ``bzip2`` or ``bz2`` for bzip2 compression
        - ``xz`` or ``lzma`` for XZ compression (requires `xz-utils`_, as well
          as the ``lzma`` module from Python 3.3, available in Python 2 and
          Python 3.0-3.2 as `backports.lzma`_)

        This parameter can be omitted and Salt will attempt to determine the
        compression type by examining the filename passed in the ``path``
        parameter.

        .. _`xz-utils`: http://tukaani.org/xz/
        .. _`backports.lzma`: https://pypi.python.org/pypi/backports.lzma

    push : False
        If ``True``, the container will be pushed to the master using
        :py:func:`cp.push <salt.modules.cp.push>`.

        .. note::

            This requires :conf_master:`file_recv` to be set to ``True`` on the
            Master.


    **RETURN DATA**

    A dictionary will containing the following keys:

    - ``Path`` - Path of the file that was exported
    - ``Push`` - Reports whether or not the file was successfully pushed to the
      Master

      *(Only present if push=True)*
    - ``Size`` - Size of the file, in bytes
    - ``Size_Human`` - Size of the file, in human-readable units
    - ``Time_Elapsed`` - Time in seconds taken to perform the export

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.export mycontainer /tmp/mycontainer.tar
        salt myminion docker.export mycontainer /tmp/mycontainer.tar.xz push=True
    """
    err = f"Path '{path}' is not absolute"
    try:
        if not os.path.isabs(path):
            raise SaltInvocationError(err)
    except AttributeError:
        raise SaltInvocationError(err)

    if os.path.exists(path) and not overwrite:
        raise CommandExecutionError(f"{path} already exists")

    if compression is None:
        if path.endswith(".tar.gz") or path.endswith(".tgz"):
            compression = "gzip"
        elif path.endswith(".tar.bz2") or path.endswith(".tbz2"):
            compression = "bzip2"
        elif path.endswith(".tar.xz") or path.endswith(".txz"):
            if HAS_LZMA:
                compression = "xz"
            else:
                raise CommandExecutionError(
                    "XZ compression unavailable. Install the backports.lzma "
                    "module and xz-utils to enable XZ compression."
                )
    elif compression == "gz":
        compression = "gzip"
    elif compression == "bz2":
        compression = "bzip2"
    elif compression == "lzma":
        compression = "xz"

    if compression and compression not in ("gzip", "bzip2", "xz"):
        raise SaltInvocationError(f"Invalid compression type '{compression}'")

    parent_dir = os.path.dirname(path)
    if not os.path.isdir(parent_dir):
        if not makedirs:
            raise CommandExecutionError(
                "Parent dir {} of destination path does not exist. Use "
                "makedirs=True to create it.".format(parent_dir)
            )
        try:
            os.makedirs(parent_dir)
        except OSError as exc:
            raise CommandExecutionError(
                f"Unable to make parent dir {parent_dir}: {exc}"
            )

    if compression == "gzip":
        try:
            out = gzip.open(path, "wb")
        except OSError as exc:
            raise CommandExecutionError(f"Unable to open {path} for writing: {exc}")
    elif compression == "bzip2":
        compressor = bz2.BZ2Compressor()
    elif compression == "xz":
        compressor = lzma.LZMACompressor()

    time_started = time.time()
    try:
        if compression != "gzip":
            # gzip doesn't use a Compressor object, it uses a .open() method to
            # open the filehandle. If not using gzip, we need to open the
            # filehandle here. We make sure to close it in the "finally" block
            # below.
            out = __utils__["files.fopen"](
                path, "wb"
            )  # pylint: disable=resource-leakage
        response = _client_wrapper("export", name)
        buf = None
        while buf != "":
            buf = response.read(4096)
            if buf:
                if compression in ("bzip2", "xz"):
                    data = compressor.compress(buf)
                    if data:
                        out.write(data)
                else:
                    out.write(buf)
        if compression in ("bzip2", "xz"):
            # Flush any remaining data out of the compressor
            data = compressor.flush()
            if data:
                out.write(data)
        out.flush()
    except Exception as exc:  # pylint: disable=broad-except
        try:
            os.remove(path)
        except OSError:
            pass
        raise CommandExecutionError(f"Error occurred during container export: {exc}")
    finally:
        out.close()
    ret = {"Time_Elapsed": time.time() - time_started}

    ret["Path"] = path
    ret["Size"] = os.stat(path).st_size
    ret["Size_Human"] = _size_fmt(ret["Size"])

    # Process push
    if kwargs.get(push, False):
        ret["Push"] = __salt__["cp.push"](path)

    return ret


@_refresh_mine_cache
def rm_(name, force=False, volumes=False, **kwargs):
    """
    Removes a container

    name
        Container name or ID

    force : False
        If ``True``, the container will be killed first before removal, as the
        Docker API will not permit a running container to be removed. This
        option is set to ``False`` by default to prevent accidental removal of
        a running container.

    stop : False
        If ``True``, the container will be stopped first before removal, as the
        Docker API will not permit a running container to be removed. This
        option is set to ``False`` by default to prevent accidental removal of
        a running container.

        .. versionadded:: 2017.7.0

    timeout
        Optional timeout to be passed to :py:func:`docker.stop
        <salt.modules.dockermod.stop>` if stopping the container.

        .. versionadded:: 2018.3.0

    volumes : False
        Also remove volumes associated with container


    **RETURN DATA**

    A list of the IDs of containers which were removed

    CLI Example:

    .. code-block:: bash

        salt myminion docker.rm mycontainer
        salt myminion docker.rm mycontainer force=True
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)
    stop_ = kwargs.pop("stop", False)
    timeout = kwargs.pop("timeout", None)
    auto_remove = False
    if kwargs:
        __utils__["args.invalid_kwargs"](kwargs)

    if state(name) == "running" and not (force or stop_):
        raise CommandExecutionError(
            "Container '{}' is running, use force=True to forcibly "
            "remove this container".format(name)
        )
    if stop_ and not force:
        inspect_results = inspect_container(name)
        try:
            auto_remove = inspect_results["HostConfig"]["AutoRemove"]
        except KeyError:
            log.error(
                "Failed to find AutoRemove in inspect results, Docker API may "
                "have changed. Full results: %s",
                inspect_results,
            )
        stop(name, timeout=timeout)
    pre = ps_(all=True)

    if not auto_remove:
        _client_wrapper("remove_container", name, v=volumes, force=force)
    _clear_context()
    return [x for x in pre if x not in ps_(all=True)]


def rename(name, new_name):
    """
    .. versionadded:: 2017.7.0

    Renames a container. Returns ``True`` if successful, and raises an error if
    the API returns one. If unsuccessful and the API returns no error (should
    not happen), then ``False`` will be returned.

    name
        Name or ID of existing container

    new_name
        New name to assign to container

    CLI Example:

    .. code-block:: bash

        salt myminion docker.rename foo bar
    """
    id_ = inspect_container(name)["Id"]
    log.debug("Renaming container '%s' (ID: %s) to '%s'", name, id_, new_name)
    _client_wrapper("rename", id_, new_name)
    # Confirm that the ID of the container corresponding to the new name is the
    # same as it was before.
    return inspect_container(new_name)["Id"] == id_


# Functions to manage images
def build(
    path=None,
    repository=None,
    tag=None,
    cache=True,
    rm=True,
    api_response=False,
    fileobj=None,
    dockerfile=None,
    buildargs=None,
):
    """
    .. versionchanged:: 2018.3.0
        If the built image should be tagged, then the repository and tag must
        now be passed separately using the ``repository`` and ``tag``
        arguments, rather than together in the (now deprecated) ``image``
        argument.

    Builds a docker image from a Dockerfile or a URL

    path
        Path to directory on the Minion containing a Dockerfile

    repository
        Optional repository name for the image being built

        .. versionadded:: 2018.3.0

    tag : latest
        Tag name for the image (required if ``repository`` is passed)

        .. versionadded:: 2018.3.0

    image
        .. deprecated:: 2018.3.0
            Use both ``repository`` and ``tag`` instead

    cache : True
        Set to ``False`` to force the build process not to use the Docker image
        cache, and pull all required intermediate image layers

    rm : True
        Remove intermediate containers created during build

    api_response : False
        If ``True``: an ``API_Response`` key will be present in the return
        data, containing the raw output from the Docker API.

    fileobj
        Allows for a file-like object containing the contents of the Dockerfile
        to be passed in place of a file ``path`` argument. This argument should
        not be used from the CLI, only from other Salt code.

    dockerfile
        Allows for an alternative Dockerfile to be specified. Path to
        alternative Dockefile is relative to the build path for the Docker
        container.

        .. versionadded:: 2016.11.0

    buildargs
        A dictionary of build arguments provided to the docker build process.


    **RETURN DATA**

    A dictionary containing one or more of the following keys:

    - ``Id`` - ID of the newly-built image
    - ``Time_Elapsed`` - Time in seconds taken to perform the build
    - ``Intermediate_Containers`` - IDs of containers created during the course
      of the build process

      *(Only present if rm=False)*
    - ``Images`` - A dictionary containing one or more of the following keys:
        - ``Already_Pulled`` - Layers that that were already present on the
          Minion
        - ``Pulled`` - Layers that that were pulled

      *(Only present if the image specified by the "repository" and "tag"
      arguments was not present on the Minion, or if cache=False)*
    - ``Status`` - A string containing a summary of the pull action (usually a
      message saying that an image was downloaded, or that it was up to date).

      *(Only present if the image specified by the "repository" and "tag"
      arguments was not present on the Minion, or if cache=False)*

    CLI Example:

    .. code-block:: bash

        salt myminion docker.build /path/to/docker/build/dir
        salt myminion docker.build https://github.com/myuser/myrepo.git repository=myimage tag=latest
        salt myminion docker.build /path/to/docker/build/dir dockerfile=Dockefile.different repository=myimage tag=dev
    """
    _prep_pull()

    if repository or tag:
        if not repository and tag:
            # Have to have both or neither
            raise SaltInvocationError(
                "If tagging, both a repository and tag are required"
            )
        else:
            if not isinstance(repository, str):
                repository = str(repository)
            if not isinstance(tag, str):
                tag = str(tag)

    # For the build function in the low-level API, the "tag" refers to the full
    # tag (e.g. myuser/myimage:mytag). This is different than in other
    # functions, where the repo and tag are passed separately.
    image_tag = f"{repository}:{tag}" if repository and tag else None

    time_started = time.time()
    response = _client_wrapper(
        "build",
        path=path,
        tag=image_tag,
        quiet=False,
        fileobj=fileobj,
        rm=rm,
        nocache=not cache,
        dockerfile=dockerfile,
        buildargs=buildargs,
    )
    ret = {"Time_Elapsed": time.time() - time_started}
    _clear_context()

    if not response:
        raise CommandExecutionError(
            f"Build failed for {path}, no response returned from Docker API"
        )

    stream_data = []
    for line in response:
        stream_data.extend(salt.utils.json.loads(line, cls=DockerJSONDecoder))
    errors = []
    # Iterate through API response and collect information
    for item in stream_data:
        try:
            item_type = next(iter(item))
        except StopIteration:
            continue
        if item_type == "status":
            _pull_status(ret, item)
        if item_type == "stream":
            _build_status(ret, item)
        elif item_type == "errorDetail":
            _error_detail(errors, item)

    if "Id" not in ret:
        # API returned information, but there was no confirmation of a
        # successful build.
        msg = f"Build failed for {path}"
        log.error(msg)
        log.error(stream_data)
        if errors:
            msg += ". Error(s) follow:\n\n{}".format("\n\n".join(errors))
        raise CommandExecutionError(msg)

    resolved_tag = resolve_tag(ret["Id"], all=True)
    if resolved_tag:
        ret["Image"] = resolved_tag
    else:
        ret["Warning"] = f"Failed to tag image as {image_tag}"

    if api_response:
        ret["API_Response"] = stream_data

    if rm:
        ret.pop("Intermediate_Containers", None)
    return ret


def commit(name, repository, tag="latest", message=None, author=None):
    """
    .. versionchanged:: 2018.3.0
        The repository and tag must now be passed separately using the
        ``repository`` and ``tag`` arguments, rather than together in the (now
        deprecated) ``image`` argument.

    Commits a container, thereby promoting it to an image. Equivalent to
    running the ``docker commit`` Docker CLI command.

    name
        Container name or ID to commit

    repository
        Repository name for the image being committed

        .. versionadded:: 2018.3.0

    tag : latest
        Tag name for the image

        .. versionadded:: 2018.3.0

    image
        .. deprecated:: 2018.3.0
            Use both ``repository`` and ``tag`` instead

    message
        Commit message (Optional)

    author
        Author name (Optional)


    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Id`` - ID of the newly-created image
    - ``Image`` - Name of the newly-created image
    - ``Time_Elapsed`` - Time in seconds taken to perform the commit

    CLI Example:

    .. code-block:: bash

        salt myminion docker.commit mycontainer myuser/myimage mytag
    """
    if not isinstance(repository, str):
        repository = str(repository)
    if not isinstance(tag, str):
        tag = str(tag)

    time_started = time.time()
    response = _client_wrapper(
        "commit", name, repository=repository, tag=tag, message=message, author=author
    )
    ret = {"Time_Elapsed": time.time() - time_started}
    _clear_context()

    image_id = None
    for id_ in ("Id", "id", "ID"):
        if id_ in response:
            image_id = response[id_]
            break

    if image_id is None:
        raise CommandExecutionError("No image ID was returned in API response")

    ret["Id"] = image_id
    return ret


def dangling(prune=False, force=False):
    """
    Return top-level images (those on which no other images depend) which do
    not have a tag assigned to them. These include:

    - Images which were once tagged but were later untagged, such as those
      which were superseded by committing a new copy of an existing tagged
      image.
    - Images which were loaded using :py:func:`docker.load
      <salt.modules.dockermod.load>` (or the ``docker load`` Docker CLI
      command), but not tagged.

    prune : False
        Remove these images

    force : False
        If ``True``, and if ``prune=True``, then forcibly remove these images.

    **RETURN DATA**

    If ``prune=False``, the return data will be a list of dangling image IDs.

    If ``prune=True``, the return data will be a dictionary with each key being
    the ID of the dangling image, and the following information for each image:

    - ``Comment`` - Any error encountered when trying to prune a dangling image

      *(Only present if prune failed)*
    - ``Removed`` - A boolean (``True`` if prune was successful, ``False`` if
      not)

    CLI Example:

    .. code-block:: bash

        salt myminion docker.dangling
        salt myminion docker.dangling prune=True
    """
    all_images = images(all=True)
    dangling_images = [
        x[:12]
        for x in _get_top_level_images(all_images)
        if all_images[x]["RepoTags"] is None
    ]
    if not prune:
        return dangling_images

    ret = {}
    for image in dangling_images:
        try:
            ret.setdefault(image, {})["Removed"] = rmi(image, force=force)
        except Exception as exc:  # pylint: disable=broad-except
            err = str(exc)
            log.error(err)
            ret.setdefault(image, {})["Comment"] = err
            ret[image]["Removed"] = False
    return ret


def import_(source, repository, tag="latest", api_response=False):
    """
    .. versionchanged:: 2018.3.0
        The repository and tag must now be passed separately using the
        ``repository`` and ``tag`` arguments, rather than together in the (now
        deprecated) ``image`` argument.

    Imports content from a local tarball or a URL as a new docker image

    source
        Content to import (URL or absolute path to a tarball).  URL can be a
        file on the Salt fileserver (i.e.
        ``salt://path/to/rootfs/tarball.tar.xz``. To import a file from a
        saltenv other than ``base`` (e.g. ``dev``), pass it at the end of the
        URL (ex. ``salt://path/to/rootfs/tarball.tar.xz?saltenv=dev``).

    repository
        Repository name for the image being imported

        .. versionadded:: 2018.3.0

    tag : latest
        Tag name for the image

        .. versionadded:: 2018.3.0

    image
        .. deprecated:: 2018.3.0
            Use both ``repository`` and ``tag`` instead

    api_response : False
        If ``True`` an ``api_response`` key will be present in the return data,
        containing the raw output from the Docker API.


    **RETURN DATA**

    A dictionary containing the following keys:

    - ``Id`` - ID of the newly-created image
    - ``Image`` - Name of the newly-created image
    - ``Time_Elapsed`` - Time in seconds taken to perform the commit

    CLI Example:

    .. code-block:: bash

        salt myminion docker.import /tmp/cent7-minimal.tar.xz myuser/centos
        salt myminion docker.import /tmp/cent7-minimal.tar.xz myuser/centos:7
        salt myminion docker.import salt://dockerimages/cent7-minimal.tar.xz myuser/centos:7
    """
    if not isinstance(repository, str):
        repository = str(repository)
    if not isinstance(tag, str):
        tag = str(tag)

    path = __salt__["container_resource.cache_file"](source)

    time_started = time.time()
    response = _client_wrapper("import_image", path, repository=repository, tag=tag)
    ret = {"Time_Elapsed": time.time() - time_started}
    _clear_context()

    if not response:
        raise CommandExecutionError(
            f"Import failed for {source}, no response returned from Docker API"
        )
    elif api_response:
        ret["API_Response"] = response

    errors = []
    # Iterate through API response and collect information
    for item in response:
        try:
            item_type = next(iter(item))
        except StopIteration:
            continue
        if item_type == "status":
            _import_status(ret, item, repository, tag)
        elif item_type == "errorDetail":
            _error_detail(errors, item)

    if "Id" not in ret:
        # API returned information, but there was no confirmation of a
        # successful push.
        msg = f"Import failed for {source}"
        if errors:
            msg += ". Error(s) follow:\n\n{}".format("\n\n".join(errors))
        raise CommandExecutionError(msg)

    return ret


def load(path, repository=None, tag=None):
    """
    .. versionchanged:: 2018.3.0
        If the loaded image should be tagged, then the repository and tag must
        now be passed separately using the ``repository`` and ``tag``
        arguments, rather than together in the (now deprecated) ``image``
        argument.

    Load a tar archive that was created using :py:func:`docker.save
    <salt.modules.dockermod.save>` (or via the Docker CLI using ``docker save``).

    path
        Path to docker tar archive. Path can be a file on the Minion, or the
        URL of a file on the Salt fileserver (i.e.
        ``salt://path/to/docker/saved/image.tar``). To load a file from a
        saltenv other than ``base`` (e.g. ``dev``), pass it at the end of the
        URL (ex. ``salt://path/to/rootfs/tarball.tar.xz?saltenv=dev``).

    repository
        If specified, the topmost layer of the newly-loaded image will be
        tagged with the specified repo using :py:func:`docker.tag
        <salt.modules.dockermod.tag_>`. If a repository name is provided, then
        the ``tag`` argument is also required.

        .. versionadded:: 2018.3.0

    tag
        Tag name to go along with the repository name, if the loaded image is
        to be tagged.

        .. versionadded:: 2018.3.0

    image
        .. deprecated:: 2018.3.0
            Use both ``repository`` and ``tag`` instead


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``Path`` - Path of the file that was saved
    - ``Layers`` - A list containing the IDs of the layers which were loaded.
      Any layers in the file that was loaded, which were already present on the
      Minion, will not be included.
    - ``Image`` - Name of tag applied to topmost layer

      *(Only present if tag was specified and tagging was successful)*
    - ``Time_Elapsed`` - Time in seconds taken to load the file
    - ``Warning`` - Message describing any problems encountered in attempt to
      tag the topmost layer

      *(Only present if tag was specified and tagging failed)*

    CLI Example:

    .. code-block:: bash

        salt myminion docker.load /path/to/image.tar
        salt myminion docker.load salt://path/to/docker/saved/image.tar repository=myuser/myimage tag=mytag
    """
    if (repository or tag) and not (repository and tag):
        # Have to have both or neither
        raise SaltInvocationError("If tagging, both a repository and tag are required")

    local_path = __salt__["container_resource.cache_file"](path)
    if not os.path.isfile(local_path):
        raise CommandExecutionError(f"Source file {path} does not exist")

    pre = images(all=True)
    cmd = ["docker", "load", "-i", local_path]
    time_started = time.time()
    result = __salt__["cmd.run_all"](cmd)
    ret = {"Time_Elapsed": time.time() - time_started}
    _clear_context()
    post = images(all=True)
    if result["retcode"] != 0:
        msg = f"Failed to load image(s) from {path}"
        if result["stderr"]:
            msg += ": {}".format(result["stderr"])
        raise CommandExecutionError(msg)
    ret["Path"] = path

    new_layers = [x for x in post if x not in pre]
    ret["Layers"] = [x[:12] for x in new_layers]
    top_level_images = _get_top_level_images(post, subset=new_layers)
    if repository or tag:
        if len(top_level_images) > 1:
            ret["Warning"] = (
                "More than one top-level image layer was loaded ({}), no "
                "image was tagged".format(", ".join(top_level_images))
            )
        else:
            # Normally just joining the two would be quicker than a str.format,
            # but since we can't be positive the repo and tag will both be
            # strings when passed (e.g. a numeric tag would be loaded as an int
            # or float), and because the tag_ function will stringify them if
            # need be, a str.format is the correct thing to do here.
            tagged_image = f"{repository}:{tag}"
            try:
                result = tag_(top_level_images[0], repository=repository, tag=tag)
                ret["Image"] = tagged_image
            except IndexError:
                ret["Warning"] = (
                    "No top-level image layers were loaded, no image was tagged"
                )
            except Exception as exc:  # pylint: disable=broad-except
                ret["Warning"] = "Failed to tag {} as {}: {}".format(
                    top_level_images[0], tagged_image, exc
                )
    return ret


def layers(name):
    """
    Returns a list of the IDs of layers belonging to the specified image, with
    the top-most layer (the one correspnding to the passed name) appearing
    last.

    name
        Image name or ID

    CLI Example:

    .. code-block:: bash

        salt myminion docker.layers centos:7
    """
    ret = []
    cmd = ["docker", "history", "-q", name]
    for line in reversed(
        __salt__["cmd.run_stdout"](cmd, python_shell=False).splitlines()
    ):
        ret.append(line)
    if not ret:
        raise CommandExecutionError(f"Image '{name}' not found")
    return ret


def pull(
    image,
    insecure_registry=False,
    api_response=False,
    client_timeout=salt.utils.dockermod.CLIENT_TIMEOUT,
):
    """
    .. versionchanged:: 2018.3.0
        If no tag is specified in the ``image`` argument, all tags for the
        image will be pulled. For this reason is it recommended to pass
        ``image`` using the ``repo:tag`` notation.

    Pulls an image from a Docker registry

    image
        Image to be pulled

    insecure_registry : False
        If ``True``, the Docker client will permit the use of insecure
        (non-HTTPS) registries.

    api_response : False
        If ``True``, an ``API_Response`` key will be present in the return
        data, containing the raw output from the Docker API.

        .. note::

            This may result in a **lot** of additional return data, especially
            for larger images.

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``Layers`` - A dictionary containing one or more of the following keys:
        - ``Already_Pulled`` - Layers that that were already present on the
          Minion
        - ``Pulled`` - Layers that that were pulled
    - ``Status`` - A string containing a summary of the pull action (usually a
      message saying that an image was downloaded, or that it was up to date).
    - ``Time_Elapsed`` - Time in seconds taken to perform the pull

    CLI Example:

    .. code-block:: bash

        salt myminion docker.pull centos
        salt myminion docker.pull centos:6
    """
    _prep_pull()

    kwargs = {"stream": True, "client_timeout": client_timeout}
    if insecure_registry:
        kwargs["insecure_registry"] = insecure_registry

    time_started = time.time()
    response = _client_wrapper("pull", image, **kwargs)
    ret = {"Time_Elapsed": time.time() - time_started, "retcode": 0}
    _clear_context()

    if not response:
        raise CommandExecutionError(
            f"Pull failed for {image}, no response returned from Docker API"
        )
    elif api_response:
        ret["API_Response"] = response

    errors = []
    # Iterate through API response and collect information
    for event in response:
        log.debug("pull event: %s", event)
        try:
            event = salt.utils.json.loads(event)
        except Exception as exc:  # pylint: disable=broad-except
            raise CommandExecutionError(
                f"Unable to interpret API event: '{event}'",
                info={"Error": str(exc)},
            )
        try:
            event_type = next(iter(event))
        except StopIteration:
            continue
        if event_type == "status":
            _pull_status(ret, event)
        elif event_type == "errorDetail":
            _error_detail(errors, event)

    if errors:
        ret["Errors"] = errors
        ret["retcode"] = 1
    return ret


def push(
    image,
    insecure_registry=False,
    api_response=False,
    client_timeout=salt.utils.dockermod.CLIENT_TIMEOUT,
):
    """
    .. versionchanged:: 2015.8.4
        The ``Id`` and ``Image`` keys are no longer present in the return data.
        This is due to changes in the Docker Remote API.

    Pushes an image to a Docker registry. See the documentation at top of this
    page to configure authentication credentials.

    image
        Image to be pushed. If just the repository name is passed, then all
        tagged images for the specified repo will be pushed. If the image name
        is passed in ``repo:tag`` notation, only the specified image will be
        pushed.

    insecure_registry : False
        If ``True``, the Docker client will permit the use of insecure
        (non-HTTPS) registries.

    api_response : False
        If ``True``, an ``API_Response`` key will be present in the return
        data, containing the raw output from the Docker API.

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``Layers`` - A dictionary containing one or more of the following keys:
        - ``Already_Pushed`` - Layers that that were already present on the
          Minion
        - ``Pushed`` - Layers that that were pushed
    - ``Time_Elapsed`` - Time in seconds taken to perform the push

    CLI Example:

    .. code-block:: bash

        salt myminion docker.push myuser/mycontainer
        salt myminion docker.push myuser/mycontainer:mytag
    """
    if not isinstance(image, str):
        image = str(image)

    kwargs = {"stream": True, "client_timeout": client_timeout}
    if insecure_registry:
        kwargs["insecure_registry"] = insecure_registry

    time_started = time.time()
    response = _client_wrapper("push", image, **kwargs)
    ret = {"Time_Elapsed": time.time() - time_started, "retcode": 0}
    _clear_context()

    if not response:
        raise CommandExecutionError(
            f"Push failed for {image}, no response returned from Docker API"
        )
    elif api_response:
        ret["API_Response"] = response

    errors = []
    # Iterate through API response and collect information
    for event in response:
        try:
            event = salt.utils.json.loads(event)
        except Exception as exc:  # pylint: disable=broad-except
            raise CommandExecutionError(
                f"Unable to interpret API event: '{event}'",
                info={"Error": str(exc)},
            )
        try:
            event_type = next(iter(event))
        except StopIteration:
            continue
        if event_type == "status":
            _push_status(ret, event)
        elif event_type == "errorDetail":
            _error_detail(errors, event)

    if errors:
        ret["Errors"] = errors
        ret["retcode"] = 1
    return ret


def rmi(*names, **kwargs):
    """
    Removes an image

    name
        Name (in ``repo:tag`` notation) or ID of image.

    force : False
        If ``True``, the image will be removed even if the Minion has
        containers created from that image

    prune : True
        If ``True``, untagged parent image layers will be removed as well, set
        this to ``False`` to keep them.


    **RETURN DATA**

    A dictionary will be returned, containing the following two keys:

    - ``Layers`` - A list of the IDs of image layers that were removed
    - ``Tags`` - A list of the tags that were removed
    - ``Errors`` - A list of any errors that were encountered

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.rmi busybox
        salt myminion docker.rmi busybox force=True
        salt myminion docker.rmi foo bar baz
    """
    pre_images = images(all=True)
    pre_tags = list_tags()
    force = kwargs.get("force", False)
    noprune = not kwargs.get("prune", True)

    errors = []
    for name in names:
        image_id = inspect_image(name)["Id"]
        try:
            _client_wrapper(
                "remove_image",
                image_id,
                force=force,
                noprune=noprune,
                catch_api_errors=False,
            )
        except docker.errors.APIError as exc:
            if exc.response.status_code == 409:
                errors.append(exc.explanation)
                deps = depends(name)
                if deps["Containers"] or deps["Images"]:
                    err = "Image is in use by "
                    if deps["Containers"]:
                        err += "container(s): {}".format(", ".join(deps["Containers"]))
                    if deps["Images"]:
                        if deps["Containers"]:
                            err += " and "
                        err += "image(s): {}".format(", ".join(deps["Images"]))
                    errors.append(err)
            else:
                errors.append(f"Error {exc.response.status_code}: {exc.explanation}")

    _clear_context()
    ret = {
        "Layers": [x for x in pre_images if x not in images(all=True)],
        "Tags": [x for x in pre_tags if x not in list_tags()],
        "retcode": 0,
    }
    if errors:
        ret["Errors"] = errors
        ret["retcode"] = 1
    return ret


def save(name, path, overwrite=False, makedirs=False, compression=None, **kwargs):
    """
    Saves an image and to a file on the minion. Equivalent to running the
    ``docker save`` Docker CLI command, but unlike ``docker save`` this will
    also work on named images instead of just images IDs.

    name
        Name or ID of image. Specify a specific tag by using the ``repo:tag``
        notation.

    path
        Absolute path on the Minion where the image will be exported

    overwrite : False
        Unless this option is set to ``True``, then if the destination file
        exists an error will be raised.

    makedirs : False
        If ``True``, then if the parent directory of the file specified by the
        ``path`` argument does not exist, Salt will attempt to create it.

    compression : None
        Can be set to any of the following:

        - ``gzip`` or ``gz`` for gzip compression
        - ``bzip2`` or ``bz2`` for bzip2 compression
        - ``xz`` or ``lzma`` for XZ compression (requires `xz-utils`_, as well
          as the ``lzma`` module from Python 3.3, available in Python 2 and
          Python 3.0-3.2 as `backports.lzma`_)

        This parameter can be omitted and Salt will attempt to determine the
        compression type by examining the filename passed in the ``path``
        parameter.

        .. note::
            Since the Docker API does not support ``docker save``, compression
            will be a bit slower with this function than with
            :py:func:`docker.export <salt.modules.dockermod.export>` since the
            image(s) will first be saved and then the compression done
            afterwards.

        .. _`xz-utils`: http://tukaani.org/xz/
        .. _`backports.lzma`: https://pypi.python.org/pypi/backports.lzma

    push : False
        If ``True``, the container will be pushed to the master using
        :py:func:`cp.push <salt.modules.cp.push>`.

        .. note::

            This requires :conf_master:`file_recv` to be set to ``True`` on the
            Master.


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``Path`` - Path of the file that was saved
    - ``Push`` - Reports whether or not the file was successfully pushed to the
      Master

      *(Only present if push=True)*
    - ``Size`` - Size of the file, in bytes
    - ``Size_Human`` - Size of the file, in human-readable units
    - ``Time_Elapsed`` - Time in seconds taken to perform the save

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.save centos:7 /tmp/cent7.tar
        salt myminion docker.save 0123456789ab cdef01234567 /tmp/saved.tar
    """
    err = f"Path '{path}' is not absolute"
    try:
        if not os.path.isabs(path):
            raise SaltInvocationError(err)
    except AttributeError:
        raise SaltInvocationError(err)

    if os.path.exists(path) and not overwrite:
        raise CommandExecutionError(f"{path} already exists")

    if compression is None:
        if path.endswith(".tar.gz") or path.endswith(".tgz"):
            compression = "gzip"
        elif path.endswith(".tar.bz2") or path.endswith(".tbz2"):
            compression = "bzip2"
        elif path.endswith(".tar.xz") or path.endswith(".txz"):
            if HAS_LZMA:
                compression = "xz"
            else:
                raise CommandExecutionError(
                    "XZ compression unavailable. Install the backports.lzma "
                    "module and xz-utils to enable XZ compression."
                )
    elif compression == "gz":
        compression = "gzip"
    elif compression == "bz2":
        compression = "bzip2"
    elif compression == "lzma":
        compression = "xz"

    if compression and compression not in ("gzip", "bzip2", "xz"):
        raise SaltInvocationError(f"Invalid compression type '{compression}'")

    parent_dir = os.path.dirname(path)
    if not os.path.isdir(parent_dir):
        if not makedirs:
            raise CommandExecutionError(
                "Parent dir '{}' of destination path does not exist. Use "
                "makedirs=True to create it.".format(parent_dir)
            )

    if compression:
        saved_path = __utils__["files.mkstemp"]()
    else:
        saved_path = path
    # use the image name if its valid if not use the image id
    image_to_save = (
        name if name in inspect_image(name)["RepoTags"] else inspect_image(name)["Id"]
    )
    cmd = ["docker", "save", "-o", saved_path, image_to_save]
    time_started = time.time()
    result = __salt__["cmd.run_all"](cmd, python_shell=False)
    if result["retcode"] != 0:
        err = f"Failed to save image(s) to {path}"
        if result["stderr"]:
            err += ": {}".format(result["stderr"])
        raise CommandExecutionError(err)

    if compression:
        if compression == "gzip":
            try:
                out = gzip.open(path, "wb")
            except OSError as exc:
                raise CommandExecutionError(f"Unable to open {path} for writing: {exc}")
        elif compression == "bzip2":
            compressor = bz2.BZ2Compressor()
        elif compression == "xz":
            compressor = lzma.LZMACompressor()

        try:
            with __utils__["files.fopen"](saved_path, "rb") as uncompressed:
                # No need to decode on read and encode on on write, since we're
                # reading and immediately writing out bytes.
                if compression != "gzip":
                    # gzip doesn't use a Compressor object, it uses a .open()
                    # method to open the filehandle. If not using gzip, we need
                    # to open the filehandle here.
                    out = __utils__["files.fopen"](path, "wb")
                buf = None
                while buf != "":
                    buf = uncompressed.read(4096)
                    if buf:
                        if compression in ("bzip2", "xz"):
                            data = compressor.compress(buf)
                            if data:
                                out.write(data)
                        else:
                            out.write(buf)
                if compression in ("bzip2", "xz"):
                    # Flush any remaining data out of the compressor
                    data = compressor.flush()
                    if data:
                        out.write(data)
                out.flush()
        except Exception as exc:  # pylint: disable=broad-except
            try:
                os.remove(path)
            except OSError:
                pass
            raise CommandExecutionError(f"Error occurred during image save: {exc}")
        finally:
            try:
                # Clean up temp file
                os.remove(saved_path)
            except OSError:
                pass
            out.close()
    ret = {"Time_Elapsed": time.time() - time_started}

    ret["Path"] = path
    ret["Size"] = os.stat(path).st_size
    ret["Size_Human"] = _size_fmt(ret["Size"])

    # Process push
    if kwargs.get("push", False):
        ret["Push"] = __salt__["cp.push"](path)

    return ret


def tag_(name, repository, tag="latest", force=False):
    """
    .. versionchanged:: 2018.3.0
        The repository and tag must now be passed separately using the
        ``repository`` and ``tag`` arguments, rather than together in the (now
        deprecated) ``image`` argument.

    Tag an image into a repository and return ``True``. If the tag was
    unsuccessful, an error will be raised.

    name
        ID of image

    repository
        Repository name for the image to be built

        .. versionadded:: 2018.3.0

    tag : latest
        Tag name for the image to be built

        .. versionadded:: 2018.3.0

    image
        .. deprecated:: 2018.3.0
            Use both ``repository`` and ``tag`` instead

    force : False
        Force apply tag

    CLI Example:

    .. code-block:: bash

        salt myminion docker.tag 0123456789ab myrepo/mycontainer mytag
    """
    if not isinstance(repository, str):
        repository = str(repository)
    if not isinstance(tag, str):
        tag = str(tag)

    image_id = inspect_image(name)["Id"]
    response = _client_wrapper(
        "tag", image_id, repository=repository, tag=tag, force=force
    )
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


# Network Management
def networks(names=None, ids=None):
    """
    .. versionchanged:: 2017.7.0
        The ``names`` and ``ids`` can be passed as a comma-separated list now,
        as well as a Python list.
    .. versionchanged:: 2018.3.0
        The ``Containers`` key for each network is no longer always empty.

    List existing networks

    names
        Filter by name

    ids
        Filter by id

    CLI Example:

    .. code-block:: bash

        salt myminion docker.networks names=network-web
        salt myminion docker.networks ids=1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    """
    if names is not None:
        names = __utils__["args.split_input"](names)
    if ids is not None:
        ids = __utils__["args.split_input"](ids)

    response = _client_wrapper("networks", names=names, ids=ids)
    # Work around https://github.com/docker/docker-py/issues/1775
    for idx, netinfo in enumerate(response):
        try:
            containers = inspect_network(netinfo["Id"])["Containers"]
        except Exception:  # pylint: disable=broad-except
            continue
        else:
            if containers:
                response[idx]["Containers"] = containers

    return response


def create_network(
    name,
    skip_translate=None,
    ignore_collisions=False,
    validate_ip_addrs=True,
    client_timeout=salt.utils.dockermod.CLIENT_TIMEOUT,
    **kwargs,
):
    """
    .. versionchanged:: 2018.3.0
        Support added for network configuration options other than ``driver``
        and ``driver_opts``, as well as IPAM configuration.

    Create a new network

    .. note::
        This function supports all arguments for network and IPAM pool
        configuration which are available for the release of docker-py
        installed on the minion. For that reason, the arguments described below
        in the :ref:`NETWORK CONFIGURATION ARGUMENTS
        <salt-modules-dockermod-create-network-netconf>` and :ref:`IP ADDRESS
        MANAGEMENT (IPAM) <salt-modules-dockermod-create-network-ipam>`
        sections may not accurately reflect what is available on the minion.
        The :py:func:`docker.get_client_args
        <salt.modules.dockermod.get_client_args>` function can be used to check
        the available arguments for the installed version of docker-py (they
        are found in the ``network_config`` and ``ipam_config`` sections of the
        return data), but Salt will not prevent a user from attempting to use
        an argument which is unsupported in the release of Docker which is
        installed. In those cases, network creation be attempted but will fail.

    name
        Network name

    skip_translate
        This function translates Salt CLI or SLS input into the format which
        docker-py expects. However, in the event that Salt's translation logic
        fails (due to potential changes in the Docker Remote API, or to bugs in
        the translation code), this argument can be used to exert granular
        control over which arguments are translated and which are not.

        Pass this argument as a comma-separated list (or Python list) of
        arguments, and translation for each passed argument name will be
        skipped. Alternatively, pass ``True`` and *all* translation will be
        skipped.

        Skipping tranlsation allows for arguments to be formatted directly in
        the format which docker-py expects. This allows for API changes and
        other issues to be more easily worked around. See the following links
        for more information:

        - `docker-py Low-level API`_
        - `Docker Engine API`_

        .. versionadded:: 2018.3.0

    ignore_collisions : False
        Since many of docker-py's arguments differ in name from their CLI
        counterparts (with which most Docker users are more familiar), Salt
        detects usage of these and aliases them to the docker-py version of
        that argument. However, if both the alias and the docker-py version of
        the same argument (e.g. ``options`` and ``driver_opts``) are used, an error
        will be raised. Set this argument to ``True`` to suppress these errors
        and keep the docker-py version of the argument.

        .. versionadded:: 2018.3.0

    validate_ip_addrs : True
        For parameters which accept IP addresses as input, IP address
        validation will be performed. To disable, set this to ``False``

        .. note::
            When validating subnets, whether or not the IP portion of the
            subnet is a valid subnet boundary will not be checked. The IP will
            portion will be validated, and the subnet size will be checked to
            confirm it is a valid number (1-32 for IPv4, 1-128 for IPv6).

        .. versionadded:: 2018.3.0

    .. _salt-modules-dockermod-create-network-netconf:

    **NETWORK CONFIGURATION ARGUMENTS**

    driver
        Network driver

        Example: ``driver=macvlan``

    driver_opts (or *driver_opt*, or *options*)
        Options for the network driver. Either a dictionary of option names and
        values or a Python list of strings in the format ``varname=value``.

        Examples:

        - ``driver_opts='macvlan_mode=bridge,parent=eth0'``
        - ``driver_opts="['macvlan_mode=bridge', 'parent=eth0']"``
        - ``driver_opts="{'macvlan_mode': 'bridge', 'parent': 'eth0'}"``

    check_duplicate : True
        If ``True``, checks for networks with duplicate names. Since networks
        are primarily keyed based on a random ID and not on the name, and
        network name is strictly a user-friendly alias to the network which is
        uniquely identified using ID, there is no guaranteed way to check for
        duplicates. This option providess a best effort, checking for any
        networks which have the same name, but it is not guaranteed to catch
        all name collisions.

        Example: ``check_duplicate=False``

    internal : False
        If ``True``, restricts external access to the network

        Example: ``internal=True``

    labels
        Add metadata to the network. Labels can be set both with and without
        values:

        Examples (*with* values):

        - ``labels="label1=value1,label2=value2"``
        - ``labels="['label1=value1', 'label2=value2']"``
        - ``labels="{'label1': 'value1', 'label2': 'value2'}"``

        Examples (*without* values):

        - ``labels=label1,label2``
        - ``labels="['label1', 'label2']"``

    enable_ipv6 (or *ipv6*) : False
        Enable IPv6 on the network

        Example: ``enable_ipv6=True``

        .. note::
            While it should go without saying, this argument must be set to
            ``True`` to :ref:`configure an IPv6 subnet
            <salt-states-docker-network-present-ipam>`. Also, if this option is
            turned on without an IPv6 subnet explicitly configured, you will
            get an error unless you have set up a fixed IPv6 subnet. Consult
            the `Docker IPv6 docs`_ for information on how to do this.

            .. _`Docker IPv6 docs`: https://docs.docker.com/v17.09/engine/userguide/networking/default_network/ipv6/

    attachable : False
        If ``True``, and the network is in the global scope, non-service
        containers on worker nodes will be able to connect to the network.

        Example: ``attachable=True``

        .. note::
            While support for this option was added in API version 1.24, its
            value was not added to the inpsect results until API version 1.26.
            The version of Docker which is available for CentOS 7 runs API
            version 1.24, meaning that while Salt can pass this argument to the
            API, it has no way of knowing the value of this config option in an
            existing Docker network.

    scope
        Specify the network's scope (``local``, ``global`` or ``swarm``)

        Example: ``scope=local``

    ingress : False
        If ``True``, create an ingress network which provides the routing-mesh in
        swarm mode

        Example: ``ingress=True``

    .. _salt-modules-dockermod-create-network-ipam:

    **IP ADDRESS MANAGEMENT (IPAM)**

    This function supports networks with either IPv4, or both IPv4 and IPv6. If
    configuring IPv4, then you can pass the IPAM arguments as shown below, as
    individual arguments on the Salt CLI. However, if configuring IPv4 and
    IPv6, the arguments must be passed as a list of dictionaries, in the
    ``ipam_pools`` argument. See the **CLI Examples** below. `These docs`_ also
    have more information on these arguments.

    .. _`These docs`: http://docker-py.readthedocs.io/en/stable/api.html#docker.types.IPAMPool

    *IPAM ARGUMENTS*

    ipam_driver
        IPAM driver to use, if different from the default one

        Example: ``ipam_driver=foo``

    ipam_opts
        Options for the IPAM driver. Either a dictionary of option names
        and values or a Python list of strings in the format
        ``varname=value``.

        Examples:

        - ``ipam_opts='foo=bar,baz=qux'``
        - ``ipam_opts="['foo=bar', 'baz=quz']"``
        - ``ipam_opts="{'foo': 'bar', 'baz': 'qux'}"``

    *IPAM POOL ARGUMENTS*

    subnet
        Subnet in CIDR format that represents a network segment

        Example: ``subnet=192.168.50.0/25``

    iprange (or *ip_range*)
        Allocate container IP from a sub-range within the subnet

        Subnet in CIDR format that represents a network segment

        Example: ``iprange=192.168.50.64/26``

    gateway
        IPv4 gateway for the master subnet

        Example: ``gateway=192.168.50.1``

    aux_addresses (or *aux_address*)
        A dictionary of mapping container names to IP addresses which should be
        allocated for them should they connect to the network. Either a
        dictionary of option names and values or a Python list of strings in
        the format ``host=ipaddr``.

        Examples:

        - ``aux_addresses='foo.bar.tld=192.168.50.10,hello.world.tld=192.168.50.11'``
        - ``aux_addresses="['foo.bar.tld=192.168.50.10', 'hello.world.tld=192.168.50.11']"``
        - ``aux_addresses="{'foo.bar.tld': '192.168.50.10', 'hello.world.tld': '192.168.50.11'}"``

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.create_network web_network driver=bridge
        # IPv4
        salt myminion docker.create_network macvlan_network driver=macvlan driver_opts="{'parent':'eth0'}" gateway=172.20.0.1 subnet=172.20.0.0/24
        # IPv4 and IPv6
        salt myminion docker.create_network mynet ipam_pools='[{"subnet": "10.0.0.0/24", "gateway": "10.0.0.1"}, {"subnet": "fe3f:2180:26:1::60/123", "gateway": "fe3f:2180:26:1::61"}]'
    """
    kwargs = __utils__["docker.translate_input"](
        salt.utils.dockermod.translate.network,
        skip_translate=skip_translate,
        ignore_collisions=ignore_collisions,
        validate_ip_addrs=validate_ip_addrs,
        **__utils__["args.clean_kwargs"](**kwargs),
    )

    if "ipam" not in kwargs:
        ipam_kwargs = {}
        for key in [
            x
            for x in ["ipam_driver", "ipam_opts"]
            + get_client_args("ipam_config")["ipam_config"]
            if x in kwargs
        ]:
            ipam_kwargs[key] = kwargs.pop(key)
        ipam_pools = kwargs.pop("ipam_pools", ())

        # Don't go through the work of building a config dict if no
        # IPAM-specific configuration was passed. Just create the network
        # without specifying IPAM configuration.
        if ipam_pools or ipam_kwargs:
            kwargs["ipam"] = __utils__["docker.create_ipam_config"](
                *ipam_pools, **ipam_kwargs
            )

    response = _client_wrapper("create_network", name, **kwargs)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


def remove_network(network_id):
    """
    Remove a network

    network_id
        Network name or ID

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.remove_network mynet
        salt myminion docker.remove_network 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    """
    response = _client_wrapper("remove_network", network_id)
    _clear_context()
    return True


def inspect_network(network_id):
    """
    Inspect Network

    network_id
        ID of network

    CLI Example:

    .. code-block:: bash

        salt myminion docker.inspect_network 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    """
    response = _client_wrapper("inspect_network", network_id)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


def connect_container_to_network(container, net_id, **kwargs):
    """
    .. versionadded:: 2015.8.3
    .. versionchanged:: 2017.7.0
        Support for ``ipv4_address`` argument added
    .. versionchanged:: 2018.3.0
        All arguments are now passed through to
        `connect_container_to_network()`_, allowing for any new arguments added
        to this function to be supported automagically.

    Connect container to network. See the `connect_container_to_network()`_
    docs for information on supported arguments.

    container
        Container name or ID

    net_id
        Network name or ID

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.connect_container_to_network web-1 mynet
        salt myminion docker.connect_container_to_network web-1 mynet ipv4_address=10.20.0.10
        salt myminion docker.connect_container_to_network web-1 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)
    log.debug(
        "Connecting container '%s' to network '%s' with the following "
        "configuration: %s",
        container,
        net_id,
        kwargs,
    )
    response = _client_wrapper(
        "connect_container_to_network", container, net_id, **kwargs
    )
    log.debug(
        "Successfully connected container '%s' to network '%s'", container, net_id
    )
    _clear_context()
    return True


def disconnect_container_from_network(container, network_id):
    """
    .. versionadded:: 2015.8.3

    Disconnect container from network

    container
        Container name or ID

    network_id
        Network name or ID

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.disconnect_container_from_network web-1 mynet
        salt myminion docker.disconnect_container_from_network web-1 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    """
    log.debug("Disconnecting container '%s' from network '%s'", container, network_id)
    response = _client_wrapper(
        "disconnect_container_from_network", container, network_id
    )
    log.debug(
        "Successfully disconnected container '%s' from network '%s'",
        container,
        network_id,
    )
    _clear_context()
    return True


def disconnect_all_containers_from_network(network_id):
    """
    .. versionadded:: 2018.3.0

    Runs :py:func:`docker.disconnect_container_from_network
    <salt.modules.dockermod.disconnect_container_from_network>` on all
    containers connected to the specified network, and returns the names of all
    containers that were disconnected.

    network_id
        Network name or ID

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.disconnect_all_containers_from_network mynet
        salt myminion docker.disconnect_all_containers_from_network 1f9d2454d0872b68dd9e8744c6e7a4c66b86f10abaccc21e14f7f014f729b2bc
    """
    connected_containers = connected(network_id)
    ret = []
    failed = []
    for cname in connected_containers:
        try:
            disconnect_container_from_network(cname, network_id)
            ret.append(cname)
        except CommandExecutionError as exc:
            msg = str(exc)
            if "404" not in msg:
                # If 404 was in the error, then the container no longer exists,
                # so to avoid a race condition we won't consider 404 errors to
                # men that removal failed.
                failed.append(msg)
    if failed:
        raise CommandExecutionError(
            "One or more containers failed to be removed",
            info={"removed": ret, "errors": failed},
        )
    return ret


# Volume Management
def volumes(filters=None):
    """
    List existing volumes

    .. versionadded:: 2015.8.4

    filters
      There is one available filter: dangling=true

    CLI Example:

    .. code-block:: bash

        salt myminion docker.volumes filters="{'dangling': True}"
    """
    response = _client_wrapper("volumes", filters=filters)
    # Only non-error return case is a True return, so just return the response
    return response


def create_volume(name, driver=None, driver_opts=None):
    """
    Create a new volume

    .. versionadded:: 2015.8.4

    name
        name of volume

    driver
        Driver of the volume

    driver_opts
        Options for the driver volume

    CLI Example:

    .. code-block:: bash

        salt myminion docker.create_volume my_volume driver=local
    """
    response = _client_wrapper(
        "create_volume", name, driver=driver, driver_opts=driver_opts
    )
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


def remove_volume(name):
    """
    Remove a volume

    .. versionadded:: 2015.8.4

    name
        Name of volume

    CLI Example:

    .. code-block:: bash

        salt myminion docker.remove_volume my_volume
    """
    response = _client_wrapper("remove_volume", name)
    _clear_context()
    return True


def inspect_volume(name):
    """
    Inspect Volume

    .. versionadded:: 2015.8.4

    name
      Name of volume

    CLI Example:

    .. code-block:: bash

        salt myminion docker.inspect_volume my_volume
    """
    response = _client_wrapper("inspect_volume", name)
    _clear_context()
    # Only non-error return case is a True return, so just return the response
    return response


# Functions to manage container state
@_refresh_mine_cache
def kill(name):
    """
    Kill all processes in a running container instead of performing a graceful
    shutdown

    name
        Container name or ID

    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container cannot be killed

    CLI Example:

    .. code-block:: bash

        salt myminion docker.kill mycontainer
    """
    return _change_state(name, "kill", "stopped")


@_refresh_mine_cache
def pause(name):
    """
    Pauses a container

    name
        Container name or ID


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container cannot be paused

    CLI Example:

    .. code-block:: bash

        salt myminion docker.pause mycontainer
    """
    orig_state = state(name)
    if orig_state == "stopped":
        return {
            "result": False,
            "state": {"old": orig_state, "new": orig_state},
            "comment": f"Container '{name}' is stopped, cannot pause",
        }
    return _change_state(name, "pause", "paused")


freeze = salt.utils.functools.alias_function(pause, "freeze")


def restart(name, timeout=10):
    """
    Restarts a container

    name
        Container name or ID

    timeout : 10
        Timeout in seconds after which the container will be killed (if it has
        not yet gracefully shut down)


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``restarted`` - If restart was successful, this key will be present and
      will be set to ``True``.

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.restart mycontainer
        salt myminion docker.restart mycontainer timeout=20
    """
    ret = _change_state(name, "restart", "running", timeout=timeout)
    if ret["result"]:
        ret["restarted"] = True
    return ret


@_refresh_mine_cache
def signal_(name, signal):
    """
    Send a signal to a container. Signals can be either strings or numbers, and
    are defined in the **Standard Signals** section of the ``signal(7)``
    manpage. Run ``man 7 signal`` on a Linux host to browse this manpage.

    name
        Container name or ID

    signal
        Signal to send to container

    **RETURN DATA**

    If the signal was successfully sent, ``True`` will be returned. Otherwise,
    an error will be raised.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.signal mycontainer SIGHUP
    """
    _client_wrapper("kill", name, signal=signal)
    return True


@_refresh_mine_cache
def start_(name):
    """
    Start a container

    name
        Container name or ID

    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container cannot be started

    CLI Example:

    .. code-block:: bash

        salt myminion docker.start mycontainer
    """
    orig_state = state(name)
    if orig_state == "paused":
        return {
            "result": False,
            "state": {"old": orig_state, "new": orig_state},
            "comment": f"Container '{name}' is paused, cannot start",
        }

    return _change_state(name, "start", "running")


@_refresh_mine_cache
def stop(name, timeout=None, **kwargs):
    """
    Stops a running container

    name
        Container name or ID

    unpause : False
        If ``True`` and the container is paused, it will be unpaused before
        attempting to stop the container.

    timeout
        Timeout in seconds after which the container will be killed (if it has
        not yet gracefully shut down)

        .. versionchanged:: 2017.7.0
            If this argument is not passed, then the container's configuration
            will be checked. If the container was created using the
            ``stop_timeout`` argument, then the configured timeout will be
            used, otherwise the timeout will be 10 seconds.

    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container can not be stopped

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.stop mycontainer
        salt myminion docker.stop mycontainer unpause=True
        salt myminion docker.stop mycontainer timeout=20
    """
    if timeout is None:
        try:
            # Get timeout from container config
            timeout = inspect_container(name)["Config"]["StopTimeout"]
        except KeyError:
            # Fall back to a global default defined in salt.utils.dockermod
            timeout = salt.utils.dockermod.SHUTDOWN_TIMEOUT

    orig_state = state(name)
    if orig_state == "paused":
        if kwargs.get("unpause", False):
            unpause_result = _change_state(name, "unpause", "running")
            if unpause_result["result"] is False:
                unpause_result["comment"] = "Failed to unpause container '{}'".format(
                    name
                )
                return unpause_result
        else:
            return {
                "result": False,
                "state": {"old": orig_state, "new": orig_state},
                "comment": (
                    "Container '{}' is paused, run with "
                    "unpause=True to unpause before stopping".format(name)
                ),
            }
    ret = _change_state(name, "stop", "stopped", timeout=timeout)
    ret["state"]["old"] = orig_state
    return ret


@_refresh_mine_cache
def unpause(name):
    """
    Unpauses a container

    name
        Container name or ID


    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``comment`` - Only present if the container can not be unpaused

    CLI Example:

    .. code-block:: bash

        salt myminion docker.pause mycontainer
    """
    orig_state = state(name)
    if orig_state == "stopped":
        return {
            "result": False,
            "state": {"old": orig_state, "new": orig_state},
            "comment": f"Container '{name}' is stopped, cannot unpause",
        }
    return _change_state(name, "unpause", "running")


unfreeze = salt.utils.functools.alias_function(unpause, "unfreeze")


def wait(name, ignore_already_stopped=False, fail_on_exit_status=False):
    """
    Wait for the container to exit gracefully, and return its exit code

    .. note::

        This function will block until the container is stopped.

    name
        Container name or ID

    ignore_already_stopped
        Boolean flag that prevents execution to fail, if a container
        is already stopped.

    fail_on_exit_status
        Boolean flag to report execution as failure if ``exit_status``
        is different than 0.

    **RETURN DATA**

    A dictionary will be returned, containing the following keys:

    - ``status`` - A dictionary showing the prior state of the container as
      well as the new state
    - ``result`` - A boolean noting whether or not the action was successful
    - ``exit_status`` - Exit status for the container
    - ``comment`` - Only present if the container is already stopped

    CLI Example:

    .. code-block:: bash

        salt myminion docker.wait mycontainer
    """
    try:
        pre = state(name)
    except CommandExecutionError:
        # Container doesn't exist anymore
        return {
            "result": ignore_already_stopped,
            "comment": f"Container '{name}' absent",
        }
    already_stopped = pre == "stopped"
    response = _client_wrapper("wait", name)
    _clear_context()
    try:
        post = state(name)
    except CommandExecutionError:
        # Container doesn't exist anymore
        post = None

    if already_stopped:
        success = ignore_already_stopped
    elif post == "stopped":
        success = True
    else:
        success = False

    result = {
        "result": success,
        "state": {"old": pre, "new": post},
        "exit_status": response,
    }
    if already_stopped:
        result["comment"] = f"Container '{name}' already stopped"
    if fail_on_exit_status and result["result"]:
        result["result"] = result["exit_status"] == 0
    return result


def prune(
    containers=False,
    networks=False,
    images=False,
    build=False,
    volumes=False,
    system=None,
    **filters,
):
    """
    .. versionadded:: 2019.2.0

    Prune Docker's various subsystems

    .. note::
        This requires docker-py version 2.1.0 or later.

    containers : False
        If ``True``, prunes stopped containers (documentation__)

        .. __: https://docs.docker.com/engine/reference/commandline/container_prune/#filtering

    images : False
        If ``True``, prunes unused images (documentation__)

        .. __: https://docs.docker.com/engine/reference/commandline/image_prune/#filtering

    networks : False
        If ``False``, prunes unreferenced networks (documentation__)

        .. __: https://docs.docker.com/engine/reference/commandline/network_prune/#filtering)

    build : False
        If ``True``, clears the builder cache

        .. note::
            Only supported in Docker 17.07.x and newer. Additionally, filters
            do not apply to this argument.

    volumes : False
        If ``True``, prunes unreferenced volumes (documentation__)

        .. __: https://docs.docker.com/engine/reference/commandline/volume_prune/

    system
        If ``True``, prunes containers, images, networks, and builder cache.
        Assumed to be ``True`` if none of ``containers``, ``images``,
        ``networks``, or ``build`` are set to ``True``.

        .. note::
            ``volumes=True`` must still be used to prune volumes

    filters
        - ``dangling=True`` (images only) - remove only dangling images

        - ``until=<timestamp>`` - only remove objects created before given
          timestamp. Not applicable to volumes. See the documentation links
          above for examples of valid time expressions.

        - ``label`` - only remove objects matching the label expression. Valid
          expressions include ``labelname`` or ``labelname=value``.

    CLI Examples:

    .. code-block:: bash

        salt myminion docker.prune system=True
        salt myminion docker.prune system=True until=12h
        salt myminion docker.prune images=True dangling=True
        salt myminion docker.prune images=True label=foo,bar=baz
    """
    if system is None and not any((containers, images, networks, build)):
        system = True

    filters = __utils__["args.clean_kwargs"](**filters)
    for fname in list(filters):
        if not isinstance(filters[fname], bool):
            # support comma-separated values
            filters[fname] = salt.utils.args.split_input(filters[fname])

    ret = {}
    if system or containers:
        ret["containers"] = _client_wrapper("prune_containers", filters=filters)
    if system or images:
        ret["images"] = _client_wrapper("prune_images", filters=filters)
    if system or networks:
        ret["networks"] = _client_wrapper("prune_networks", filters=filters)
    if system or build:
        try:
            # Doesn't exist currently in docker-py as of 3.0.1
            ret["build"] = _client_wrapper("prune_build", filters=filters)
        except SaltInvocationError:
            # It's not in docker-py yet, POST directly to the API endpoint
            ret["build"] = _client_wrapper(
                "_result",
                _client_wrapper("_post", _client_wrapper("_url", "/build/prune")),
                True,
            )
    if volumes:
        ret["volumes"] = _client_wrapper("prune_volumes", filters=filters)

    return ret


# Functions to run commands inside containers
@_refresh_mine_cache
def _run(
    name,
    cmd,
    exec_driver=None,
    output=None,
    stdin=None,
    python_shell=True,
    output_loglevel="debug",
    ignore_retcode=False,
    use_vt=False,
    keep_env=None,
):
    """
    Common logic for docker.run functions
    """
    if exec_driver is None:
        exec_driver = _get_exec_driver()
    ret = __salt__["container_resource.run"](
        name,
        cmd,
        container_type=__virtualname__,
        exec_driver=exec_driver,
        output=output,
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        ignore_retcode=ignore_retcode,
        use_vt=use_vt,
        keep_env=keep_env,
    )

    if output in (None, "all"):
        return ret
    else:
        return ret[output]


@_refresh_mine_cache
def _script(
    name,
    source,
    saltenv="base",
    args=None,
    template=None,
    exec_driver=None,
    stdin=None,
    python_shell=True,
    output_loglevel="debug",
    ignore_retcode=False,
    use_vt=False,
    keep_env=None,
):
    """
    Common logic to run a script on a container
    """

    def _cleanup_tempfile(path):
        """
        Remove the tempfile allocated for the script
        """
        try:
            os.remove(path)
        except OSError as exc:
            log.error("cmd.script: Unable to clean tempfile '%s': %s", path, exc)

    path = __utils__["files.mkstemp"](
        dir="/tmp", prefix="salt", suffix=os.path.splitext(source)[1]
    )
    if template:
        fn_ = __salt__["cp.get_template"](source, path, template, saltenv)
        if not fn_:
            _cleanup_tempfile(path)
            return {
                "pid": 0,
                "retcode": 1,
                "stdout": "",
                "stderr": "",
                "cache_error": True,
            }
    else:
        fn_ = __salt__["cp.cache_file"](source, saltenv)
        if not fn_:
            _cleanup_tempfile(path)
            return {
                "pid": 0,
                "retcode": 1,
                "stdout": "",
                "stderr": "",
                "cache_error": True,
            }
        shutil.copyfile(fn_, path)

    if exec_driver is None:
        exec_driver = _get_exec_driver()

    copy_to(name, path, path, exec_driver=exec_driver)
    run(name, "chmod 700 " + path)

    ret = run_all(
        name,
        path + " " + str(args) if args else path,
        exec_driver=exec_driver,
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        ignore_retcode=ignore_retcode,
        use_vt=use_vt,
        keep_env=keep_env,
    )
    _cleanup_tempfile(path)
    run(name, "rm " + path)
    return ret


def retcode(
    name,
    cmd,
    exec_driver=None,
    stdin=None,
    python_shell=True,
    output_loglevel="debug",
    use_vt=False,
    ignore_retcode=False,
    keep_env=None,
):
    """
    Run :py:func:`cmd.retcode <salt.modules.cmdmod.retcode>` within a container

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.retcode mycontainer 'ls -l /etc'
    """
    return _run(
        name,
        cmd,
        exec_driver=exec_driver,
        output="retcode",
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        use_vt=use_vt,
        ignore_retcode=ignore_retcode,
        keep_env=keep_env,
    )


def run(
    name,
    cmd,
    exec_driver=None,
    stdin=None,
    python_shell=True,
    output_loglevel="debug",
    use_vt=False,
    ignore_retcode=False,
    keep_env=None,
):
    """
    Run :py:func:`cmd.run <salt.modules.cmdmod.run>` within a container

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.run mycontainer 'ls -l /etc'
    """
    return _run(
        name,
        cmd,
        exec_driver=exec_driver,
        output=None,
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        use_vt=use_vt,
        ignore_retcode=ignore_retcode,
        keep_env=keep_env,
    )


def run_all(
    name,
    cmd,
    exec_driver=None,
    stdin=None,
    python_shell=True,
    output_loglevel="debug",
    use_vt=False,
    ignore_retcode=False,
    keep_env=None,
):
    """
    Run :py:func:`cmd.run_all <salt.modules.cmdmod.run_all>` within a container

    .. note::

        While the command is run within the container, it is initiated from the
        host. Therefore, the PID in the return dict is from the host, not from
        the container.

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.run_all mycontainer 'ls -l /etc'
    """
    return _run(
        name,
        cmd,
        exec_driver=exec_driver,
        output="all",
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        use_vt=use_vt,
        ignore_retcode=ignore_retcode,
        keep_env=keep_env,
    )


def run_stderr(
    name,
    cmd,
    exec_driver=None,
    stdin=None,
    python_shell=True,
    output_loglevel="debug",
    use_vt=False,
    ignore_retcode=False,
    keep_env=None,
):
    """
    Run :py:func:`cmd.run_stderr <salt.modules.cmdmod.run_stderr>` within a
    container

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.run_stderr mycontainer 'ls -l /etc'
    """
    return _run(
        name,
        cmd,
        exec_driver=exec_driver,
        output="stderr",
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        use_vt=use_vt,
        ignore_retcode=ignore_retcode,
        keep_env=keep_env,
    )


def run_stdout(
    name,
    cmd,
    exec_driver=None,
    stdin=None,
    python_shell=True,
    output_loglevel="debug",
    use_vt=False,
    ignore_retcode=False,
    keep_env=None,
):
    """
    Run :py:func:`cmd.run_stdout <salt.modules.cmdmod.run_stdout>` within a
    container

    name
        Container name or ID in which to run the command

    cmd
        Command to run

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.run_stdout mycontainer 'ls -l /etc'
    """
    return _run(
        name,
        cmd,
        exec_driver=exec_driver,
        output="stdout",
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        use_vt=use_vt,
        ignore_retcode=ignore_retcode,
        keep_env=keep_env,
    )


def script(
    name,
    source,
    saltenv="base",
    args=None,
    template=None,
    exec_driver=None,
    stdin=None,
    python_shell=True,
    output_loglevel="debug",
    ignore_retcode=False,
    use_vt=False,
    keep_env=None,
):
    """
    Run :py:func:`cmd.script <salt.modules.cmdmod.script>` within a container

    .. note::

        While the command is run within the container, it is initiated from the
        host. Therefore, the PID in the return dict is from the host, not from
        the container.

    name
        Container name or ID

    source
        Path to the script. Can be a local path on the Minion or a remote file
        from the Salt fileserver.

    args
        A string containing additional command-line options to pass to the
        script.

    template : None
        Templating engine to use on the script before running.

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

    stdin : None
        Standard input to be used for the script

    output_loglevel : debug
        Level at which to log the output from the script. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.script mycontainer salt://docker_script.py
        salt myminion docker.script mycontainer salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt myminion docker.script mycontainer salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n' output_loglevel=quiet
    """
    return _script(
        name,
        source,
        saltenv=saltenv,
        args=args,
        template=template,
        exec_driver=exec_driver,
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        ignore_retcode=ignore_retcode,
        use_vt=use_vt,
        keep_env=keep_env,
    )


def script_retcode(
    name,
    source,
    saltenv="base",
    args=None,
    template=None,
    exec_driver=None,
    stdin=None,
    python_shell=True,
    output_loglevel="debug",
    ignore_retcode=False,
    use_vt=False,
    keep_env=None,
):
    """
    Run :py:func:`cmd.script_retcode <salt.modules.cmdmod.script_retcode>`
    within a container

    name
        Container name or ID

    source
        Path to the script. Can be a local path on the Minion or a remote file
        from the Salt fileserver.

    args
        A string containing additional command-line options to pass to the
        script.

    template : None
        Templating engine to use on the script before running.

    exec_driver : None
        If not passed, the execution driver will be detected as described
        :ref:`above <docker-execution-driver>`.

    stdin : None
        Standard input to be used for the script

    output_loglevel : debug
        Level at which to log the output from the script. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.script_retcode mycontainer salt://docker_script.py
        salt myminion docker.script_retcode mycontainer salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt myminion docker.script_retcode mycontainer salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n' output_loglevel=quiet
    """
    return _script(
        name,
        source,
        saltenv=saltenv,
        args=args,
        template=template,
        exec_driver=exec_driver,
        stdin=stdin,
        python_shell=python_shell,
        output_loglevel=output_loglevel,
        ignore_retcode=ignore_retcode,
        use_vt=use_vt,
        keep_env=keep_env,
    )["retcode"]


def _generate_tmp_path():
    return os.path.join("/tmp", f"salt.docker.{uuid.uuid4().hex[:6]}")


def _prepare_trans_tar(name, sls_opts, mods=None, pillar=None, extra_filerefs=""):
    """
    Prepares a self contained tarball that has the state
    to be applied in the container
    """
    chunks = _compile_state(sls_opts, mods)
    # reuse it from salt.ssh, however this function should
    # be somewhere else
    refs = salt.client.ssh.state.lowstate_file_refs(chunks, extra_filerefs)
    with _file_client() as fileclient:
        return salt.client.ssh.state.prep_trans_tar(
            fileclient, chunks, refs, pillar, name
        )


def _compile_state(sls_opts, mods=None):
    """
    Generates the chunks of lowdata from the list of modules
    """
    with HighState(sls_opts) as st_:
        if not mods:
            return st_.compile_low_chunks()

        high_data, errors = st_.render_highstate({sls_opts["saltenv"]: mods})
        high_data, ext_errors = st_.state.reconcile_extend(high_data)
        errors += ext_errors
        errors += st_.state.verify_high(high_data)
        if errors:
            return errors

        high_data, req_in_errors = st_.state.requisite_in(high_data)
        errors += req_in_errors
        high_data = st_.state.apply_exclude(high_data)
        # Verify that the high data is structurally sound
        if errors:
            return errors

        # Compile and verify the raw chunks
        return st_.state.compile_high_data(high_data)


def call(name, function, *args, **kwargs):
    """
    Executes a Salt function inside a running container

    .. versionadded:: 2016.11.0

    The container does not need to have Salt installed, but Python is required.

    name
        Container name or ID

    function
        Salt execution module function

    CLI Example:

    .. code-block:: bash

        salt myminion docker.call test.ping
        salt myminion test.arg arg1 arg2 key1=val1
        salt myminion dockerng.call compassionate_mirzakhani test.arg arg1 arg2 key1=val1

    """
    # where to put the salt-thin
    thin_dest_path = _generate_tmp_path()
    mkdirp_thin_argv = ["mkdir", "-p", thin_dest_path]

    # make thin_dest_path in the container
    ret = run_all(name, subprocess.list2cmdline(mkdirp_thin_argv))
    if ret["retcode"] != 0:
        return {"result": False, "comment": ret["stderr"]}

    if function is None:
        raise CommandExecutionError("Missing function parameter")

    # move salt into the container
    thin_path = __utils__["thin.gen_thin"](
        __opts__["cachedir"],
        extra_mods=__salt__["config.option"]("thin_extra_mods", ""),
        so_mods=__salt__["config.option"]("thin_so_mods", ""),
    )
    ret = copy_to(
        name, thin_path, os.path.join(thin_dest_path, os.path.basename(thin_path))
    )

    # figure out available python interpreter inside the container (only Python3)
    pycmds = ("python3", "/usr/libexec/platform-python")
    container_python_bin = None
    for py_cmd in pycmds:
        cmd = [py_cmd] + ["--version"]
        ret = run_all(name, subprocess.list2cmdline(cmd))
        if ret["retcode"] == 0:
            container_python_bin = py_cmd
            break
    if not container_python_bin:
        raise CommandExecutionError(
            "Python interpreter cannot be found inside the container. Make sure Python is installed in the container"
        )

    # untar archive
    untar_cmd = [
        container_python_bin,
        "-c",
        'import tarfile; tarfile.open("{0}/{1}").extractall(path="{0}")'.format(
            thin_dest_path, os.path.basename(thin_path)
        ),
    ]
    ret = run_all(name, subprocess.list2cmdline(untar_cmd))
    if ret["retcode"] != 0:
        return {"result": False, "comment": ret["stderr"]}

    try:
        salt_argv = (
            [
                container_python_bin,
                os.path.join(thin_dest_path, "salt-call"),
                "--metadata",
                "--local",
                "--log-file",
                os.path.join(thin_dest_path, "log"),
                "--cachedir",
                os.path.join(thin_dest_path, "cache"),
                "--out",
                "json",
                "-l",
                "quiet",
                "--",
                function,
            ]
            + list(args)
            + [
                f"{key}={value}"
                for (key, value) in kwargs.items()
                if not key.startswith("__")
            ]
        )

        ret = run_all(name, subprocess.list2cmdline(map(str, salt_argv)))
        # python not found
        if ret["retcode"] != 0:
            raise CommandExecutionError(ret["stderr"])

        # process "real" result in stdout
        try:
            data = __utils__["json.find_json"](ret["stdout"])
            local = data.get("local", data)
            if isinstance(local, dict):
                if "retcode" in local:
                    __context__["retcode"] = local["retcode"]
            return local.get("return", data)
        except ValueError:
            return {"result": False, "comment": "Can't parse container command output"}
    finally:
        # delete the thin dir so that it does not end in the image
        rm_thin_argv = ["rm", "-rf", thin_dest_path]
        run_all(name, subprocess.list2cmdline(rm_thin_argv))


def apply_(name, mods=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Apply states! This function will call highstate or state.sls based on the
    arguments passed in, ``apply`` is intended to be the main gateway for
    all state executions.

    CLI Example:

    .. code-block:: bash

        salt 'docker' docker.apply web01
        salt 'docker' docker.apply web01 test
        salt 'docker' docker.apply web01 test,pkgs
    """
    if mods:
        return sls(name, mods, **kwargs)
    return highstate(name, **kwargs)


def sls(name, mods=None, **kwargs):
    """
    Apply the states defined by the specified SLS modules to the running
    container

    .. versionadded:: 2016.11.0

    The container does not need to have Salt installed, but Python is required.

    name
        Container name or ID

    mods : None
        A string containing comma-separated list of SLS with defined states to
        apply to the container.

    saltenv : base
        Specify the environment from which to retrieve the SLS indicated by the
        `mods` parameter.

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

        .. versionadded:: 2018.3.0

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. note::
            Values passed this way will override Pillar values set via
            ``pillar_roots`` or an external Pillar source.

        .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt myminion docker.sls compassionate_mirzakhani mods=rails,web

    """
    mods = [item.strip() for item in mods.split(",")] if mods else []

    # Figure out the saltenv/pillarenv to use
    pillar_override = kwargs.pop("pillar", None)
    if "saltenv" not in kwargs:
        kwargs["saltenv"] = "base"
    sls_opts = __utils__["state.get_sls_opts"](__opts__, **kwargs)

    # gather grains from the container
    grains = call(name, "grains.items")

    # compile pillar with container grains
    pillar = salt.pillar.get_pillar(
        __opts__,
        grains,
        __opts__["id"],
        pillar_override=pillar_override,
        pillarenv=sls_opts["pillarenv"],
    ).compile_pillar()
    if pillar_override and isinstance(pillar_override, dict):
        pillar.update(pillar_override)

    sls_opts["grains"].update(grains)
    sls_opts["pillar"].update(pillar)
    trans_tar = _prepare_trans_tar(
        name,
        sls_opts,
        mods=mods,
        pillar=pillar,
        extra_filerefs=kwargs.get("extra_filerefs", ""),
    )

    # where to put the salt trans tar
    trans_dest_path = _generate_tmp_path()
    mkdirp_trans_argv = ["mkdir", "-p", trans_dest_path]
    # put_archive requires the path to exist
    ret = run_all(name, subprocess.list2cmdline(mkdirp_trans_argv))
    if ret["retcode"] != 0:
        return {"result": False, "comment": ret["stderr"]}

    ret = None
    try:
        trans_tar_sha256 = __utils__["hashutils.get_hash"](trans_tar, "sha256")
        copy_to(
            name,
            trans_tar,
            os.path.join(trans_dest_path, "salt_state.tgz"),
            exec_driver=_get_exec_driver(),
            overwrite=True,
        )

        # Now execute the state into the container
        ret = call(
            name,
            "state.pkg",
            os.path.join(trans_dest_path, "salt_state.tgz"),
            trans_tar_sha256,
            "sha256",
        )
    finally:
        # delete the trans dir so that it does not end in the image
        rm_trans_argv = ["rm", "-rf", trans_dest_path]
        run_all(name, subprocess.list2cmdline(rm_trans_argv))
        # delete the local version of the trans tar
        try:
            os.remove(trans_tar)
        except OSError as exc:
            log.error(
                "docker.sls: Unable to remove state tarball '%s': %s", trans_tar, exc
            )
    if not isinstance(ret, dict):
        __context__["retcode"] = 1
    elif not __utils__["state.check_result"](ret):
        __context__["retcode"] = 2
    else:
        __context__["retcode"] = 0
    return ret


def highstate(name, saltenv="base", **kwargs):
    """
    Apply a highstate to the running container

    .. versionadded:: 2019.2.0

    The container does not need to have Salt installed, but Python is required.

    name
        Container name or ID

    saltenv : base
        Specify the environment from which to retrieve the SLS indicated by the
        `mods` parameter.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.highstate compassionate_mirzakhani

    """
    return sls(name, saltenv="base", **kwargs)


def sls_build(
    repository, tag="latest", base="opensuse/python", mods=None, dryrun=False, **kwargs
):
    """
    .. versionchanged:: 2018.3.0
        The repository and tag must now be passed separately using the
        ``repository`` and ``tag`` arguments, rather than together in the (now
        deprecated) ``image`` argument.

    Build a Docker image using the specified SLS modules on top of base image

    .. versionadded:: 2016.11.0

    The base image does not need to have Salt installed, but Python is required.

    repository
        Repository name for the image to be built

        .. versionadded:: 2018.3.0

    tag : latest
        Tag name for the image to be built

        .. versionadded:: 2018.3.0

    name
        .. deprecated:: 2018.3.0
            Use both ``repository`` and ``tag`` instead

    base : opensuse/python
        Name or ID of the base image

    mods
        A string containing comma-separated list of SLS with defined states to
        apply to the base image.

    saltenv : base
        Specify the environment from which to retrieve the SLS indicated by the
        `mods` parameter.

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

        .. versionadded:: 2018.3.0

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. note::
            Values passed this way will override Pillar values set via
            ``pillar_roots`` or an external Pillar source.

        .. versionadded:: 2018.3.0

    dryrun: False
        when set to True the container will not be committed at the end of
        the build. The dryrun succeed also when the state contains errors.

    **RETURN DATA**

    A dictionary with the ID of the new container. In case of a dryrun,
    the state result is returned and the container gets removed.

    CLI Example:

    .. code-block:: bash

        salt myminion docker.sls_build imgname base=mybase mods=rails,web

    """
    create_kwargs = __utils__["args.clean_kwargs"](**copy.deepcopy(kwargs))
    for key in ("image", "name", "cmd", "interactive", "tty", "extra_filerefs"):
        try:
            del create_kwargs[key]
        except KeyError:
            pass

    # start a new container
    ret = create(
        image=base, cmd="sleep infinity", interactive=True, tty=True, **create_kwargs
    )
    id_ = ret["Id"]
    try:
        start_(id_)

        # Now execute the state into the container
        ret = sls(id_, mods, **kwargs)
        # fail if the state was not successful
        if not dryrun and not __utils__["state.check_result"](ret):
            raise CommandExecutionError(ret)
        if dryrun is False:
            ret = commit(id_, repository, tag=tag)
    finally:
        stop(id_)
        rm_(id_)
    return ret
