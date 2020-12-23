import pytest
import salt.exceptions
import salt.utils.stringutils
import salt.utils.thin
from tests.support.mock import MagicMock, patch


def _mock_popen(return_value=None, side_effect=None, returncode=0):
    proc = MagicMock()
    proc.communicate = MagicMock(return_value=return_value, side_effect=side_effect)
    proc.returncode = returncode
    popen = MagicMock(return_value=proc)
    return popen


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
