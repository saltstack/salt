"""
    tests.support.pytest.helpers
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    PyTest helpers functions
"""

import logging
import os
import pathlib
import pprint
import shutil
import subprocess
import tempfile
import textwrap
import time
import types
import warnings
from contextlib import contextmanager

import attr
import psutil
import pytest
from saltfactories.utils import random_string
from saltfactories.utils.tempfiles import temp_file

import salt.utils.platform
import salt.utils.pycrypto
from tests.support.pytest.loader import LoaderModuleMock
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion

log = logging.getLogger(__name__)


@pytest.helpers.register
def temp_state_file(name, contents, saltenv="base", strip_first_newline=True):
    """
    This helper creates a temporary state file. It should be used as a context manager
    which returns the temporary state file path, and, once out of context, deletes it.

    Can be directly imported and used, or, it can be used as a pytest helper function if
    ``pytest-helpers-namespace`` is installed.

    .. code-block:: python

        import os
        import pytest

        def test_blah():
            with pytest.helpers.temp_state_file("blah.sls") as tpath:
                print(tpath)
                assert os.path.exists(tpath)

            assert not os.path.exists(tpath)

    Depending on the saltenv, it will be created under ``RUNTIME_VARS.TMP_STATE_TREE`` or
    ``RUNTIME_VARS.TMP_PRODENV_STATE_TREE``.

    Args:
        name(str):
            The temporary state file name
        contents(str):
            The contents of the temporary file
        saltenv(str):
            The salt env to use. Either ``base`` or ``prod``
        strip_first_newline(bool):
            Whether to strip the initial first new line char or not.
    """

    if saltenv == "base":
        directory = RUNTIME_VARS.TMP_BASEENV_STATE_TREE
    elif saltenv == "prod":
        directory = RUNTIME_VARS.TMP_PRODENV_STATE_TREE
    else:
        raise RuntimeError(f'"saltenv" can only be "base" or "prod", not "{saltenv}"')
    return temp_file(
        name, contents, directory=directory, strip_first_newline=strip_first_newline
    )


@pytest.helpers.register
def temp_pillar_file(name, contents, saltenv="base", strip_first_newline=True):
    """
    This helper creates a temporary pillar file. It should be used as a context manager
    which returns the temporary pillar file path, and, once out of context, deletes it.

    Can be directly imported and used, or, it can be used as a pytest helper function if
    ``pytest-helpers-namespace`` is installed.

    .. code-block:: python

        import os
        import pytest

        def test_blah():
            with pytest.helpers.temp_pillar_file("blah.sls") as tpath:
                print(tpath)
                assert os.path.exists(tpath)

            assert not os.path.exists(tpath)

    Depending on the saltenv, it will be created under ``RUNTIME_VARS.TMP_PILLAR_TREE`` or
    ``RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE``.

    Args:
        name(str):
            The temporary state file name
        contents(str):
            The contents of the temporary file
        saltenv(str):
            The salt env to use. Either ``base`` or ``prod``
        strip_first_newline(bool):
            Whether to strip the initial first new line char or not.
    """

    if saltenv == "base":
        directory = RUNTIME_VARS.TMP_BASEENV_PILLAR_TREE
    elif saltenv == "prod":
        directory = RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE
    else:
        raise RuntimeError(f'"saltenv" can only be "base" or "prod", not "{saltenv}"')
    return temp_file(
        name, contents, directory=directory, strip_first_newline=strip_first_newline
    )


@pytest.helpers.register
def loader_mock(*args, **kwargs):
    if len(args) > 1:
        loader_modules = args[1]
        warnings.warn(
            "'request' is not longer an accepted argument to 'loader_mock()'. Please"
            " stop passing it.",
            category=DeprecationWarning,
        )
    else:
        loader_modules = args[0]
    return LoaderModuleMock(loader_modules, **kwargs)


@pytest.helpers.register
def salt_loader_module_functions(module):
    if not isinstance(module, types.ModuleType):
        raise RuntimeError(
            "The passed 'module' argument must be an imported "
            "imported module, not {}".format(type(module))
        )
    funcs = {}
    func_alias = getattr(module, "__func_alias__", {})
    virtualname = getattr(module, "__virtualname__")
    for name in dir(module):
        if name.startswith("_"):
            continue
        func = getattr(module, name)
        if getattr(func, "__module__", None) != module.__name__:
            # Not eve defined on the module being processed, carry on
            continue
        if not isinstance(func, types.FunctionType):
            # Not a function? carry on
            continue
        funcname = func_alias.get(func.__name__) or func.__name__
        funcs[f"{virtualname}.{funcname}"] = func
    return funcs


@pytest.helpers.register
def remove_stale_minion_key(master, minion_id):
    key_path = os.path.join(master.config["pki_dir"], "minions", minion_id)
    if os.path.exists(key_path):
        os.unlink(key_path)
    else:
        log.debug("The minion(id=%r) key was not found at %s", minion_id, key_path)


@pytest.helpers.register
def remove_stale_master_key(master):
    keys_path = os.path.join(master.config["pki_dir"], "master")
    for key_name in ("master.pem", "master.pub"):
        key_path = os.path.join(keys_path, key_name)
        if os.path.exists(key_path):
            os.unlink(key_path)
        else:
            log.debug(
                "The master(id=%r) %s key was not found at %s",
                master.id,
                key_name,
                key_path,
            )
    key_path = os.path.join(master.config["pki_dir"], "minion", "minion_master.pub")
    if os.path.exists(key_path):
        os.unlink(key_path)
    else:
        log.debug(
            "The master(id=%r) minion_master.pub key was not found at %s",
            master.id,
            key_path,
        )


@pytest.helpers.register
def remove_stale_proxy_minion_cache_file(proxy_minion, minion_id=None):
    cachefile = os.path.join(
        proxy_minion.config["cachedir"],
        f"dummy-proxy-{minion_id or proxy_minion.id}.cache",
    )
    if os.path.exists(cachefile):
        os.unlink(cachefile)


@attr.s(kw_only=True, slots=True)
class TestGroup:
    sminion = attr.ib(repr=False)
    name = attr.ib()
    gid = attr.ib(default=None)
    members = attr.ib(default=None)
    _delete_group = attr.ib(init=False, repr=False, default=False)

    @sminion.default
    def _default_sminion(self):
        return create_sminion()

    @name.default
    def _default_name(self):
        return random_string("group-", uppercase=False)

    @property
    def info(self):
        return types.SimpleNamespace(**self.sminion.functions.group.info(self.name))

    def __enter__(self):
        group = self.sminion.functions.group.info(self.name)
        if not group:
            ret = self.sminion.functions.group.add(
                self.name, gid=self.gid, non_unique=True
            )
            assert ret
            self._delete_group = True
            log.debug("Created system group: %s", self)
        else:
            log.debug("Reusing existing system group: %s", self)
        if self.members:
            ret = self.sminion.functions.group.members(
                self.name, members_list=self.members
            )
            assert ret
        # Run tests
        return self

    def __exit__(self, *_):
        if self._delete_group:
            try:
                self.sminion.functions.group.delete(self.name)
                log.debug("Deleted system group: %s", self.name)
            except Exception:  # pylint: disable=broad-except
                log.warning(
                    "Failed to delete system group: %s", self.name, exc_info=True
                )


@pytest.helpers.register
@contextmanager
def create_group(name=attr.NOTHING, sminion=attr.NOTHING, gid=None, members=None):
    with TestGroup(sminion=sminion, name=name, gid=gid, members=members) as group:
        yield group


@attr.s(kw_only=True, slots=True)
class TestAccount:
    sminion = attr.ib(repr=False)
    username = attr.ib()
    password = attr.ib()
    hashed_password = attr.ib(repr=False)
    create_group = attr.ib(repr=False, default=False)
    group_name = attr.ib()
    _group = attr.ib(init=True, repr=False)
    _delete_account = attr.ib(init=False, repr=False, default=False)

    @sminion.default
    def _default_sminion(self):
        return create_sminion()

    @username.default
    def _default_username(self):
        return random_string("account-", uppercase=False)

    @password.default
    def _default_password(self):
        return random_string("pwd-", size=8)

    @hashed_password.default
    def _default_hashed_password(self):
        if not salt.utils.platform.is_darwin() and not salt.utils.platform.is_windows():
            return salt.utils.pycrypto.gen_hash(password=self.password)
        return self.password

    @group_name.default
    def _default_group_name(self):
        if self.create_group:
            return f"group-{self.username}"
        return None

    @_group.default
    def _default__group(self):
        if self.group_name:
            return TestGroup(sminion=self.sminion, name=self.group_name)
        return None

    @property
    def info(self):
        return types.SimpleNamespace(**self.sminion.functions.user.info(self.username))

    @property
    def group(self):
        if self._group is None:
            raise RuntimeError(
                "Neither `create_group` nor `group_name` was passed when creating the "
                "account. There's no group attribute in this account instance."
            )
        return self._group

    @group.setter
    def _set_group(self, value):
        self._group = value

    def __enter__(self):
        if not self.sminion.functions.user.info(self.username):
            log.debug("Creating system account: %s", self)
            ret = self.sminion.functions.user.add(self.username)
            assert ret is True
            self._delete_account = True
        if salt.utils.platform.is_windows():
            log.debug("Configuring system account: %s", self)
            ret = self.sminion.functions.user.update(
                self.username, password_never_expires=True
            )
        if salt.utils.platform.is_darwin() or salt.utils.platform.is_windows():
            password = self.password
        else:
            password = self.hashed_password
        ret = self.sminion.functions.shadow.set_password(self.username, password)
        assert ret is True
        assert self.username in self.sminion.functions.user.list_users()
        if self._group:
            self.group.__enter__()
            self.sminion.functions.group.adduser(self.group.name, self.username)
            if not salt.utils.platform.is_windows():
                # Make this group the primary_group for the user
                self.sminion.functions.user.chgid(self.username, self.group.info.gid)
                assert self.info.gid == self.group.info.gid
        if self._delete_account:
            log.debug("Created system account: %s", self)
        else:
            log.debug("Reusing existing system account: %s", self)
        # Run tests
        return self

    def __exit__(self, *args):
        if self._group:
            try:
                self.sminion.functions.group.deluser(self.group.name, self.username)
                log.debug(
                    "Removed user %r from group %r", self.username, self.group.name
                )
            except Exception:  # pylint: disable=broad-except
                log.warning(
                    "Failed to remove user %r from group %r",
                    self.username,
                    self.group.name,
                    exc_info=True,
                )

            self.group.__exit__(*args)

        if self._delete_account:
            try:
                delete_kwargs = {"force": True}
                if salt.utils.platform.is_windows():
                    delete_kwargs["purge"] = True
                else:
                    delete_kwargs["remove"] = True
                self.sminion.functions.user.delete(self.username, **delete_kwargs)
                log.debug("Deleted system account: %s", self.username)
            except Exception:  # pylint: disable=broad-except
                log.warning(
                    "Failed to delete system account: %s", self.username, exc_info=True
                )

            if self.sminion.functions.group.info(self.username):
                # A group with the same name as the user name still exists.
                # Let's delete it
                try:
                    self.sminion.functions.group.delete(self.username)
                    log.debug(
                        "Deleted system group matching username: %s", self.username
                    )
                except Exception:  # pylint: disable=broad-except
                    log.warning(
                        "Failed to delete system group matching username: %s",
                        self.username,
                        exc_info=True,
                    )


@pytest.helpers.register
@contextmanager
def create_account(
    username=attr.NOTHING,
    password=attr.NOTHING,
    hashed_password=attr.NOTHING,
    group_name=attr.NOTHING,
    create_group=False,
    group=attr.NOTHING,
    sminion=attr.NOTHING,
):
    with TestAccount(
        sminion=sminion,
        username=username,
        password=password,
        hashed_password=hashed_password,
        group_name=group_name,
        create_group=create_group,
        group=group,
    ) as account:
        yield account


@pytest.helpers.register
def shell_test_true():
    if salt.utils.platform.is_windows():
        return "cmd.exe /c exit 0"
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        return "/usr/bin/true"
    return "/bin/true"


@pytest.helpers.register
def shell_test_false():
    if salt.utils.platform.is_windows():
        return "cmd.exe /c exit 1"
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        return "/usr/bin/false"
    return "/bin/false"


@attr.s(kw_only=True, frozen=True)
class FakeSaltExtension:
    tmp_path_factory = attr.ib(repr=False)
    name = attr.ib()
    pkgname = attr.ib(init=False)
    srcdir = attr.ib(init=False)

    @srcdir.default
    def _srcdir(self):
        return self.tmp_path_factory.mktemp("src", numbered=True)

    @pkgname.default
    def _pkgname(self):
        replace_chars = ("-", " ")
        name = self.name
        for char in replace_chars:
            name = name.replace(char, "_")
        return name

    def __attrs_post_init__(self):
        self._laydown_files()

    def _laydown_files(self):
        if not self.srcdir.exists():
            self.srcdir.mkdir()
        setup_py = self.srcdir.joinpath("setup.py")
        if not setup_py.exists():
            setup_py.write_text(
                textwrap.dedent(
                    """\
            import setuptools

            if __name__ == "__main__":
                setuptools.setup()
            """
                )
            )
        setup_cfg = self.srcdir.joinpath("setup.cfg")
        if not setup_cfg.exists():
            setup_cfg.write_text(
                textwrap.dedent(
                    """\
            [metadata]
            name = {0}
            version = 1.0
            description = Salt Extension Test
            author = Pedro
            author_email = pedro@algarvio.me
            keywords = salt-extension
            url = http://saltproject.io
            license = Apache Software License 2.0
            classifiers =
                Programming Language :: Python
                Programming Language :: Cython
                Programming Language :: Python :: 3
                Programming Language :: Python :: 3 :: Only
                Development Status :: 4 - Beta
                Intended Audience :: Developers
                License :: OSI Approved :: Apache Software License
            platforms = any

            [options]
            zip_safe = False
            include_package_data = True
            packages = find:
            python_requires = >= 3.5
            setup_requires =
              wheel
              setuptools>=50.3.2

            [options.entry_points]
            salt.loader=
              module_dirs = {1}
              runner_dirs = {1}.loader:get_runner_dirs
              states_dirs = {1}.loader:get_state_dirs
              wheel_dirs = {1}.loader:get_new_style_entry_points
            """.format(
                        self.name, self.pkgname
                    )
                )
            )

        extension_package_dir = self.srcdir / self.pkgname
        if not extension_package_dir.exists():
            extension_package_dir.mkdir()
            extension_package_dir.joinpath("__init__.py").write_text("")
            extension_package_dir.joinpath("loader.py").write_text(
                textwrap.dedent(
                    """\
            import pathlib

            PKG_ROOT = pathlib.Path(__file__).resolve().parent

            def get_module_dirs():
                return [str(PKG_ROOT / "modules")]

            def get_runner_dirs():
                return [str(PKG_ROOT / "runners1"), str(PKG_ROOT / "runners2")]

            def get_state_dirs():
                yield str(PKG_ROOT / "states1")

            def get_new_style_entry_points():
                return {"wheel": [str(PKG_ROOT / "the_wheel_modules")]}
            """
                )
            )

            runners1_dir = extension_package_dir / "runners1"
            runners1_dir.mkdir()
            runners1_dir.joinpath("__init__.py").write_text("")
            runners1_dir.joinpath("foobar1.py").write_text(
                textwrap.dedent(
                    """\
            __virtualname__ = "foobar"

            def __virtual__():
                return True

            def echo1(string):
                return string
            """
                )
            )

            runners2_dir = extension_package_dir / "runners2"
            runners2_dir.mkdir()
            runners2_dir.joinpath("__init__.py").write_text("")
            runners2_dir.joinpath("foobar2.py").write_text(
                textwrap.dedent(
                    """\
            __virtualname__ = "foobar"

            def __virtual__():
                return True

            def echo2(string):
                return string
            """
                )
            )

            modules_dir = extension_package_dir / "modules"
            modules_dir.mkdir()
            modules_dir.joinpath("__init__.py").write_text("")
            modules_dir.joinpath("foobar1.py").write_text(
                textwrap.dedent(
                    """\
            __virtualname__ = "foobar"

            def __virtual__():
                return True

            def echo1(string):
                return string
            """
                )
            )
            modules_dir.joinpath("foobar2.py").write_text(
                textwrap.dedent(
                    """\
            __virtualname__ = "foobar"

            def __virtual__():
                return True

            def echo2(string):
                return string
            """
                )
            )

            wheel_dir = extension_package_dir / "the_wheel_modules"
            wheel_dir.mkdir()
            wheel_dir.joinpath("__init__.py").write_text("")
            wheel_dir.joinpath("foobar1.py").write_text(
                textwrap.dedent(
                    """\
            __virtualname__ = "foobar"

            def __virtual__():
                return True

            def echo1(string):
                return string
            """
                )
            )
            wheel_dir.joinpath("foobar2.py").write_text(
                textwrap.dedent(
                    """\
            __virtualname__ = "foobar"

            def __virtual__():
                return True

            def echo2(string):
                return string
            """
                )
            )

            states_dir = extension_package_dir / "states1"
            states_dir.mkdir()
            states_dir.joinpath("__init__.py").write_text("")
            states_dir.joinpath("foobar1.py").write_text(
                textwrap.dedent(
                    """\
            __virtualname__ = "foobar"

            def __virtual__():
                return True

            def echoed(string):
                ret = {"name": name, "changes": {}, "result": True, "comment": string}
                return ret
            """
                )
            )

            utils_dir = extension_package_dir / "utils"
            utils_dir.mkdir()
            utils_dir.joinpath("__init__.py").write_text("")
            utils_dir.joinpath("foobar1.py").write_text(
                textwrap.dedent(
                    """\
            __virtualname__ = "foobar"

            def __virtual__():
                return True

            def echo(string):
                return string
            """
                )
            )

    def __enter__(self):
        self._laydown_files()
        return self

    def __exit__(self, *_):
        shutil.rmtree(str(self.srcdir), ignore_errors=True)


class EntropyGenerator:
    max_minutes = 5
    minimum_entropy = 800

    def __init__(self, max_minutes=None, minimum_entropy=None, skip=None):
        if max_minutes is not None:
            self.max_minutes = max_minutes
        if minimum_entropy is not None:
            self.minimum_entropy = minimum_entropy
        if skip is None:
            skip = True
        self.skip = skip
        self.current_entropy = 0

    def generate_entropy(self):
        max_time = self.max_minutes * 60
        kernel_entropy_file = pathlib.Path("/proc/sys/kernel/random/entropy_avail")
        kernel_poolsize_file = pathlib.Path("/proc/sys/kernel/random/poolsize")
        if not kernel_entropy_file.exists():
            log.info("The '%s' file is not available", kernel_entropy_file)
            return

        self.current_entropy = int(
            kernel_entropy_file.read_text(encoding="utf-8").strip()
        )
        log.info("Available Entropy: %s", self.current_entropy)

        if not kernel_poolsize_file.exists():
            log.info("The '%s' file is not available", kernel_poolsize_file)
        else:
            self.current_poolsize = int(
                kernel_poolsize_file.read_text(encoding="utf-8").strip()
            )
            log.info("Entropy Poolsize: %s", self.current_poolsize)
            # Account for smaller poolsizes using BLAKE2s
            if self.current_poolsize == 256:
                self.minimum_entropy = 192

        if self.current_entropy >= self.minimum_entropy:
            return

        rngd = shutil.which("rngd")
        openssl = shutil.which("openssl")
        timeout = time.time() + max_time
        if rngd:
            log.info("Using rngd to generate entropy")
            while True:
                if time.time() >= timeout:
                    message = (
                        "Skipping test as generating entropy took more than {} minutes. "
                        "Current entropy value {}".format(
                            self.max_minutes, self.current_entropy
                        )
                    )
                    if self.skip:
                        raise pytest.skip.Exception(message, _use_item_location=True)
                    raise pytest.fail(message)
                subprocess.run([rngd, "-r", "/dev/urandom"], shell=False, check=True)
                self.current_entropy = int(
                    kernel_entropy_file.read_text(encoding="utf-8").strip()
                )
                log.info("Available Entropy: %s", self.current_entropy)
                if self.current_entropy >= self.minimum_entropy:
                    break
        elif openssl:
            log.info("Using openssl to generate entropy")
            while True:
                if time.time() >= timeout:
                    message = (
                        "Skipping test as generating entropy took more than {} minutes. "
                        "Current entropy value {}".format(
                            self.max_minutes, self.current_entropy
                        )
                    )
                    if self.skip:
                        raise pytest.skip.Exception(message, _use_item_location=True)
                    raise pytest.fail(message)

                target_file = tempfile.NamedTemporaryFile(
                    delete=False, suffix="sample.txt"
                )
                target_file.close()
                subprocess.run(
                    [
                        openssl,
                        "rand",
                        "-out",
                        target_file.name,
                        "-base64",
                        str(int(2**30 * 3 / 4)),  # 1GB
                    ],
                    shell=False,
                    check=True,
                )
                os.unlink(target_file.name)
                self.current_entropy = int(
                    kernel_entropy_file.read_text(encoding="utf-8").strip()
                )
                log.info("Available Entropy: %s", self.current_entropy)
                if self.current_entropy >= self.minimum_entropy:
                    break
        else:
            message = (
                "Skipping test as there's not enough entropy({}) to continue and "
                "neither 'rgn-tools' nor 'openssl' is available on the system.".format(
                    self.current_entropy
                )
            )
            if self.skip:
                raise pytest.skip.Exception(message, _use_item_location=True)
            raise pytest.fail(message)

    def __enter__(self):
        self.generate_entropy()
        return self

    def __exit__(self, *_):
        pass


@pytest.helpers.register
@contextmanager
def change_cwd(path):
    """
    Context manager helper to change CWD for a with code block and restore
    it at the end
    """
    old_cwd = os.getcwd()
    try:
        os.chdir(path)
        # Do stuff
        yield
    finally:
        # Restore Old CWD
        os.chdir(old_cwd)


@contextmanager
def reap_stray_processes(pid: int = os.getpid()):

    try:
        pre_children = psutil.Process(pid).children(recursive=True)
        # Do stuff
        yield
    finally:
        post_children = psutil.Process(pid).children(recursive=True)

    children = []
    for process in post_children:
        if process in pre_children:
            # Process existed before entering the context
            continue
        if not psutil.pid_exists(process.pid):
            # Process just died
            continue
        # This process is alive and was not running before entering the context
        children.append(process)

    if not children:
        log.info("No astray processes found")
        return

    def on_terminate(proc):
        log.debug("Process %s terminated with exit code %s", proc, proc.returncode)

    if children:
        # Reverse the order, sublings first, parents after
        children.reverse()
        log.warning(
            "Test suite left %d astray processes running. Killing those processes:\n%s",
            len(children),
            pprint.pformat(children),
        )

        _, alive = psutil.wait_procs(children, timeout=3, callback=on_terminate)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                continue

        _, alive = psutil.wait_procs(alive, timeout=3, callback=on_terminate)
        if alive:
            # Give up
            for child in alive:
                log.warning(
                    "Process %s survived SIGKILL, giving up:\n%s",
                    child,
                    pprint.pformat(child.as_dict()),
                )


# Only allow star importing the functions defined in this module
__all__ = [
    name
    for (name, func) in locals().items()
    if getattr(func, "__module__", None) == __name__
]
