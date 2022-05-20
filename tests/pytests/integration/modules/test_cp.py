import hashlib
import logging
import os
import pathlib
import signal
import textwrap
import time
import uuid

import psutil  # pylint: disable=3rd-party-module-not-gated
import pytest
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from saltfactories.utils.ports import get_unused_localhost_port
from saltfactories.utils.tempfiles import temp_file
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@pytest.mark.slow_test
def test_get_file(tmp_path, salt_cli, salt_minion):
    """
    cp.get_file
    """
    tgt = str(tmp_path / "test_get_file")
    salt_cli.run("cp.get_file", "salt://grail/scene33", tgt, minion_tgt=salt_minion.id)
    with salt.utils.files.fopen(tgt, "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_get_file_to_dir(tmp_path, salt_cli, salt_minion):
    """
    cp.get_file
    """
    tgt = tmp_path
    salt_cli.run(
        "cp.get_file", "salt://grail/scene33", str(tgt), minion_tgt=salt_minion.id
    )
    with salt.utils.files.fopen(str(tgt / "scene33"), "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@skipIf(
    salt.utils.platform.is_windows(),
    "This test hangs on Windows on Py3",
)
def test_get_file_templated_paths(tmp_path, salt_cli, salt_minion):
    """
    cp.get_file
    """
    tgt = str(tmp_path / "cheese")
    salt_cli.run(
        "cp.get_file",
        "salt://{{grains.test_grain}}",
        tgt.replace("cheese", "{{grains.test_grain}}"),
        template="jinja",
        minion_tgt=salt_minion.id,
    )
    with salt.utils.files.fopen(tgt, "r") as cheese:
        data = salt.utils.stringutils.to_unicode(cheese.read())
    assert "Gromit" in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_get_file_gzipped(tmp_path, salt_cli, salt_minion):
    """
    cp.get_file
    """
    tgt = str(tmp_path / "gzipped")
    src = os.path.join(RUNTIME_VARS.FILES, "file", "base", "file.big")
    with salt.utils.files.fopen(src, "rb") as fp_:
        hash_str = hashlib.md5(fp_.read()).hexdigest()

    salt_cli.run(
        "cp.get_file", "salt://file.big", tgt, gzip=5, minion_tgt=salt_minion.id
    )
    with salt.utils.files.fopen(tgt, "rb") as scene:
        data = scene.read()
    assert hash_str == hashlib.md5(data).hexdigest()
    data = salt.utils.stringutils.to_unicode(data)
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_get_file_makedirs(tmp_path, salt_cli, salt_minion):
    """
    cp.get_file
    """
    tgt = tmp_path / "make" / "dirs" / "scene33"
    salt_cli.run(
        "cp.get_file",
        "salt://grail/scene33",
        tgt,
        makedirs=True,
        minion_tgt=salt_minion.id,
    )
    with salt.utils.files.fopen(tgt, "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_get_template(tmp_path, salt_cli, salt_minion):
    """
    cp.get_template
    """
    tgt = str(tmp_path / "template")
    salt_cli.run(
        "cp.get_template",
        "salt://grail/scene33",
        tgt,
        spam="bacon",
        minion_tgt=salt_minion.id,
    )
    with salt.utils.files.fopen(tgt, "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "bacon" in data
    assert "spam" not in data


@pytest.mark.slow_test
def test_get_dir(tmp_path, salt_cli, salt_minion):
    """
    cp.get_dir
    """
    tgt = tmp_path / "many"
    salt_cli.run("cp.get_dir", "salt://grail", str(tgt), minion_tgt=salt_minion.id)
    assert "grail" in os.listdir(tgt)
    assert "36", os.listdir(str(tgt / "grail"))
    assert "empty", os.listdir(str(tgt / "grail"))
    assert "scene", os.listdir(str(tgt / "grail" / "36"))


@pytest.mark.slow_test
def test_get_dir_templated_paths(tmp_path, salt_cli, salt_minion):
    """
    cp.get_dir
    """
    tgt = tmp_path / "many"
    test = salt_cli.run(
        "cp.get_dir",
        "salt://{{grains.script}}",
        str(tgt).replace("many", "{{grains.alot}}"),
        template="jinja",
        minion_tgt=salt_minion.id,
    )
    assert "grail" in os.listdir(str(tgt))
    assert "36" in os.listdir(str(tgt / "grail"))
    assert "empty" in os.listdir(str(tgt / "grail"))
    assert "scene" in os.listdir(str(tgt / "grail" / "36"))


# cp.get_url tests


@pytest.mark.slow_test
def test_get_url(tmp_path, salt_cli, salt_minion):
    """
    cp.get_url with salt:// source given
    """
    tgt = str(tmp_path / "get_url")
    salt_cli.run("cp.get_url", "salt://grail/scene33", tgt, minion_tgt=salt_minion.id)
    with salt.utils.files.fopen(tgt, "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_get_url_makedirs(tmp_path, salt_cli, salt_minion):
    """
    cp.get_url
    """
    tgt = tmp_path / "make" / "dirs" / "scene33"
    salt_cli.run(
        "cp.get_url",
        "salt://grail/scene33",
        tgt,
        makedirs=True,
        minion_tgt=salt_minion.id,
    )
    with salt.utils.files.fopen(tgt, "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_get_url_dest_empty(salt_cli, salt_minion):
    """
    cp.get_url with salt:// source given and destination omitted.
    """
    ret = salt_cli.run("cp.get_url", "salt://grail/scene33", minion_tgt=salt_minion.id)
    with salt.utils.files.fopen(ret.json, "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_get_url_no_dest(salt_cli, salt_minion):
    """
    cp.get_url with salt:// source given and destination set as None
    """
    tgt = None
    ret = salt_cli.run(
        "cp.get_url", "salt://grail/scene33", tgt, minion_tgt=salt_minion.id
    )
    assert "KNIGHT:  They're nervous, sire." in ret.json


@pytest.mark.slow_test
def test_get_url_nonexistent_source(salt_cli, salt_minion):
    """
    cp.get_url with nonexistent salt:// source given
    """
    tgt = None
    ret = salt_cli.run(
        "cp.get_url", "salt://grail/nonexistent_scene", tgt, minion_tgt=salt_minion.id
    )
    assert ret.json is False


@pytest.mark.slow_test
def test_get_url_to_dir(tmp_path, salt_cli, salt_minion):
    """
    cp.get_url with salt:// source
    """
    tgt = tmp_path
    salt_cli.run(
        "cp.get_url", "salt://grail/scene33", str(tgt), minion_tgt=salt_minion.id
    )
    with salt.utils.files.fopen(tgt / "scene33", "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_get_url_https(tmp_path, salt_cli, salt_minion):
    """
    cp.get_url with https:// source given
    """
    tgt = str(tmp_path / "url_https")
    salt_cli.run(
        "cp.get_url",
        "https://repo.saltproject.io/index.html",
        tgt,
        minion_tgt=salt_minion.id,
    )
    with salt.utils.files.fopen(tgt, "r") as instructions:
        data = salt.utils.stringutils.to_unicode(instructions.read())
    assert "Bootstrap" in data
    assert "Debian" in data
    assert "Windows" in data
    assert "AYBABTU" not in data


@pytest.mark.slow_test
def test_get_url_https_dest_empty(salt_cli, salt_minion):
    """
    cp.get_url with https:// source given and destination omitted.
    """
    ret = salt_cli.run(
        "cp.get_url",
        "https://repo.saltproject.io/index.html",
        minion_tgt=salt_minion.id,
    )

    with salt.utils.files.fopen(ret.json, "r") as instructions:
        data = salt.utils.stringutils.to_unicode(instructions.read())
    assert "Bootstrap" in data
    assert "Debian" in data
    assert "Windows" in data
    assert "AYBABTU" not in data


@pytest.mark.slow_test
def test_get_url_https_no_dest(salt_cli, salt_minion):
    """
    cp.get_url with https:// source given and destination set as None
    """
    timeout = 500
    start = time.time()
    sleep = 5
    tgt = None
    while time.time() - start <= timeout:
        ret = salt_cli.run(
            "cp.get_url",
            "https://repo.saltproject.io/index.html",
            tgt,
            minion_tgt=salt_minion.id,
        )
        if ret.json.find("HTTP 599") == -1:
            break
        time.sleep(sleep)
    if ret.json.find("HTTP 599") != -1:
        raise Exception("https://repo.saltproject.io/index.html returned 599 error")
    assert "Bootstrap" in ret.json
    assert "Debian" in ret.json
    assert "Windows" in ret.json
    assert "AYBABTU" not in ret.json


@pytest.mark.slow_test
def test_get_url_file(salt_cli, salt_minion):
    """
    cp.get_url with file:// source given
    """
    tgt = ""
    src = os.path.join("file://", RUNTIME_VARS.FILES, "file", "base", "file.big")
    ret = salt_cli.run("cp.get_url", src, tgt, minion_tgt=salt_minion.id)
    with salt.utils.files.fopen(ret.json, "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_get_url_file_no_dest(salt_cli, salt_minion):
    """
    cp.get_url with file:// source given and destination set as None
    """
    tgt = None
    src = os.path.join("file://", RUNTIME_VARS.FILES, "file", "base", "file.big")
    ret = salt_cli.run("cp.get_url", src, tgt, minion_tgt=salt_minion.id)
    assert "KNIGHT:  They're nervous, sire." in ret.json
    assert "bacon" not in ret.json


@pytest.mark.slow_test
def test_get_url_ftp(tmp_path, ftpserver, salt_cli, salt_minion):
    """
    cp.get_url with https:// source given
    """
    test_data = "Test data"
    ftp_file = tmp_path / "ftp_data"
    with salt.utils.files.fopen(ftp_file, "w") as fp:
        fp.write(test_data)
    url = ftpserver.put_files(str(ftp_file), style="url", anon=True)
    tgt = str(tmp_path / "get_ftp")
    salt_cli.run("cp.get_url", url[0], tgt, minion_tgt=salt_minion.id)
    with salt.utils.files.fopen(tgt, "r") as instructions:
        data = salt.utils.stringutils.to_unicode(instructions.read())
    assert test_data in data


# cp.get_file_str tests


@pytest.mark.slow_test
def test_get_file_str_salt(salt_cli, salt_minion):
    """
    cp.get_file_str with salt:// source given
    """
    src = "salt://grail/scene33"
    ret = salt_cli.run("cp.get_file_str", src, minion_tgt=salt_minion.id)
    assert "KNIGHT:  They're nervous, sire." in ret.json


@pytest.mark.slow_test
def test_get_file_str_nonexistent_source(salt_cli, salt_minion):
    """
    cp.get_file_str with nonexistent salt:// source given
    """
    src = "salt://grail/nonexistent_scene"
    ret = salt_cli.run("cp.get_file_str", src, minion_tgt=salt_minion.id)
    assert ret.json is False


@pytest.mark.slow_test
def test_get_file_str_https(salt_cli, salt_minion):
    """
    cp.get_file_str with https:// source given
    """
    src = "https://repo.saltproject.io/index.html"
    ret = salt_cli.run("cp.get_file_str", src, minion_tgt=salt_minion.id)
    assert "Bootstrap" in ret.json
    assert "Debian" in ret.json
    assert "Windows" in ret.json
    assert "AYBABTU" not in ret.json


@pytest.mark.slow_test
def test_get_file_str_local(salt_cli, salt_minion):
    """
    cp.get_file_str with file:// source given
    """
    src = os.path.join("file://", RUNTIME_VARS.FILES, "file", "base", "file.big")
    ret = salt_cli.run("cp.get_file_str", src, minion_tgt=salt_minion.id)
    assert "KNIGHT:  They're nervous, sire." in ret.json
    assert "bacon" not in ret.json


# caching tests


@pytest.mark.slow_test
def test_cache_file(salt_cli, salt_minion):
    """
    cp.cache_file
    """
    ret = salt_cli.run(
        "cp.cache_file", "salt://grail/scene33", minion_tgt=salt_minion.id
    )
    with salt.utils.files.fopen(ret.json, "r") as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert "KNIGHT:  They're nervous, sire." in data
    assert "bacon" not in data


@pytest.mark.slow_test
def test_cache_files(salt_cli, salt_minion):
    """
    cp.cache_files
    """
    ret = salt_cli.run(
        "cp.cache_files",
        ["salt://grail/scene33", "salt://grail/36/scene"],
        minion_tgt=salt_minion.id,
    )
    for path in ret.json:
        with salt.utils.files.fopen(path, "r") as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert "ARTHUR:" in data
        assert "bacon" not in data


@pytest.mark.slow_test
def test_cache_master(tmp_path, salt_cli, salt_minion):
    """
    cp.cache_master
    """
    tgt = str(tmp_path / "cache_master")
    ret = salt_cli.run("cp.cache_master", tgt, minion_tgt=salt_minion.id)
    for path in ret.json:
        assert pathlib.Path(path).is_file()


@pytest.mark.slow_test
def test_cache_local_file(salt_cli, salt_minion):
    """
    cp.cache_local_file
    """
    src = os.path.join(RUNTIME_VARS.TMP, "random")
    with salt.utils.files.fopen(src, "w+") as fn_:
        fn_.write(salt.utils.stringutils.to_str("foo"))
    ret = salt_cli.run("cp.cache_local_file", src, minion_tgt=salt_minion.id)
    with salt.utils.files.fopen(ret.json, "r") as cp_:
        assert salt.utils.stringutils.to_unicode(cp_.read()) == "foo"


@pytest.fixture
def nginx_setup(tmp_path, salt_cli, salt_minion):
    nginx_port = get_unused_localhost_port()
    url_prefix = "http://localhost:{}/".format(nginx_port)
    nginx_root_dir = tmp_path / "root"
    nginx_conf_dir = tmp_path / "conf"
    nginx_conf = nginx_conf_dir / "nginx.conf"
    nginx_pidfile = nginx_conf_dir / "nginx.pid"
    file_contents = "Hello world!"

    for dirname in (nginx_root_dir, nginx_conf_dir):
        os.makedirs(dirname)

    # Write the temp file
    with salt.utils.files.fopen(
        os.path.join(nginx_root_dir, "actual_file"), "w"
    ) as fp_:
        fp_.write(salt.utils.stringutils.to_str(file_contents))

    # Write the nginx config
    with salt.utils.files.fopen(nginx_conf, "w") as fp_:
        fp_.write(
            textwrap.dedent(
                salt.utils.stringutils.to_str(
                    """\
            user root;
            worker_processes 1;
            error_log {nginx_conf_dir}/server_error.log;
            pid {nginx_pidfile};

            events {{
                worker_connections 1024;
            }}

            http {{
                include       /etc/nginx/mime.types;
                default_type  application/octet-stream;

                access_log {nginx_conf_dir}/access.log;
                error_log {nginx_conf_dir}/error.log;

                server {{
                    listen {nginx_port} default_server;
                    server_name cachefile.local;
                    root {nginx_root_dir};

                    location ~ ^/301$ {{
                        return 301 /actual_file;
                    }}

                    location ~ ^/302$ {{
                        return 302 /actual_file;
                    }}
                }}
            }}""".format(
                        nginx_conf_dir=str(nginx_conf_dir),
                        nginx_pidfile=str(nginx_pidfile),
                        nginx_port=nginx_port,
                        nginx_root_dir=str(nginx_root_dir),
                    )
                )
            )
        )

    test = salt_cli.run(
        "cmd.run",
        ["nginx", "-c", str(nginx_conf)],
        python_shell=False,
        minion_tgt=salt_minion.id,
    )
    yield {"url": url_prefix, "file_contents": file_contents}
    with salt.utils.files.fopen(str(nginx_pidfile)) as fp_:
        nginx_pid = int(fp_.read().strip())
        nginx_proc = psutil.Process(pid=nginx_pid)
        nginx_proc.send_signal(signal.SIGQUIT)


@skipIf(not salt.utils.path.which("nginx"), "nginx not installed")
@pytest.mark.slow_test
@pytest.mark.skip_if_not_root
def test_cache_remote_file(tmp_path, salt_cli, salt_minion, nginx_setup):
    """
    cp.cache_file
    """
    for code in ("", "301", "302"):
        url = nginx_setup["url"] + (code or "actual_file")
        log.debug("attempting to cache %s", url)
        ret = salt_cli.run("cp.cache_file", url, minion_tgt=salt_minion.id)
        assert ret
        with salt.utils.files.fopen(ret.json) as fp_:
            cached_contents = salt.utils.stringutils.to_unicode(fp_.read())
            assert cached_contents == nginx_setup["file_contents"]


@pytest.mark.slow_test
def test_list_states(tmp_path, salt_cli, salt_minion):
    """
    cp.list_states
    """
    top_sls = """
    base:
      '*':
        - core
        """

    core_state = """
    {}/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
        """.format(
        str(tmp_path)
    )

    with temp_file("top.sls", top_sls, RUNTIME_VARS.TMP_BASEENV_STATE_TREE), temp_file(
        "core.sls", core_state, RUNTIME_VARS.TMP_BASEENV_STATE_TREE
    ):
        ret = salt_cli.run("cp.list_states", minion_tgt=salt_minion.id)
        assert "core" in ret.json
        assert "top" in ret.json


@pytest.mark.slow_test
def test_list_minion(salt_cli, salt_minion):
    """
    cp.list_minion
    """
    salt_cli.run("cp.cache_file", "salt://grail/scene33", minion_tgt=salt_minion.id)
    ret = salt_cli.run("cp.list_minion", minion_tgt=salt_minion.id)
    found = False
    search = "grail/scene33"
    if salt.utils.platform.is_windows():
        search = r"grail\scene33"
    for path in ret.json:
        if search in path:
            found = True
            break
    assert found


@pytest.mark.slow_test
def test_is_cached(salt_cli, salt_minion):
    """
    cp.is_cached
    """
    salt_cli.run("cp.cache_file", "salt://grail/scene33", minion_tgt=salt_minion.id)
    ret1 = salt_cli.run(
        "cp.is_cached", "salt://grail/scene33", minion_tgt=salt_minion.id
    )
    assert ret1.json
    ret2 = salt_cli.run(
        "cp.is_cached", "salt://fasldkgj/poicxzbn", minion_tgt=salt_minion.id
    )
    assert not ret2.json


@pytest.mark.slow_test
def test_hash_file(salt_cli, salt_minion):
    """
    cp.hash_file
    """
    sha256_hash = salt_cli.run(
        "cp.hash_file", "salt://grail/scene33", minion_tgt=salt_minion.id
    )
    path = salt_cli.run(
        "cp.cache_file", "salt://grail/scene33", minion_tgt=salt_minion.id
    )
    with salt.utils.files.fopen(path.json, "rb") as fn_:
        data = fn_.read()
        assert sha256_hash.json["hsum"] == hashlib.sha256(data).hexdigest()


@pytest.mark.slow_test
def test_get_file_from_env_predefined(tmp_path, salt_cli, salt_minion):
    """
    cp.get_file
    """
    tgt = str(tmp_path / "cheese")
    salt_cli.run("cp.get_file", "salt://cheese", tgt, minion_tgt=salt_minion.id)
    with salt.utils.files.fopen(tgt, "r") as cheese:
        data = salt.utils.stringutils.to_unicode(cheese.read())
    assert "Gromit" in data
    assert "Comte" not in data


@pytest.mark.slow_test
def test_get_file_from_env_in_url(tmp_path, salt_cli, salt_minion):
    tgt = str(tmp_path / "cheese")
    salt_cli.run(
        "cp.get_file", "salt://cheese?saltenv=prod", tgt, minion_tgt=salt_minion.id
    )
    with salt.utils.files.fopen(tgt, "r") as cheese:
        data = salt.utils.stringutils.to_unicode(cheese.read())
    assert "Gromit" in data
    assert "Comte" in data


@pytest.mark.slow_test
def test_push(tmp_path, salt_cli, salt_minion):
    log_to_xfer = str(tmp_path / uuid.uuid4().hex)
    open(log_to_xfer, "w").close()  # pylint: disable=resource-leakage
    salt_cli.run("cp.push", log_to_xfer, minion_tgt=salt_minion.id)
    tgt_cache_file = str(
        tmp_path
        / "master-minion-root"
        / "cache"
        / "minions"
        / "minion"
        / "files"
        / tmp_path
        / log_to_xfer
    )
    assert os.path.isfile(tgt_cache_file)


@pytest.mark.slow_test
def test_envs(salt_cli, salt_minion):
    assert sorted(salt_cli.run("cp.envs", minion_tgt=salt_minion.id).json) == sorted(
        ["base", "prod"]
    )
