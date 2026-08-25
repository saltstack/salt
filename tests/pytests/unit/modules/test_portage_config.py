"""
    :codeauthor: Ryan Lewis (ryansname@gmail.com)

    pytest.unit.modules.portage_flags
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import pytest

import salt.modules.portage_config as portage_config
import salt.utils.files
from tests.support.mock import patch

pytest.importorskip("portage", reason="System is not gentoo/funtoo.")


def setup_loader_modules():
    return {}


def test_get_config_file_wildcards():
    pairs = [
        ("*/*::repo", "/etc/portage/package.mask/repo"),
        ("*/pkg::repo", "/etc/portage/package.mask/pkg"),
        ("cat/*", "/etc/portage/package.mask/cat_"),
        ("cat/pkg", "/etc/portage/package.mask/cat/pkg"),
        ("cat/pkg::repo", "/etc/portage/package.mask/cat/pkg"),
    ]

    for atom, expected in pairs:
        assert portage_config._get_config_file("mask", atom) == expected


def test_enforce_nice_config(tmp_path):
    atoms = [
        ("*/*::repo", "repo"),
        ("*/pkg1::repo", "pkg1"),
        ("cat/*", "cat_"),
        ("cat/pkg2", "cat/pkg2"),
        ("cat/pkg3::repo", "cat/pkg3"),
        ("<cat/pkg4-0.0.0.0", "cat/pkg4"),
        (">cat/pkg5-0.0.0.0:0", "cat/pkg5"),
        (">cat/pkg6-0.0.0.0:0::repo", "cat/pkg6"),
        ("<=cat/pkg7-0.0.0.0", "cat/pkg7"),
        ("=cat/pkg8-0.0.0.0", "cat/pkg8"),
    ]

    supported = [
        ("accept_keywords", ["~amd64"]),
        ("env", ["glibc.conf"]),
        ("license", ["LICENCE1", "LICENCE2"]),
        ("mask", [""]),
        ("properties", ["* -interactive"]),
        ("unmask", [""]),
        ("use", ["apple", "-banana", "ananas", "orange"]),
    ]

    base_path = str(tmp_path / "/package.{0}")

    def make_line(atom, addition):
        return atom + (" " + addition if addition != "" else "") + "\n"

    for typ, additions in supported:
        path = base_path.format(typ)
        with salt.utils.files.fopen(path, "a") as fh:
            for atom, _ in atoms:
                for addition in additions:
                    line = make_line(atom, addition)
                    fh.write("# comment for: " + line)
                    fh.write(line)

    with patch.object(portage_config, "BASE_PATH", base_path):
        with patch.object(
            portage_config, "_merge_flags", lambda l1, l2, _: list(set(l1 + l2))
        ):
            portage_config.enforce_nice_config()

    for typ, additions in supported:
        for atom, file_name in atoms:
            with salt.utils.files.fopen(
                base_path.format(typ) + "/" + file_name, "r"
            ) as fh:
                for line in fh:
                    for atom in line:
                        assert atom not in line
                    for addition in additions:
                        assert addition not in line
