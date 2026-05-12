import hashlib
import os
import time
from pathlib import Path

import pytest
from saltfactories.utils import random_string

from tests.support.helpers import system_python_version
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.skipif(
        system_python_version() < (3, 10),
        reason="System python too old for these tests",
    ),
]


@pytest.fixture(scope="module", autouse=True)
def _pillar_tree(salt_master):
    top_file = """
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    basic_pillar_file = """
    test_pillar: cheese
    alot: many
    script: grail
    """
    with salt_master.pillar_tree.base.temp_file(
        "top.sls", top_file
    ), salt_master.pillar_tree.base.temp_file("basic.sls", basic_pillar_file):
        yield


@pytest.fixture(scope="function")
def cachedir(salt_ssh_cli_parameterized):
    """
    The current minion cache dir

    Note: This uses function scope (not module scope) to match salt_ssh_cli_parameterized.
    Module-scoped fixtures cannot depend on function-scoped fixtures in pytest.
    """
    # The salt-ssh cache dir in the minion context is different than
    # the one available in the salt_ssh_cli_parameterized opts. Any other way to get this? TODO
    res = salt_ssh_cli_parameterized.run("cp.cache_dest", "salt://file")
    assert res.returncode == 0
    assert isinstance(res.data, str)
    # This will return <cachedir>/files/base/file
    return Path(res.data).parent.parent.parent


@pytest.fixture(scope="function")
def master_cachedir(salt_ssh_cli_parameterized, cachedir):
    """
    The current per-target master-side staging root for salt-ssh files.

    The salt-ssh ``cp`` wrapper stages master-side files under
    ``<_master_staging_root()>/salt-ssh/<id>/`` -- a *sibling* of the thin
    dir, not a child of the minion cachedir. This is required because
    ``ssh_py_shim`` removes the thin dir tree when ``ssh_wipe`` is enabled,
    which would otherwise wipe staged files before the test (or any caller)
    can inspect them. Discover the actual location at runtime via
    ``cp.convert_cache_path`` so we mirror the production path computation
    in :class:`salt.client.ssh.wrapper.cp.SSHCpClient` instead of
    duplicating its (changing) layout assumptions.
    """
    probe = cachedir / "files" / "base" / "_master_cachedir_probe"
    res = salt_ssh_cli_parameterized.run(
        "cp.convert_cache_path", str(probe), master=True
    )
    assert res.returncode == 0
    assert isinstance(res.data, str)
    # convert_cache_path returns <master_root>/salt-ssh/<id>/files/base/_probe...
    # strip ``files/base/_master_cachedir_probe`` to get the per-target root.
    return Path(res.data).parent.parent.parent


def _convert(cachedir, master_cachedir, path, master=False):
    if not isinstance(path, Path):
        path = Path(path)
    if master:
        if master_cachedir in path.parents:
            return path
        return master_cachedir / path.relative_to(cachedir)
    if master_cachedir not in path.parents:
        return path
    return cachedir / path.relative_to(master_cachedir)


@pytest.mark.parametrize("template", (None, "jinja"))
@pytest.mark.parametrize("dst_is_dir", (False, True))
def test_get_file(
    salt_ssh_cli_parameterized, tmp_path, template, dst_is_dir, master_cachedir
):
    src = "salt://" + ("cheese" if not template else "{{pillar.test_pillar}}")
    if dst_is_dir:
        tgt = tmp_path
    else:
        tgt = tmp_path / ("cheese" if not template else "{{pillar.test_pillar}}")
    res = salt_ssh_cli_parameterized.run(
        "cp.get_file", src, str(tgt), template=template
    )
    assert res.returncode == 0
    assert res.data
    tgt = tmp_path / "cheese"
    assert res.data == str(tgt)
    master_path = master_cachedir / "files" / "base" / "cheese"
    for path in (tgt, master_path):
        assert path.exists()
        data = path.read_text(encoding="utf-8")
        assert "Gromit" in data
        assert "bacon" not in data


def test_get_file_gzipped(salt_ssh_cli_parameterized, caplog, tmp_path):
    tgt = tmp_path / random_string("foo-")
    res = salt_ssh_cli_parameterized.run(
        "cp.get_file", "salt://grail/scene33", str(tgt), gzip=5
    )
    assert res.returncode == 0
    assert res.data
    assert res.data == str(tgt)
    assert "The gzip argument to cp.get_file in salt-ssh is unsupported" in caplog.text
    assert tgt.exists()
    data = tgt.read_text(encoding="utf-8")
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


def test_get_file_makedirs(salt_ssh_cli_parameterized, tmp_path, master_cachedir):
    tgt = tmp_path / "make" / "dirs" / "scene33"
    res = salt_ssh_cli_parameterized.run(
        "cp.get_file", "salt://grail/scene33", str(tgt), makedirs=True
    )
    assert res.returncode == 0
    assert res.data
    assert res.data == str(tgt)
    master_path = master_cachedir / "files" / "base" / "grail" / "scene33"
    for path in (tgt, master_path):
        assert path.exists()
        data = path.read_text(encoding="utf-8")
        assert "KNIGHT:  They're nervous, sire." in data
        assert "bacon" not in data


@pytest.mark.parametrize("suffix", ("", "?saltenv=prod"))
def test_get_file_from_env(salt_ssh_cli_parameterized, tmp_path, suffix):
    tgt = tmp_path / "cheese"
    ret = salt_ssh_cli_parameterized.run(
        "cp.get_file", "salt://cheese" + suffix, str(tgt)
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == str(tgt)
    data = tgt.read_text(encoding="utf-8")
    assert "Gromit" in data
    assert ("Comte" in data) is bool(suffix)


def test_get_file_nonexistent_source(salt_ssh_cli_parameterized):
    res = salt_ssh_cli_parameterized.run(
        "cp.get_file", "salt://grail/nonexistent_scene", ""
    )
    assert res.returncode == 0  # not a fan of this
    assert res.data == ""


def test_envs(salt_ssh_cli_parameterized):
    ret = salt_ssh_cli_parameterized.run("cp.envs")
    assert ret.returncode == 0
    assert ret.data
    assert isinstance(ret.data, list)
    assert sorted(ret.data) == sorted(["base", "prod"])


def test_get_template(salt_ssh_cli_parameterized, tmp_path, master_cachedir):
    tgt = tmp_path / "scene33"
    res = salt_ssh_cli_parameterized.run(
        "cp.get_template", "salt://grail/scene33", str(tgt), spam="bacon"
    )
    assert res.returncode == 0
    assert res.data
    assert res.data == str(tgt)
    master_path = master_cachedir / "extrn_files" / "base" / "grail" / "scene33"
    for path in (tgt, master_path):
        assert tgt.exists()
        data = tgt.read_text(encoding="utf-8")
        assert "bacon" in data
        assert "spam" not in data


def test_get_template_dest_empty(salt_ssh_cli_parameterized, cachedir, master_cachedir):
    res = salt_ssh_cli_parameterized.run(
        "cp.get_template", "salt://grail/scene33", "", spam="bacon"
    )
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, str)
    master_path = master_cachedir / "extrn_files" / "base" / "grail" / "scene33"
    tgt = _convert(cachedir, master_cachedir, master_path)
    assert res.data == str(tgt)
    for file in (tgt, master_path):
        assert file.exists()
        data = file.read_text(encoding="utf-8")
        assert "bacon" in data
        assert "spam" not in data


def test_get_template_nonexistent_source(salt_ssh_cli_parameterized, tmp_path):
    res = salt_ssh_cli_parameterized.run(
        "cp.get_template", "salt://grail/nonexistent_scene", ""
    )
    assert res.returncode == 0  # not a fan of this
    assert res.data == ""
    # The regular module only logs "unable to fetch" with get_url


@pytest.mark.parametrize("template", (None, "jinja"))
@pytest.mark.parametrize("suffix", ("", "/"))
def test_get_dir(
    salt_ssh_cli_parameterized, tmp_path, template, suffix, master_cachedir
):
    tgt = tmp_path / ("many" if not template else "{{pillar.alot}}")
    res = salt_ssh_cli_parameterized.run(
        "cp.get_dir",
        "salt://" + ("grail" if not template else "{{pillar.script}}"),
        str(tgt) + suffix,
        template=template,
    )
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, list)
    tgt = tmp_path / "many"
    master_path = master_cachedir / "files" / "base"
    for path in (tgt, master_path):
        assert path.exists()
        assert "grail" in os.listdir(path)
        assert "36" in os.listdir(path / "grail")
        assert "empty" in os.listdir(path / "grail")
        assert "scene" in os.listdir(path / "grail" / "36")
        if path == master_path:
            # otherwise we would include other cached files
            path = path / "grail"
            files = {str(master_path / Path(x).relative_to(tgt)) for x in res.data}
        else:
            files = set(res.data)
        # The regular cp.get_dir keeps superfluous path separators as well
        filelist = {
            str(x).replace(str(tgt), str(tgt) + suffix)
            for x in path.rglob("*")
            if not x.is_dir()
        }
        assert files == filelist


def test_get_dir_gzipped(salt_ssh_cli_parameterized, caplog, tmp_path):
    tgt = tmp_path / "many"
    res = salt_ssh_cli_parameterized.run("cp.get_dir", "salt://grail", tgt, gzip=5)
    assert "The gzip argument to cp.get_dir in salt-ssh is unsupported" in caplog.text
    assert res.returncode == 0
    assert res.data
    tgt = tmp_path / "many"
    assert isinstance(res.data, list)
    assert tgt.exists()
    assert "grail" in os.listdir(tgt)
    assert "36" in os.listdir(tgt / "grail")
    assert "empty" in os.listdir(tgt / "grail")
    assert "scene" in os.listdir(tgt / "grail" / "36")


def test_get_dir_nonexistent_source(salt_ssh_cli_parameterized, caplog):
    res = salt_ssh_cli_parameterized.run(
        "cp.get_dir", "salt://grail/non/ex/is/tent", ""
    )
    assert res.returncode == 0  # not a fan of this
    assert isinstance(res.data, list)
    assert not res.data


@pytest.mark.parametrize("dst_is_dir", (False, True))
def test_get_url(salt_ssh_cli_parameterized, tmp_path, dst_is_dir, master_cachedir):
    src = "salt://grail/scene33"
    if dst_is_dir:
        tgt = tmp_path
    else:
        tgt = tmp_path / "scene33"
    res = salt_ssh_cli_parameterized.run("cp.get_url", src, str(tgt))
    assert res.returncode == 0
    assert res.data
    tgt = tmp_path / "scene33"
    assert res.data == str(tgt)
    master_path = master_cachedir / "files" / "base" / "grail" / "scene33"
    for file in (tgt, master_path):
        assert file.exists()
        data = file.read_text(encoding="utf-8")
        assert "KNIGHT:  They're nervous, sire." in data
        assert "bacon" not in data


def test_get_url_makedirs(salt_ssh_cli_parameterized, tmp_path, master_cachedir):
    tgt = tmp_path / "make" / "dirs" / "scene33"
    res = salt_ssh_cli_parameterized.run(
        "cp.get_url", "salt://grail/scene33", str(tgt), makedirs=True
    )
    assert res.returncode == 0
    assert res.data
    assert res.data == str(tgt)
    master_path = master_cachedir / "files" / "base" / "grail" / "scene33"
    for file in (tgt, master_path):
        assert file.exists()
        data = file.read_text(encoding="utf-8")
        assert "KNIGHT:  They're nervous, sire." in data
        assert "bacon" not in data


def test_get_url_dest_empty(salt_ssh_cli_parameterized, cachedir, master_cachedir):
    """
    salt:// source and destination omitted, should still cache the file
    """
    res = salt_ssh_cli_parameterized.run("cp.get_url", "salt://grail/scene33")
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, str)
    master_path = master_cachedir / "files" / "base" / "grail" / "scene33"
    tgt = _convert(cachedir, master_cachedir, master_path)
    assert res.data == str(tgt)
    for file in (tgt, master_path):
        assert file.exists()
        data = file.read_text(encoding="utf-8")
        assert "KNIGHT:  They're nervous, sire." in data
        assert "bacon" not in data


def test_get_url_no_dest(salt_ssh_cli_parameterized):
    """
    salt:// source given and destination set as None, should return the data
    """
    res = salt_ssh_cli_parameterized.run("cp.get_url", "salt://grail/scene33", None)
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, str)
    assert "KNIGHT:  They're nervous, sire." in res.data
    assert "bacon" not in res.data


def test_get_url_nonexistent_source(salt_ssh_cli_parameterized, caplog):
    res = salt_ssh_cli_parameterized.run(
        "cp.get_url", "salt://grail/nonexistent_scene", None
    )
    assert res.returncode == 0  # not a fan of this
    assert res.data is False
    assert (
        "Unable to fetch file salt://grail/nonexistent_scene from saltenv base."
        in caplog.text
    )


def test_get_url_https(salt_ssh_cli_parameterized, tmp_path, master_cachedir):
    tgt = tmp_path / "index.html"
    res = salt_ssh_cli_parameterized.run(
        "cp.get_url", "https://saltproject.io/index.html", tgt
    )
    assert res.returncode == 0
    assert res.data
    assert res.data == str(tgt)
    master_path = (
        master_cachedir / "extrn_files" / "base" / "saltproject.io" / "index.html"
    )
    for path in (tgt, master_path):
        assert path.exists()
        data = path.read_text(encoding="utf-8")
        assert "Salt Project" in data


def test_get_url_https_dest_empty(
    salt_ssh_cli_parameterized, tmp_path, cachedir, master_cachedir
):
    """
    https:// source given and destination omitted, should still cache the file
    """
    res = salt_ssh_cli_parameterized.run(
        "cp.get_url", "https://saltproject.io/index.html"
    )
    assert res.returncode == 0
    assert res.data
    master_path = (
        master_cachedir / "extrn_files" / "base" / "saltproject.io" / "index.html"
    )
    tgt = _convert(cachedir, master_cachedir, master_path)
    assert res.data == str(tgt)
    for path in (tgt, master_path):
        assert path.exists()
        data = path.read_text(encoding="utf-8")
        assert "Salt Project" in data


def test_get_url_https_no_dest(salt_ssh_cli_parameterized):
    """
    https:// source given and destination set as None, should return the data
    """
    timeout = 500
    start = time.time()
    sleep = 5
    while time.time() - start <= timeout:
        res = salt_ssh_cli_parameterized.run(
            "cp.get_url", "https://saltproject.io/index.html", None
        )
        if isinstance(res.data, str) and res.data.find("HTTP 599") == -1:
            break
        time.sleep(sleep)
    if isinstance(res.data, str) and res.data.find("HTTP 599") != -1:
        raise Exception("https://saltproject.io/index.html returned 599 error")
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, str)
    assert "Salt Project" in res.data


@pytest.mark.parametrize("scheme", ("file://", ""))
@pytest.mark.parametrize(
    "path,expected",
    (
        (Path(RUNTIME_VARS.FILES) / "file" / "base" / "file.big", True),
        (Path("_foo", "bar", "baz"), False),
    ),
)
def test_get_url_file(salt_ssh_cli_parameterized, path, expected, scheme):
    """
    Ensure the file:// scheme is not supported
    """
    res = salt_ssh_cli_parameterized.run("cp.get_url", scheme + str(path))
    assert res.returncode == 0
    assert res.data is False


def test_get_url_file_contents(salt_ssh_cli_parameterized, tmp_path, caplog):
    """
    A file:// source is not supported since it would need to fetch
    a file from the minion onto the master to be consistent
    """
    src = Path(RUNTIME_VARS.FILES) / "file" / "base" / "file.big"
    res = salt_ssh_cli_parameterized.run("cp.get_url", "file://" + str(src), None)
    assert res.returncode == 0
    assert res.data is False
    assert (
        "The file:// scheme is not supported via the salt-ssh cp wrapper" in caplog.text
    )


@pytest.mark.timeout(300)  # FTP can be slow, allow 5 minutes
def test_get_url_ftp(salt_ssh_cli_parameterized, tmp_path, master_cachedir):
    tgt = tmp_path / "README.TXT"
    res = salt_ssh_cli_parameterized.run(
        "cp.get_url", "ftp://ftp.freebsd.org/pub/FreeBSD/releases/amd64/README.TXT", tgt
    )
    assert res.returncode == 0
    assert res.data
    assert res.data == str(tgt)
    master_path = (
        master_cachedir
        / "extrn_files"
        / "base"
        / "ftp.freebsd.org"
        / "pub"
        / "FreeBSD"
        / "releases"
        / "amd64"
        / "README.TXT"
    )
    for path in (tgt, master_path):
        assert path.exists()
        data = path.read_text(encoding="utf-8")
        assert "The official FreeBSD" in data


def test_get_file_str_salt(salt_ssh_cli_parameterized, cachedir, master_cachedir):
    src = "salt://grail/scene33"
    res = salt_ssh_cli_parameterized.run("cp.get_file_str", src)
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, str)
    assert "KNIGHT:  They're nervous, sire." in res.data
    tgt = cachedir / "files" / "base" / "grail" / "scene33"
    master_path = _convert(cachedir, master_cachedir, tgt, master=True)
    for path in (tgt, master_path):
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "KNIGHT:  They're nervous, sire." in text


def test_get_file_str_nonexistent_source(salt_ssh_cli_parameterized, caplog):
    src = "salt://grail/nonexistent_scene"
    res = salt_ssh_cli_parameterized.run("cp.get_file_str", src)
    assert res.returncode == 0  # yup...
    assert res.data is False


def test_get_file_str_https(salt_ssh_cli_parameterized, cachedir, master_cachedir):
    src = "https://saltproject.io/index.html"
    res = salt_ssh_cli_parameterized.run("cp.get_file_str", src)
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, str)
    assert "Salt Project" in res.data
    tgt = cachedir / "extrn_files" / "base" / "saltproject.io" / "index.html"
    master_path = _convert(cachedir, master_cachedir, tgt, master=True)
    for path in (tgt, master_path):
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "Salt Project" in text


def test_get_file_str_local(salt_ssh_cli_parameterized, cachedir, caplog):
    src = Path(RUNTIME_VARS.FILES) / "file" / "base" / "cheese"
    res = salt_ssh_cli_parameterized.run("cp.get_file_str", "file://" + str(src))
    assert res.returncode == 0
    assert isinstance(res.data, str)
    assert "Gromit" in res.data
    assert (
        "The file:// scheme is not supported via the salt-ssh cp wrapper"
        not in caplog.text
    )


@pytest.mark.parametrize("suffix", ("", "?saltenv=prod"))
def test_cache_file(salt_ssh_cli_parameterized, suffix, cachedir, master_cachedir):
    res = salt_ssh_cli_parameterized.run("cp.cache_file", "salt://cheese" + suffix)
    assert res.returncode == 0
    assert res.data
    tgt = (
        cachedir
        / "files"
        / ("base" if "saltenv" not in suffix else suffix.split("=")[1])
        / "cheese"
    )
    master_path = _convert(cachedir, master_cachedir, tgt, master=True)
    for file in (tgt, master_path):
        data = file.read_text(encoding="utf-8")
        assert "Gromit" in data
        assert ("Comte" in data) is bool(suffix)


@pytest.fixture
def _cache_twice(
    salt_master, request, salt_ssh_cli_parameterized, cachedir, master_cachedir
):

    # ensure the cache is clean
    tgt = cachedir / "extrn_files" / "base" / "saltproject.io" / "index.html"
    tgt.unlink(missing_ok=True)
    master_tgt = _convert(cachedir, master_cachedir, tgt, master=True)
    master_tgt.unlink(missing_ok=True)

    # create a template that will cause a file to get cached twice
    # within the same context
    name = "cp_cache"
    src = "https://saltproject.io/index.html"
    remove = getattr(request, "param", False)
    contents = f"""
{{%- set cache = salt["cp.cache_file"]("{src}") %}}
{{%- if not cache %}}
{{#-   Stop rendering. It's one of the only ways to throw an exception
       during master-side rendering currently (in order to fail it).
#}}
{{%-   do salt["cp.get_file"]("foobar", template="thisthrowsanexception") %}}
{{%- endif %}}
{{%- set master_cache = salt["cp.convert_cache_path"](cache, master=true) %}}
{{%- do salt["file.append"](cache, "\nwasmodifiedhahaha") %}}
{{%- do salt["file.append"](master_cache, "\nwasmodifiedhahaha") %}}
"""
    if remove:
        contents += f"""
{{%- do salt["file.remove"]({'master_cache' if remove == 'master' else 'cache'}) %}}"""
    contents += f"""
{{%- set res2 = salt["cp.cache_file"]("{src}") %}}
{{{{ res2 }}}}
    """
    with salt_master.state_tree.base.temp_file(name, contents):
        yield f"salt://{name}"


def test_cache_file_context_cache(
    salt_ssh_cli_parameterized, cachedir, master_cachedir, _cache_twice
):
    res = salt_ssh_cli_parameterized.run(
        "slsutil.renderer", _cache_twice, default_renderer="jinja"
    )
    assert res.returncode == 0
    tgt = res.data.strip()
    assert tgt
    tgt = Path(tgt)
    for file in (tgt, _convert(cachedir, master_cachedir, tgt, master=True)):
        assert tgt.exists()
        # If both files were present, they should not be re-fetched
        assert "wasmodifiedhahaha" in tgt.read_text(encoding="utf-8")


@pytest.mark.parametrize("_cache_twice", ("master", "minion"), indirect=True)
def test_cache_file_context_cache_requires_both_caches(
    salt_ssh_cli_parameterized, cachedir, master_cachedir, _cache_twice
):
    res = salt_ssh_cli_parameterized.run(
        "slsutil.renderer", _cache_twice, default_renderer="jinja"
    )
    assert res.returncode == 0
    tgt = res.data.strip()
    assert tgt
    tgt = Path(tgt)
    for file in (tgt, _convert(cachedir, master_cachedir, tgt, master=True)):
        assert tgt.exists()
        # If one of the files was removed, it should be re-fetched
        assert "wasmodifiedhahaha" not in tgt.read_text(encoding="utf-8")


def test_cache_file_nonexistent_source(salt_ssh_cli_parameterized):
    res = salt_ssh_cli_parameterized.run(
        "cp.get_template", "salt://grail/nonexistent_scene", ""
    )
    assert res.returncode == 0  # not a fan of this
    assert res.data == ""
    # The regular module only logs "unable to fetch" with get_url


@pytest.mark.parametrize(
    "files",
    (
        ["salt://grail/scene33", "salt://grail/36/scene"],
        "salt://grail/scene33,salt://grail/36/scene",
    ),
)
def test_cache_files(salt_ssh_cli_parameterized, files):
    res = salt_ssh_cli_parameterized.run("cp.cache_files", files)
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, list)
    for path in res.data:
        assert isinstance(path, str)
        path = Path(path)
        assert path.exists()
        data = Path(path).read_text(encoding="utf-8")
        assert "ARTHUR:" in data
        assert "bacon" not in data


def test_cache_dir(salt_ssh_cli_parameterized, cachedir, master_cachedir):
    res = salt_ssh_cli_parameterized.run("cp.cache_dir", "salt://grail")
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, list)
    tgt = cachedir / "files" / "base" / "grail"
    master_path = _convert(cachedir, master_cachedir, tgt, master=True)
    for path in (tgt, master_path):
        assert path.exists()
        assert "36" in os.listdir(path)
        assert "empty" in os.listdir(path)
        assert "scene" in os.listdir(path / "36")
        if path == master_path:
            files = {str(master_path / Path(x).relative_to(tgt)) for x in res.data}
        else:
            files = set(res.data)
        filelist = {str(x) for x in path.rglob("*") if not x.is_dir()}
        assert files == filelist


def test_cache_dir_nonexistent_source(salt_ssh_cli_parameterized, caplog):
    res = salt_ssh_cli_parameterized.run(
        "cp.cache_dir", "salt://grail/non/ex/is/tent", ""
    )
    assert res.returncode == 0  # not a fan of this
    assert isinstance(res.data, list)
    assert not res.data


def test_list_states(salt_master, salt_ssh_cli_parameterized, tmp_path):
    top_sls = """
    base:
      '*':
        - core
        """
    core_state = f"""
    {tmp_path / "testfile"}/testfile:
      file.managed:
        - source: salt://testfile
        - makedirs: true
        """

    with salt_master.state_tree.base.temp_file(
        "top.sls", top_sls
    ), salt_master.state_tree.base.temp_file("core.sls", core_state):
        res = salt_ssh_cli_parameterized.run(
            "cp.list_states",
        )
        assert res.returncode == 0
        assert res.data
        assert isinstance(res.data, list)
        assert "core" in res.data
        assert "top" in res.data
        assert "cheese" not in res.data


def test_list_master(salt_ssh_cli_parameterized):
    res = salt_ssh_cli_parameterized.run("cp.list_master")
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, list)
    for file in [
        "cheese",
        "grail/empty",
        "grail/36/scene",
        "_modules/salttest.py",
        "running.sls",
        "test_deep/a/test.sls",
    ]:
        assert file in res.data
    assert "test_deep/a" not in res.data


def test_list_master_dirs(salt_ssh_cli_parameterized):
    res = salt_ssh_cli_parameterized.run("cp.list_master_dirs")
    assert res.returncode == 0
    assert res.data
    assert isinstance(res.data, list)
    for path in ["test_deep", "test_deep/a", "test_deep/b/2"]:
        assert path in res.data
    for path in [
        "test_deep/test.sls",
        "test_deep/a/test.sls",
        "test_deep/b/2/test.sls",
        "cheese",
    ]:
        assert path not in res.data


def test_list_master_symlinks(salt_ssh_cli_parameterized, salt_master):
    if salt_ssh_cli_parameterized.config.get("fileserver_ignoresymlinks", False):
        pytest.skip("Fileserver is configured to ignore symlinks")
    with salt_master.state_tree.base.temp_file(random_string("foo-"), "") as tgt:
        sym = tgt.parent / random_string("test_list_master_symlinks-")
        try:
            sym.symlink_to(tgt)
            res = salt_ssh_cli_parameterized.run("cp.list_master_symlinks")
            assert res.returncode == 0
            assert res.data
            assert isinstance(res.data, dict)
            assert res.data
            assert sym.name in res.data
            assert res.data[sym.name] == str(tgt)
        finally:
            # Clean up the symlink to avoid conflicts with parametrized tests
            if sym.exists() or sym.is_symlink():
                sym.unlink()


@pytest.fixture(params=(False, "cached", "render_cached"))
def _is_cached(salt_ssh_cli_parameterized, suffix, request, cachedir, master_cachedir):
    remove = ["files", "extrn_files"]
    if request.param == "cached":
        ret = salt_ssh_cli_parameterized.run(
            "cp.cache_file", "salt://grail/scene33" + suffix
        )
        assert ret.returncode == 0
        assert ret.data
        remove.remove("files")
    elif request.param == "render_cached":
        ret = salt_ssh_cli_parameterized.run(
            "cp.get_template", "salt://grail/scene33" + suffix, "", spam="bacon"
        )
        assert ret.returncode == 0
        assert ret.data
        remove.remove("extrn_files")
    for basedir in remove:
        tgt = cachedir / basedir / "base" / "grail" / "scene33"
        tgt.unlink(missing_ok=True)
        master_tgt = _convert(cachedir, master_cachedir, tgt, master=True)
        master_tgt.unlink(missing_ok=True)
    return request.param


@pytest.mark.parametrize("suffix", ("", "?saltenv=base"))
def test_is_cached(salt_ssh_cli_parameterized, cachedir, _is_cached, suffix):
    """
    is_cached should find both cached files from the fileserver as well
    as cached rendered templates
    """
    if _is_cached == "render_cached":
        tgt = cachedir / "extrn_files" / "base" / "grail" / "scene33"
    else:
        tgt = cachedir / "files" / "base" / "grail" / "scene33"
    res = salt_ssh_cli_parameterized.run(
        "cp.is_cached", "salt://grail/scene33" + suffix
    )
    assert res.returncode == 0
    assert (res.data == str(tgt)) is bool(_is_cached)
    assert (res.data != "") is bool(_is_cached)


def test_is_cached_nonexistent(salt_ssh_cli_parameterized):
    res2 = salt_ssh_cli_parameterized.run("cp.is_cached", "salt://fasldkgj/poicxzbn")
    assert res2.returncode == 0
    assert res2.data == ""


@pytest.mark.parametrize("suffix", ("", "?saltenv=base"))
def test_hash_file(salt_ssh_cli_parameterized, cachedir, master_cachedir, suffix):
    res = salt_ssh_cli_parameterized.run(
        "cp.hash_file", "salt://grail/scene33" + suffix
    )
    assert res.returncode == 0
    assert res.data
    sha256_hash = res.data["hsum"]
    res = salt_ssh_cli_parameterized.run("cp.cache_file", "salt://grail/scene33")
    assert res.returncode == 0
    assert res.data
    master_path = _convert(cachedir, master_cachedir, res.data, master=True)
    assert master_path.exists()
    data = master_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == sha256_hash


def test_hash_file_local(salt_ssh_cli_parameterized, caplog):
    """
    Ensure that local files are run through ``salt-call`` on the target.
    We have to trust that this would otherwise fail because the tests
    run against localhost.
    """
    path = Path(RUNTIME_VARS.FILES) / "file" / "base" / "cheese"
    res = salt_ssh_cli_parameterized.run("cp.hash_file", str(path))
    assert res.returncode == 0
    # This would be logged if SSHCpClient was used instead of
    # performing a shimmed salt-call command
    assert "Hashing local files is not supported via salt-ssh" not in caplog.text
    assert isinstance(res.data, dict)
    assert res.data
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    sha256_hash = res.data["hsum"]
    assert digest == sha256_hash


@pytest.fixture
def state_tree_jinjaimport(tmp_path, salt_master):
    map_contents = """{%- set mapdata = {"foo": "bar"} %}"""
    managed_contents = """
        {%- from "my/map.jinja" import mapdata with context %}
        {{- mapdata["foo"] -}}
    """
    state_contents = f"""
{{%- do salt["cp.cache_file"]("salt://my/map.jinja") %}}

Serialize config:
  file.managed:
    - name: {tmp_path / "config.conf"}
    - source: salt://my/files/config.conf.j2
    - template: jinja
"""
    with salt_master.state_tree.base.temp_file(
        "my/file_managed_import.sls", state_contents
    ) as state, salt_master.state_tree.base.temp_file(
        "my/map.jinja", map_contents
    ), salt_master.state_tree.base.temp_file(
        "my/files/config.conf.j2", managed_contents
    ):
        yield f"my.{state.stem}"


def test_cp_cache_file_as_workaround_for_missing_map_file(
    salt_ssh_cli_parameterized, state_tree_jinjaimport, tmp_path
):
    tgt = tmp_path / "config.conf"
    ret = salt_ssh_cli_parameterized.run("state.sls", state_tree_jinjaimport)
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    assert tgt.exists()
    assert tgt.read_text(encoding="utf-8").strip() == "bar"
