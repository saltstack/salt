# -*- coding: utf-8 -*-
"""
    :codeauthor: Ryan Lewis (ryansname@gmail.com)

    tests.unit.modules.portage_flags
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import re

# Import salt libs
import salt.modules.portage_config as portage_config
import salt.utils.files
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class PortageConfigTestCase(TestCase, LoaderModuleMockMixin):
    class DummyAtom(object):
        def __init__(self):
            self.cp = None
            self.repo = None

        def __call__(self, atom, *_, **__):
            if atom == "#" or isinstance(atom, MagicMock):
                self.repo = None
                self.cp = None
                return self

            # extract (and remove) repo
            atom, self.repo = atom.split("::") if "::" in atom else (atom, None)

            # remove '>, >=, <=, =, ~' etc.
            atom = re.sub(r"[<>~+=]", "", atom)
            # remove slots
            atom = re.sub(r":[0-9][^:]*", "", atom)
            # remove version
            atom = re.sub(r"-[0-9][\.0-9]*", "", atom)

            self.cp = atom
            return self

    def setup_loader_modules(self):
        try:
            import portage  # pylint: disable=unused-import

            return {}
        except ImportError:
            dummy_atom = self.DummyAtom()
            self.portage = MagicMock()
            self.portage.dep.Atom = MagicMock(side_effect=dummy_atom)
            self.portage.dep_getkey = MagicMock(side_effect=lambda x: dummy_atom(x).cp)
            self.portage.exception.InvalidAtom = Exception
            self.addCleanup(delattr, self, "portage")
            return {portage_config: {"portage": self.portage}}

    def test_get_config_file_wildcards(self):
        pairs = [
            ("*/*::repo", "/etc/portage/package.mask/repo"),
            ("*/pkg::repo", "/etc/portage/package.mask/pkg"),
            ("cat/*", "/etc/portage/package.mask/cat_"),
            ("cat/pkg", "/etc/portage/package.mask/cat/pkg"),
            ("cat/pkg::repo", "/etc/portage/package.mask/cat/pkg"),
        ]

        for (atom, expected) in pairs:
            self.assertEqual(portage_config._get_config_file("mask", atom), expected)

    def test_enforce_nice_config(self):
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

        base_path = RUNTIME_VARS.TMP + "/package.{0}"

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
                        self.assertTrue(
                            atom in line, msg="'{}' not in '{}'".format(addition, line)
                        )
                        for addition in additions:
                            self.assertTrue(
                                addition in line,
                                msg="'{}' not in '{}'".format(addition, line),
                            )
