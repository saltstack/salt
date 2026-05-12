from textwrap import dedent

import pytest

pytest.importorskip("grp")

import grp

import salt.utils.user


@pytest.fixture(scope="function")
def etc_group(tmp_path):
    etcgrp = tmp_path / "etc" / "group"
    etcgrp.parent.mkdir()
    etcgrp.write_text(
        dedent(
            """games:x:50:
            docker:x:959:debian,salt
            salt:x:1000:"""
        )
    )
    return etcgrp


def test__getgrall(etc_group):
    group_lines = [
        ["games", "x", 50, []],
        ["docker", "x", 959, ["debian", "salt"]],
        ["salt", "x", 1000, []],
    ]
    expected_grall = [grp.struct_group(comps) for comps in group_lines]

    grall = salt.utils.user._getgrall(root=str(etc_group.parent.parent))

    assert grall == expected_grall


def test__getgrall_bad_format(etc_group):
    with etc_group.open("a") as _fp:
        _fp.write("\n# some comment here\n")

    with pytest.raises(IndexError):
        salt.utils.user._getgrall(root=str(etc_group.parent.parent))
