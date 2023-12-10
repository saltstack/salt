import salt.modules.freezer as freezer
from tests.support.mock import patch


def test_compare(states, temp_salt_minion, tmp_path):
    """
    Test freezer.compare
    """
    # Default options
    opts = temp_salt_minion.config.copy()

    # Set cachedir
    cachedir = tmp_path / "__salt_test_freezer_cache_dir/minion"
    opts["cachedir"] = str(cachedir)

    # Freeze data setup
    freezedir = cachedir / "freezer"
    old_pkg_file = str(freezedir / "pre_install-pkgs.yml")
    old_rep_file = str(freezedir / "pre_install-reps.yml")
    new_pkg_file = str(freezedir / "post_install-pkgs.yml")
    new_rep_file = str(freezedir / "post_install-reps.yml")

    old_reps = {
        "http://deb.debian.org/debian": [
            {
                "file": "/etc/apt/sources.list",
                "comps": ["main"],
                "disabled": False,
                "dist": "buster",
                "type": "deb",
                "uri": "http://deb.debian.org/debian",
                "line": "deb http://deb.debian.org/debian buster main",
                "architectures": [],
            }
        ]
    }
    new_reps = {
        "http://deb.debian.org/debian": [
            {
                "file": "/etc/apt/sources.list",
                "comps": ["main"],
                "disabled": False,
                "dist": "buster",
                "type": "deb",
                "uri": "http://deb.debian.org/debian",
                "line": "deb http://deb.debian.org/debian buster main",
                "architectures": [],
            }
        ],
        "http://security.debian.org/debian-security": [
            {
                "file": "/etc/apt/sources.list",
                "comps": ["main"],
                "disabled": False,
                "dist": "buster/updates",
                "type": "deb",
                "uri": "http://security.debian.org/debian-security",
                "line": "deb http://security.debian.org/debian-security buster/updates main",
                "architectures": [],
            }
        ],
    }
    old_pkgs = {"adduser": "3.118"}
    new_pkgs = {"adduser": "3.118", "consul": "1.11.1"}

    # Mock up freeze files
    states.file.serialize(
        name=old_pkg_file, dataset=old_pkgs, serializer="json", makedirs=True
    )
    states.file.serialize(
        name=new_pkg_file, dataset=new_pkgs, serializer="json", makedirs=True
    )
    states.file.serialize(
        name=old_rep_file, dataset=old_reps, serializer="json", makedirs=True
    )
    states.file.serialize(
        name=new_rep_file, dataset=new_reps, serializer="json", makedirs=True
    )

    # Compare
    with patch("salt.modules.freezer.__opts__", opts, create=True):
        ret = freezer.compare(old="pre_install", new="post_install")

    assert ret["pkgs"]["new"]["consul"] == "1.11.1"
    assert "old" not in ret["pkgs"]
    assert len(ret["repos"]["new"]) == 1
    assert "old" not in ret["repos"]
