"""
    tests.support.pytest.helpers
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    PyTest helpers functions
"""
import logging
import os
import pathlib
import pprint
import re
import shutil
import tempfile
import textwrap
import types
import warnings
from contextlib import contextmanager

import attr
import pytest
import salt.utils.platform
import salt.utils.pycrypto
from saltfactories.utils import random_string
from tests.support.pytest.loader import LoaderModuleMock
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion

log = logging.getLogger(__name__)

if not RUNTIME_VARS.PYTEST_SESSION:
    # XXX: Remove this try/except once we fully switch to pytest

    class FakePyTestHelpersNamespace:
        __slots__ = ()

        def register(self, func):
            return func

    # Patch pytest so it all works under runtests.py
    pytest.helpers = FakePyTestHelpersNamespace()


@pytest.helpers.register
@contextmanager
def temp_directory(name=None):
    """
    This helper creates a temporary directory. It should be used as a context manager
    which returns the temporary directory path, and, once out of context, deletes it.

    Can be directly imported and used, or, it can be used as a pytest helper function if
    ``pytest-helpers-namespace`` is installed.

    .. code-block:: python

        import os
        import pytest

        def test_blah():
            with pytest.helpers.temp_directory() as tpath:
                print(tpath)
                assert os.path.exists(tpath)

            assert not os.path.exists(tpath)
    """
    try:
        if name is not None:
            directory_path = os.path.join(RUNTIME_VARS.TMP, name)
        else:
            directory_path = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

        if not os.path.isdir(directory_path):
            os.makedirs(directory_path)

        yield directory_path
    finally:
        shutil.rmtree(directory_path, ignore_errors=True)


@pytest.helpers.register
@contextmanager
def temp_file(name=None, contents=None, directory=None, strip_first_newline=True):
    """
    This helper creates a temporary file. It should be used as a context manager
    which returns the temporary file path, and, once out of context, deletes it.

    Can be directly imported and used, or, it can be used as a pytest helper function if
    ``pytest-helpers-namespace`` is installed.

    .. code-block:: python

        import os
        import pytest

        def test_blah():
            with pytest.helpers.temp_file("blah.txt") as tpath:
                print(tpath)
                assert os.path.exists(tpath)

            assert not os.path.exists(tpath)

    Args:
        name(str):
            The temporary file name
        contents(str):
            The contents of the temporary file
        directory(str):
            The directory where to create the temporary file. If ``None``, then ``RUNTIME_VARS.TMP``
            will be used.
        strip_first_newline(bool):
            Wether to strip the initial first new line char or not.
    """
    try:
        if directory is None:
            directory = RUNTIME_VARS.TMP

        if not isinstance(directory, pathlib.Path):
            directory = pathlib.Path(str(directory))

        if name is not None:
            file_path = directory / name
        else:
            handle, file_path = tempfile.mkstemp(dir=str(directory))
            os.close(handle)
            file_path = pathlib.Path(file_path)

        file_directory = file_path.parent
        if not file_directory.is_dir():
            file_directory.mkdir(parents=True)

        if contents is not None:
            if contents:
                if contents.startswith("\n") and strip_first_newline:
                    contents = contents[1:]
                file_contents = textwrap.dedent(contents)
            else:
                file_contents = contents

            file_path.write_text(file_contents)
            log_contents = "{0} Contents of {1}\n{2}\n{3} Contents of {1}".format(
                ">" * 6, file_path, file_contents, "<" * 6
            )
            log.debug("Created temp file: %s\n%s", file_path, log_contents)
        else:
            log.debug("Touched temp file: %s", file_path)

        yield file_path

    finally:
        if file_path.exists():
            file_path.unlink()
            log.debug("Deleted temp file: %s", file_path)


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
            Wether to strip the initial first new line char or not.
    """

    if saltenv == "base":
        directory = RUNTIME_VARS.TMP_BASEENV_STATE_TREE
    elif saltenv == "prod":
        directory = RUNTIME_VARS.TMP_PRODENV_STATE_TREE
    else:
        raise RuntimeError(
            '"saltenv" can only be "base" or "prod", not "{}"'.format(saltenv)
        )
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
            Wether to strip the initial first new line char or not.
    """

    if saltenv == "base":
        directory = RUNTIME_VARS.TMP_BASEENV_PILLAR_TREE
    elif saltenv == "prod":
        directory = RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE
    else:
        raise RuntimeError(
            '"saltenv" can only be "base" or "prod", not "{}"'.format(saltenv)
        )
    return temp_file(
        name, contents, directory=directory, strip_first_newline=strip_first_newline
    )


@pytest.helpers.register
def loader_mock(*args, **kwargs):
    if len(args) > 1:
        loader_modules = args[1]
        warnings.warn(
            "'request' is not longer an accepted argument to 'loader_mock()'. Please stop passing it.",
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
        funcs["{}.{}".format(virtualname, funcname)] = func
    return funcs


@pytest.helpers.register
def remove_stale_minion_key(master, minion_id):
    key_path = os.path.join(master.config["pki_dir"], "minions", minion_id)
    if os.path.exists(key_path):
        os.unlink(key_path)
    else:
        log.debug("The minion(id=%r) key was not found at %s", minion_id, key_path)


@attr.s(kw_only=True, slots=True)
class TestAccount:
    sminion = attr.ib(default=None, repr=False)
    username = attr.ib(default=None)
    password = attr.ib(default=None)
    hashed_password = attr.ib(default=None, repr=False)
    groups = attr.ib(default=None)

    def __attrs_post_init__(self):
        if self.sminion is None:
            self.sminion = create_sminion()
        if self.username is None:
            self.username = random_string("account-", uppercase=False)
        if self.password is None:
            self.password = self.username
        if self.hashed_password is None:
            self.hashed_password = salt.utils.pycrypto.gen_hash(password=self.password)

    def __enter__(self):
        log.debug("Creating system account: %s", self)
        ret = self.sminion.functions.user.add(self.username)
        assert ret
        ret = self.sminion.functions.shadow.set_password(
            self.username,
            self.password if salt.utils.platform.is_darwin() else self.hashed_password,
        )
        assert ret
        assert self.username in self.sminion.functions.user.list_users()
        log.debug("Created system account: %s", self)
        # Run tests
        return self

    def __exit__(self, *args):
        self.sminion.functions.user.delete(self.username, remove=True, force=True)
        log.debug("Deleted system account: %s", self.username)


@pytest.helpers.register
@contextmanager
def create_account(username=None, password=None, hashed_password=None, sminion=None):
    with TestAccount(
        sminion=sminion,
        username=username,
        password=password,
        hashed_password=hashed_password,
    ) as account:
        yield account


@attr.s(frozen=True, slots=True)
class StateReturnAsserts:
    """
    Temporarily migrate SaltReturnAssertsMixin to a class we can use in PyTest.

    TEMPORARY!
    """

    ret = attr.ib()

    def assert_return_state_type(self):
        try:
            assert isinstance(self.ret, dict)
        except AssertionError:
            raise AssertionError(
                "{} is not dict. Salt returned: {}".format(
                    type(self.ret).__name__, self.ret
                )
            )

    def assert_return_non_empty_state_type(self):
        self.assert_return_state_type()
        try:
            assert self.ret != {}
        except AssertionError:
            raise AssertionError(
                "{} is equal to {}. Salt returned an empty dictionary."
            )

    def __return_valid_keys(self, keys):
        if isinstance(keys, tuple):
            # If it's a tuple, turn it into a list
            keys = list(keys)
        elif isinstance(keys, str):
            # If it's a string, make it a one item list
            keys = [keys]
        elif not isinstance(keys, list):
            # If we've reached here, it's a bad type passed to keys
            raise RuntimeError("The passed keys need to be a list")
        return keys

    def get_within_state_return(self, keys):
        self.assert_return_state_type()
        ret_data = []
        for part in self.ret.values():
            keys = self.__return_valid_keys(keys)
            okeys = keys[:]
            try:
                ret_item = part[okeys.pop(0)]
            except (KeyError, TypeError):
                raise AssertionError(
                    "Could not get ret{} from salt's return: {}".format(
                        "".join(["['{}']".format(k) for k in keys]), part
                    )
                )
            while okeys:
                try:
                    ret_item = ret_item[okeys.pop(0)]
                except (KeyError, TypeError):
                    raise AssertionError(
                        "Could not get ret{} from salt's return: {}".format(
                            "".join(["['{}']".format(k) for k in keys]), part
                        )
                    )
            ret_data.append(ret_item)
        return ret_data

    def assert_state_true_return(self):
        try:
            for saltret in self.get_within_state_return("result"):
                assert saltret is True
        except AssertionError:
            log.info("Salt Full Return:\n{}".format(pprint.pformat(self.ret)))
            try:
                raise AssertionError(
                    "{result} is not True. Salt Comment:\n{comment}".format(
                        **(next(iter(self.ret.values())))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    "Failed to get result. Salt Returned:\n{}".format(
                        pprint.pformat(self.ret)
                    )
                )

    def assert_state_false_return(self):
        try:
            for saltret in self.get_within_state_return("result"):
                assert saltret is False
        except AssertionError:
            log.info("Salt Full Return:\n{}".format(pprint.pformat(self.ret)))
            try:
                raise AssertionError(
                    "{result} is not False. Salt Comment:\n{comment}".format(
                        **(next(iter(self.ret.values())))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    "Failed to get result. Salt Returned: {}".format(self.ret)
                )

    def assert_state_none_return(self):
        try:
            for saltret in self.get_within_state_return("result"):
                assert saltret is None
        except AssertionError:
            log.info("Salt Full Return:\n{}".format(pprint.pformat(self.ret)))
            try:
                raise AssertionError(
                    "{result} is not None. Salt Comment:\n{comment}".format(
                        **(next(iter(self.ret.values())))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    "Failed to get result. Salt Returned: {}".format(self.ret)
                )

    def assert_in_state_comment(self, comment):
        for saltret in self.get_within_state_return("comment"):
            assert comment in saltret

    def assert_not_in_state_comment(self, comment):
        for saltret in self.get_within_state_return("comment"):
            assert comment not in saltret

    def assert_state_comment_regexp_matches(self, pattern):
        return self.assert_in_state_return_regexp_patches(pattern, "comment")

    def assert_in_state_warning(self, comment):
        for saltret in self.get_within_state_return("warnings"):
            assert comment in saltret

    def assert_not_in_state_warning(self, comment):
        for saltret in self.get_within_state_return("warnings"):
            assert comment not in saltret

    def assert_in_state_return(self, item_to_check, keys):
        for saltret in self.get_within_state_return(keys):
            assert item_to_check in saltret

    def assert_not_in_state_return(self, item_to_check, keys):
        for saltret in self.get_within_state_return(keys):
            assert item_to_check not in saltret

    def assert_in_state_return_regexp_patches(self, pattern, keys=()):
        for saltret in self.get_within_state_return(keys):
            assert re.match(pattern, saltret) is not None

    def assert_state_changes_equal(self, comparison, keys=()):
        keys = ["changes"] + self.__return_valid_keys(keys)
        for saltret in self.get_within_state_return(keys):
            assert comparison == saltret

    def assert_state_changes_not_equal(self, comparison, keys=()):
        keys = ["changes"] + self.__return_valid_keys(keys)
        for saltret in self.get_within_state_return(keys):
            assert comparison != saltret


@pytest.helpers.register
def state_return(ret):
    return StateReturnAsserts(ret)


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


# Only allow star importing the functions defined in this module
__all__ = [
    name
    for (name, func) in locals().items()
    if getattr(func, "__module__", None) == __name__
]
