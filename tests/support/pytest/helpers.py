# -*- coding: utf-8 -*-
"""
    tests.support.pytest.helpers
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    PyTest helpers functions
"""
import os
import shutil
import tempfile
import textwrap
from contextlib import contextmanager

import pytest
import salt.utils.files
from tests.support.pytest.loader import LoaderModuleMock
from tests.support.runtests import RUNTIME_VARS


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

        if name is not None:
            file_path = os.path.join(directory, name)
        else:
            handle, file_path = tempfile.mkstemp(dir=directory)
            os.close(handle)

        file_directory = os.path.dirname(file_path)
        if not os.path.isdir(file_directory):
            os.makedirs(file_directory)

        if contents is not None:
            if contents:
                if contents.startswith("\n") and strip_first_newline:
                    contents = contents[1:]
                file_contents = textwrap.dedent(contents)
            else:
                file_contents = contents

            with salt.utils.files.fopen(file_path, "w") as wfh:
                wfh.write(file_contents)

        yield file_path

    finally:
        try:
            os.unlink(file_path)
        except OSError:
            # Already deleted
            pass


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
        directory = RUNTIME_VARS.TMP_STATE_TREE
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
        directory = RUNTIME_VARS.TMP_PILLAR_TREE
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
def loader_mock(request, loader_modules, **kwargs):
    return LoaderModuleMock(request, loader_modules, **kwargs)


# Only allow star importing the functions defined in this module
__all__ = [
    name
    for (name, func) in locals().items()
    if getattr(func, "__module__", None) == __name__
]
