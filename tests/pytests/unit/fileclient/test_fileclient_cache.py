import errno
import logging
import os
import shutil

import pytest

import salt.utils.files
from salt import fileclient
from tests.support.mock import patch

log = logging.getLogger(__name__)


SUBDIR = "subdir"


def _saltenvs():
    return ("base", "dev")


def _subdir_files():
    return ("foo.txt", "bar.txt", "baz.txt")


def _get_file_roots(fs_root):
    return {x: [os.path.join(fs_root, x)] for x in _saltenvs()}


@pytest.fixture
def fs_root(tmp_path):
    return os.path.join(tmp_path, "fileclient_fs_root")


@pytest.fixture
def cache_root(tmp_path):
    return os.path.join(tmp_path, "fileclient_cache_root")


@pytest.fixture
def mocked_opts(tmp_path, fs_root, cache_root):
    return {
        "file_roots": _get_file_roots(fs_root),
        "fileserver_backend": ["roots"],
        "cachedir": cache_root,
        "file_client": "local",
    }


@pytest.fixture
def configure_loader_modules(tmp_path, mocked_opts):
    return {fileclient: {"__opts__": mocked_opts}}


@pytest.fixture(autouse=True)
def _setup(fs_root, cache_root):
    """
    No need to add a dummy foo.txt to muddy up the github repo, just make
    our own fileserver root on-the-fly.
    """

    def _new_dir(path):
        """
        Add a new dir at ``path`` using os.makedirs. If the directory
        already exists, remove it recursively and then try to create it
        again.
        """
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                # Just in case a previous test was interrupted, remove the
                # directory and try adding it again.
                shutil.rmtree(path)
                os.makedirs(path)
            else:
                raise

    # Crete the FS_ROOT
    for saltenv in _saltenvs():
        saltenv_root = os.path.join(fs_root, saltenv)
        # Make sure we have a fresh root dir for this saltenv
        _new_dir(saltenv_root)

        path = os.path.join(saltenv_root, "foo.txt")
        with salt.utils.files.fopen(path, "w") as fp_:
            fp_.write(f"This is a test file in the '{saltenv}' saltenv.\n")

        subdir_abspath = os.path.join(saltenv_root, SUBDIR)
        os.makedirs(subdir_abspath)
        for subdir_file in _subdir_files():
            path = os.path.join(subdir_abspath, subdir_file)
            with salt.utils.files.fopen(path, "w") as fp_:
                fp_.write(
                    "This is file '{}' in subdir '{} from saltenv '{}'".format(
                        subdir_file, SUBDIR, saltenv
                    )
                )

    # Create the CACHE_ROOT
    _new_dir(cache_root)


def test_cache_dir(mocked_opts, minion_opts):
    """
    Ensure entire directory is cached to correct location
    """
    patched_opts = minion_opts.copy()
    patched_opts.update(mocked_opts)

    with patch.dict(fileclient.__opts__, patched_opts):
        client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
        for saltenv in _saltenvs():
            assert client.cache_dir(f"salt://{SUBDIR}", saltenv, cachedir=None)
            for subdir_file in _subdir_files():
                cache_loc = os.path.join(
                    fileclient.__opts__["cachedir"],
                    "files",
                    saltenv,
                    SUBDIR,
                    subdir_file,
                )
                # Double check that the content of the cached file
                # identifies it as being from the correct saltenv. The
                # setUp function creates the file with the name of the
                # saltenv mentioned in the file, so a simple 'in' check is
                # sufficient here. If opening the file raises an exception,
                # this is a problem, so we are not catching the exception
                # and letting it be raised so that the test fails.
                with salt.utils.files.fopen(cache_loc) as fp_:
                    content = fp_.read()
                log.debug("cache_loc = %s", cache_loc)
                log.debug("content = %s", content)
                assert subdir_file in content
                assert SUBDIR in content
                assert saltenv in content


def test_cache_dir_with_alternate_cachedir_and_absolute_path(
    mocked_opts, minion_opts, tmp_path
):
    """
    Ensure entire directory is cached to correct location when an alternate
    cachedir is specified and that cachedir is an absolute path
    """
    patched_opts = minion_opts.copy()
    patched_opts.update(mocked_opts)
    alt_cachedir = os.path.join(tmp_path, "abs_cachedir")

    with patch.dict(fileclient.__opts__, patched_opts):
        client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
        for saltenv in _saltenvs():
            assert client.cache_dir(f"salt://{SUBDIR}", saltenv, cachedir=alt_cachedir)
            for subdir_file in _subdir_files():
                cache_loc = os.path.join(
                    alt_cachedir, "files", saltenv, SUBDIR, subdir_file
                )
                # Double check that the content of the cached file
                # identifies it as being from the correct saltenv. The
                # setUp function creates the file with the name of the
                # saltenv mentioned in the file, so a simple 'in' check is
                # sufficient here. If opening the file raises an exception,
                # this is a problem, so we are not catching the exception
                # and letting it be raised so that the test fails.
                with salt.utils.files.fopen(cache_loc) as fp_:
                    content = fp_.read()
                log.debug("cache_loc = %s", cache_loc)
                log.debug("content = %s", content)
                assert subdir_file in content
                assert SUBDIR in content
                assert saltenv in content


def test_cache_dir_with_alternate_cachedir_and_relative_path(mocked_opts, minion_opts):
    """
    Ensure entire directory is cached to correct location when an alternate
    cachedir is specified and that cachedir is a relative path
    """
    patched_opts = minion_opts.copy()
    patched_opts.update(mocked_opts)
    alt_cachedir = "foo"

    with patch.dict(fileclient.__opts__, patched_opts):
        client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
        for saltenv in _saltenvs():
            assert client.cache_dir(f"salt://{SUBDIR}", saltenv, cachedir=alt_cachedir)
            for subdir_file in _subdir_files():
                cache_loc = os.path.join(
                    fileclient.__opts__["cachedir"],
                    alt_cachedir,
                    "files",
                    saltenv,
                    SUBDIR,
                    subdir_file,
                )
                # Double check that the content of the cached file
                # identifies it as being from the correct saltenv. The
                # setUp function creates the file with the name of the
                # saltenv mentioned in the file, so a simple 'in' check is
                # sufficient here. If opening the file raises an exception,
                # this is a problem, so we are not catching the exception
                # and letting it be raised so that the test fails.
                with salt.utils.files.fopen(cache_loc) as fp_:
                    content = fp_.read()
                log.debug("cache_loc = %s", cache_loc)
                log.debug("content = %s", content)
                assert subdir_file in content
                assert SUBDIR in content
                assert saltenv in content


def test_cache_file(mocked_opts, minion_opts):
    """
    Ensure file is cached to correct location
    """
    patched_opts = minion_opts.copy()
    patched_opts.update(mocked_opts)

    with patch.dict(fileclient.__opts__, patched_opts):
        client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
        for saltenv in _saltenvs():
            assert client.cache_file("salt://foo.txt", saltenv, cachedir=None)
            cache_loc = os.path.join(
                fileclient.__opts__["cachedir"], "files", saltenv, "foo.txt"
            )
            # Double check that the content of the cached file identifies
            # it as being from the correct saltenv. The setUp function
            # creates the file with the name of the saltenv mentioned in
            # the file, so a simple 'in' check is sufficient here. If
            # opening the file raises an exception, this is a problem, so
            # we are not catching the exception and letting it be raised so
            # that the test fails.
            with salt.utils.files.fopen(cache_loc) as fp_:
                content = fp_.read()
            log.debug("cache_loc = %s", cache_loc)
            log.debug("content = %s", content)
            assert saltenv in content


def test_cache_file_with_alternate_cachedir_and_absolute_path(
    mocked_opts, minion_opts, tmp_path
):
    """
    Ensure file is cached to correct location when an alternate cachedir is
    specified and that cachedir is an absolute path
    """
    patched_opts = minion_opts.copy()
    patched_opts.update(mocked_opts)
    alt_cachedir = os.path.join(tmp_path, "abs_cachedir")

    with patch.dict(fileclient.__opts__, patched_opts):
        client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
        for saltenv in _saltenvs():
            assert client.cache_file("salt://foo.txt", saltenv, cachedir=alt_cachedir)
            cache_loc = os.path.join(alt_cachedir, "files", saltenv, "foo.txt")
            # Double check that the content of the cached file identifies
            # it as being from the correct saltenv. The setUp function
            # creates the file with the name of the saltenv mentioned in
            # the file, so a simple 'in' check is sufficient here. If
            # opening the file raises an exception, this is a problem, so
            # we are not catching the exception and letting it be raised so
            # that the test fails.
            with salt.utils.files.fopen(cache_loc) as fp_:
                content = fp_.read()
            log.debug("cache_loc = %s", cache_loc)
            log.debug("content = %s", content)
            assert saltenv in content


def test_cache_file_with_alternate_cachedir_and_relative_path(mocked_opts, minion_opts):
    """
    Ensure file is cached to correct location when an alternate cachedir is
    specified and that cachedir is a relative path
    """
    patched_opts = minion_opts.copy()
    patched_opts.update(mocked_opts)
    alt_cachedir = "foo"

    with patch.dict(fileclient.__opts__, patched_opts):
        client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
        for saltenv in _saltenvs():
            assert client.cache_file("salt://foo.txt", saltenv, cachedir=alt_cachedir)
            cache_loc = os.path.join(
                fileclient.__opts__["cachedir"],
                alt_cachedir,
                "files",
                saltenv,
                "foo.txt",
            )
            # Double check that the content of the cached file identifies
            # it as being from the correct saltenv. The setUp function
            # creates the file with the name of the saltenv mentioned in
            # the file, so a simple 'in' check is sufficient here. If
            # opening the file raises an exception, this is a problem, so
            # we are not catching the exception and letting it be raised so
            # that the test fails.
            with salt.utils.files.fopen(cache_loc) as fp_:
                content = fp_.read()
            log.debug("cache_loc = %s", cache_loc)
            log.debug("content = %s", content)
            assert saltenv in content


def test_cache_dest(mocked_opts, minion_opts):
    """
    Tests functionality for cache_dest
    """
    patched_opts = minion_opts.copy()
    patched_opts.update(mocked_opts)

    relpath = "foo.com/bar.txt"
    cachedir = minion_opts["cachedir"]

    def _external(saltenv="base"):
        return salt.utils.path.join(
            patched_opts["cachedir"], "extrn_files", saltenv, relpath
        )

    def _salt(saltenv="base"):
        return salt.utils.path.join(patched_opts["cachedir"], "files", saltenv, relpath)

    def _check(ret, expected):
        assert ret == expected, f"{ret} != {expected}"

    with patch.dict(fileclient.__opts__, patched_opts):
        client = fileclient.get_file_client(fileclient.__opts__, pillar=False)

        _check(client.cache_dest(f"https://{relpath}"), _external())

        _check(client.cache_dest(f"https://{relpath}", "dev"), _external("dev"))

        _check(client.cache_dest(f"salt://{relpath}"), _salt())

        _check(client.cache_dest(f"salt://{relpath}", "dev"), _salt("dev"))

        _check(client.cache_dest(f"salt://{relpath}?saltenv=dev"), _salt("dev"))

        _check("/foo/bar", "/foo/bar")
