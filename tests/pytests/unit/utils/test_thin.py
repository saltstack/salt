import os
import copy

import jinja2
import pytest

import salt.exceptions
import salt.utils.hashutils
import salt.utils.stringutils
import salt.utils.thin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS


def _mock_popen(return_value=None, side_effect=None, returncode=0):
    proc = MagicMock()
    proc.communicate = MagicMock(return_value=return_value, side_effect=side_effect)
    proc.returncode = returncode
    popen = MagicMock(return_value=proc)
    return popen


def patch_if(condition, *args, **kwargs):
    """
    Return a patch decorator if the provided condition is met
    """
    if condition:
        return patch(*args, **kwargs)

    def inner(func):
        return func

    return inner


@patch(
    "salt.utils.thin.distro",
    type("distro", (), {"__file__": "/site-packages/distro"}),
)
@patch(
    "salt.utils.thin.salt",
    type("salt", (), {"__file__": "/site-packages/salt"}),
)
@patch(
    "salt.utils.thin.jinja2",
    type("jinja2", (), {"__file__": "/site-packages/jinja2"}),
)
@patch(
    "salt.utils.thin.yaml",
    type("yaml", (), {"__file__": "/site-packages/yaml"}),
)
@patch(
    "salt.utils.thin.tornado",
    type("tornado", (), {"__file__": "/site-packages/tornado"}),
)
@patch(
    "salt.utils.thin.msgpack",
    type("msgpack", (), {"__file__": "/site-packages/msgpack"}),
)
@patch(
    "salt.utils.thin.certifi",
    type("certifi", (), {"__file__": "/site-packages/certifi"}),
)
@patch(
    "salt.utils.thin.singledispatch",
    type("singledispatch", (), {"__file__": "/site-packages/sdp"}),
)
@patch(
    "salt.utils.thin.singledispatch_helpers",
    type("singledispatch_helpers", (), {"__file__": "/site-packages/sdp_hlp"}),
)
@patch(
    "salt.utils.thin.ssl_match_hostname",
    type("ssl_match_hostname", (), {"__file__": "/site-packages/ssl_mh"}),
)
@patch(
    "salt.utils.thin.markupsafe",
    type("markupsafe", (), {"__file__": "/site-packages/markupsafe"}),
)
@patch(
    "salt.utils.thin.backports_abc",
    type("backports_abc", (), {"__file__": "/site-packages/backports_abc"}),
)
@patch(
    "salt.utils.thin.concurrent",
    type("concurrent", (), {"__file__": "/site-packages/concurrent"}),
)
@patch(
    "salt.utils.thin.py_contextvars",
    type("contextvars", (), {"__file__": "/site-packages/contextvars"}),
)
@patch(
    "salt.utils.thin.packaging",
    type("packaging", (), {"__file__": "/site-packages/packaging"}),
)
@patch(
    "salt.utils.thin.looseversion",
    type("looseversion", (), {"__file__": "/site-packages/looseversion"}),
)
@patch_if(
    salt.utils.thin.has_immutables,
    "salt.utils.thin.immutables",
    type("immutables", (), {"__file__": "/site-packages/immutables"}),
)
@patch("salt.utils.thin.log", MagicMock())
def test_get_tops():
    """
    Test thin.get_tops to get extra-modules alongside the top directories, based on the interpreter.
    :return:
    """
    base_tops = [
        "distro",
        "salt",
        "jinja2",
        "yaml",
        "tornado",
        "msgpack",
        "certifi",
        "sdp",
        "sdp_hlp",
        "ssl_mh",
        "concurrent",
        "markupsafe",
        "backports_abc",
        "contextvars",
        "looseversion",
        "packaging",
        "foo.so",
        "bar.so",
    ]
    if salt.utils.thin.has_immutables:
        base_tops.extend(["immutables"])
    libs = salt.utils.thin.find_site_modules("contextvars")
    with patch("salt.utils.thin.find_site_modules", MagicMock(side_effect=[libs])):
        with patch(
            "builtins.__import__",
            MagicMock(
                side_effect=[
                    type("salt", (), {"__file__": "/custom/foo.so"}),
                    type("salt", (), {"__file__": "/custom/bar.so"}),
                ]
            ),
        ):
            tops = []
            for top in salt.utils.thin.get_tops(so_mods="foo,bar"):
                if top.find("/") != -1:
                    spl = "/"
                else:
                    spl = os.sep
                tops.append(top.rsplit(spl, 1)[-1])
    assert len(tops) == len(base_tops)
    assert sorted(tops) == sorted(base_tops)


@pytest.mark.parametrize("version", [[2, 7], [3, 0], [3, 7]])
def test_get_tops_python(version):
    """
    Tests 'distro' is only included when targeting
    python 3 in get_tops_python
    """
    python3 = False
    if tuple(version) >= (3, 0):
        python3 = True

    mods = ["jinja2"]
    if python3:
        mods.append("distro")

    popen_ret = tuple(salt.utils.stringutils.to_bytes(x) for x in ("", ""))
    mock_popen = _mock_popen(return_value=popen_ret)
    patch_proc = patch("salt.utils.thin.subprocess.Popen", mock_popen)
    patch_which = patch("salt.utils.path.which", return_value=True)

    with patch_proc, patch_which:
        salt.utils.thin.get_tops_python("python2", ext_py_ver=version)
        cmds = [x[0][0] for x in mock_popen.call_args_list]
        assert [x for x in cmds if "jinja2" in x[2]]
        if python3:
            assert [x for x in cmds if "distro" in x[2]]
        else:
            assert not [x for x in cmds if "distro" in x[2]]


@pytest.mark.parametrize("version", [[2, 7], [3, 0], [3, 7]])
def test_get_ext_tops(version):
    """
    Tests 'distro' is only included when targeting
    python 3 in get_ext_tops
    """
    python3 = False
    if tuple(version) >= (3, 0):
        python3 = True

    cfg = {
        "namespace": {
            "path": "/foo",
            "py-version": version,
            "dependencies": {
                "jinja2": "/jinja/foo.py",
                "yaml": "/yaml/",
                "tornado": "/tornado/tornado.py",
                "msgpack": "msgpack.py",
            },
        }
    }
    with patch("salt.utils.thin.os.path.isfile", MagicMock(return_value=True)):
        if python3:
            with pytest.raises(salt.exceptions.SaltSystemExit) as err:
                salt.utils.thin.get_ext_tops(cfg)
        else:
            ret = salt.utils.thin.get_ext_tops(cfg)

    if python3:
        assert "distro" in err.value.code
    else:
        assert not [x for x in ret["namespace"]["dependencies"] if "distro" in x]
        assert [x for x in ret["namespace"]["dependencies"] if "msgpack" in x]


def _tarfile(getinfo=False):
    """
    Fake tarfile handler.

    :return:
    """
    spec = ["add", "close"]
    if getinfo:
        spec.append("getinfo")

    tf = MagicMock()
    tf.open = MagicMock(return_value=MagicMock(spec=spec))

    return tf


def test_pack_alternatives():
    """
    test thin._pack_alternatives
    """
    jinja_fp = os.path.dirname(jinja2.__file__)
    ext_conf = {
        "test": {
            "py-version": [2, 7],
            "path": RUNTIME_VARS.SALT_CODE_DIR,
            "dependencies": [jinja_fp],
        }
    }
    tops = copy.deepcopy(ext_conf)
    digest = salt.utils.hashutils.DigestCollector()
    tar = _tarfile(None).open()
    exp_files = [
        os.path.join("salt", "payload.py"),
        os.path.join("jinja2", "__init__.py"),
    ]
    lib_root = os.path.join(RUNTIME_VARS.TMP, "fake-libs")

    with patch("salt.utils.thin.get_ext_tops", MagicMock(return_value=tops)):
        salt.utils.thin._pack_alternative(ext_conf, digest, tar)
        calls = tar.mock_calls
        for _file in exp_files:
            assert [x for x in calls if "{}".format(_file) in x[-2]]
            assert [
                x
                for x in calls
                if os.path.join("test", "pyall", _file) in x[-1]["arcname"]
            ]
