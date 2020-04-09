# -*- coding: utf-8 -*-
"""
Pillar include tests
"""
from __future__ import absolute_import, unicode_literals

import pytest


@pytest.fixture(scope="module")
def create_pillar_tree():
    glob_include_fname = "glob_include.sls"
    glob_include_contents = """
    include:
      - 'glob_include*'
    """
    glob_include_a_fname = "glob_include_a.sls"
    glob_include_a_contents = """
    glob-a:
      - 'Entry A'
    """
    glob_include_b_fname = "glob_include_b.sls"
    glob_include_b_contents = """
    glob-b:
      - 'Entry B'
    """
    include_fname = "include.sls"
    include_contents = """
    include:
      - include-a:
          key: element:a
      - include-b:
          key: element:b
    """
    include_a_fname = "include-a.sls"
    include_a_contents = """
    a:
      - 'Entry A'
    """
    include_b_fname = "include-b.sls"
    include_b_contents = """
    b:
      - 'Entry B'
    """
    top_contents = """
    base:
      'minion':
        - include
        - glob_include
    """
    with pytest.helpers.temp_pillar_file(
        "top.sls", top_contents
    ), pytest.helpers.temp_pillar_file(
        glob_include_fname, glob_include_contents
    ), pytest.helpers.temp_pillar_file(
        glob_include_a_fname, glob_include_a_contents
    ), pytest.helpers.temp_pillar_file(
        glob_include_b_fname, glob_include_b_contents
    ), pytest.helpers.temp_pillar_file(
        include_fname, include_contents
    ), pytest.helpers.temp_pillar_file(
        include_a_fname, include_a_contents
    ), pytest.helpers.temp_pillar_file(
        include_b_fname, include_b_contents
    ):

        yield


@pytest.fixture(scope="module")
def pillar_items(salt_cli, create_pillar_tree):
    ret = salt_cli.run("pillar.items", minion_tgt="minion")
    assert ret.exitcode == 0, ret
    return ret.json


class TestPillarIncludeTest(object):
    def test_pillar_include(self, pillar_items):
        """
        Test pillar include
        """
        assert "a" in pillar_items["element"]
        assert pillar_items["element"]["a"] == {"a": ["Entry A"]}
        assert "b" in pillar_items["element"]
        assert pillar_items["element"]["b"] == {"b": ["Entry B"]}

    def test_pillar_glob_include(self, pillar_items):
        """
        Test pillar include via glob pattern
        """
        assert "glob-a" in pillar_items
        assert pillar_items["glob-a"] == ["Entry A"]
        assert "glob-b" in pillar_items
        assert pillar_items["glob-b"] == ["Entry B"]
