"""
Tests for the file state
"""
import logging

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def pillar_tree(salt_master, salt_minion, salt_call_cli):
    top_file = """
    base:
      '{}':
        - basic
    """.format(
        salt_minion.id
    )
    basic_pillar_file = """
    monty: python
    companions:
      three:
        - liz
        - jo
        - sarah jane
    """
    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    basic_tempfile = salt_master.pillar_tree.base.temp_file(
        "basic.sls", basic_pillar_file
    )

    try:
        with top_tempfile, basic_tempfile:
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
            assert ret.exitcode == 0
            assert ret.json is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.exitcode == 0
        assert ret.json is True


@pytest.mark.slow_test
def test_verify_ssl_skip_verify_false(
    salt_master, salt_call_cli, tmpdir, ssl_webserver
):
    """
    test verify_ssl when its False and True when managing
    a file with an https source and skip_verify is false.
    """
    web_file = ssl_webserver.url("this.txt")
    true_content = """
    test_verify_ssl:
      file.managed:
        - name: {}
        - source: {}
        - source_hash: {}
    """.format(
        tmpdir.join("test_verify_ssl_true.txt"), web_file, web_file + ".sha256"
    )

    false_content = true_content + "    - verify_ssl: False"

    # test when verify_ssl is True
    with salt_master.state_tree.base.temp_file(
        "verify_ssl.sls", true_content
    ) as sfpath:
        ret = salt_call_cli.run("--local", "state.apply", "verify_ssl")
        assert ret.exitcode == 1
        assert (
            "SSL: CERTIFICATE_VERIFY_FAILED"
            in ret.json[next(iter(ret.json))]["comment"]
        )

    # test when verify_ssl is False
    with salt_master.state_tree.base.temp_file(
        "verify_ssl.sls", false_content
    ) as sfpath:
        ret = salt_call_cli.run("--local", "state.apply", "verify_ssl")
        assert ret.exitcode == 0
        assert ret.json[next(iter(ret.json))]["changes"] == {
            "diff": "New file",
            "mode": "0644",
        }


@pytest.mark.windows_whitelisted
def test_contents_pillar_with_pillar_list(
    salt_master, salt_call_cli, pillar_tree, tmp_path
):
    """
    This tests for any regressions for this issue:
    https://github.com/saltstack/salt/issues/30934
    """
    target_path = tmp_path / "add-contents-pillar-target.txt"
    sls_name = "file-contents-pillar"
    sls_contents = """
    add_contents_pillar_sls:
      file.managed:
        - name: {}
        - contents_pillar: companions:three
    """.format(
        target_path
    )
    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )
    with sls_tempfile:
        ret = salt_call_cli.run("state.sls", sls_name)
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()


@pytest.mark.windows_whitelisted
def test_managed_file_with_pillar_sls(
    salt_master, salt_call_cli, pillar_tree, tmp_path
):
    """
    Test to ensure pillar data in sls file
    is rendered properly and file is created.
    """
    ret = salt_call_cli.run("pillar.get", "monty")
    assert ret.exitcode == 0
    assert ret.json

    target_path = tmp_path / "file-pillar-{}-target.txt".format(ret.json)
    sls_name = "file-pillar-get"
    sls_contents = (
        """
    {%- set filedir = '"""
        + str(tmp_path).replace("\\", "/")
        + """' %}
    {%- set filename = "file-pillar-{}-target.txt".format(salt["pillar.get"]("monty", "")) %}
    create-file:
      file.managed:
        - name: {{ filedir | path_join(filename) }}
    """
    )
    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )
    with sls_tempfile:
        ret = salt_call_cli.run("state.sls", sls_name)
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()


@pytest.mark.windows_whitelisted
def test_issue_50221(
    salt_master,
    salt_call_cli,
    pillar_tree,
    tmp_path,
    salt_minion,
    ext_pillar_file_tree_root_dir,
):
    expected_content = "abc\n\n\n"
    target_path = tmp_path / "issue-50221-target.txt"
    sls_name = "issue-50221"
    sls_contents = """
    {{ pillar["target-path"] }}:
      file.managed:
        - contents_pillar: issue-50221
    """
    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )
    issue_50221_ext_pillar_tempfile = pytest.helpers.temp_file(
        "issue-50221",
        expected_content,
        ext_pillar_file_tree_root_dir / "hosts" / salt_minion.id,
    )
    with sls_tempfile, issue_50221_ext_pillar_tempfile:
        ret = salt_call_cli.run("pillar.get", "issue-50221")
        assert ret.exitcode == 0
        assert ret.json
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert ret.json.replace("\r\n", "\n") == expected_content
        ret = salt_call_cli.run(
            "state.apply", sls_name, pillar={"target-path": str(target_path)}
        )
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert target_path.read_text().replace("\r\n", "\n") == expected_content


def test_issue_60426(
    salt_master,
    salt_call_cli,
    pillar_tree,
    tmp_path,
    salt_minion,
):
    target_path = tmp_path / "/etc/foo/bar"
    jinja_name = "foo_bar"
    jinja_contents = (
        "{% for item in accumulator['accumulated configstuff'] %}{{ item }}{% endfor %}"
    )

    sls_name = "issue-60426"
    sls_contents = """
    configuration file:
      file.managed:
        - name: {target_path}
        - source: salt://foo_bar.jinja
        - template: jinja
        - makedirs: True

    accumulated configstuff:
      file.accumulated:
        - filename: {target_path}
        - text:
          - some
          - good
          - stuff
        - watch_in:
          - configuration file
    """.format(
        target_path=target_path
    )

    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )

    jinja_tempfile = salt_master.state_tree.base.temp_file(
        "{}.jinja".format(jinja_name), jinja_contents
    )

    with sls_tempfile, jinja_tempfile:
        ret = salt_call_cli.run("state.apply", sls_name)
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert target_path.read_text() == "somegoodstuff"

    sls_name = "issue-60426"
    sls_contents = """
    configuration file:
      file.managed:
        - name: {target_path}
        - source: salt://foo_bar.jinja
        - template: jinja
        - makedirs: True

    accumulated configstuff:
      file.accumulated:
        - filename: {target_path}
        - text:
          - some
          - good
          - stuff
        - watch_in:
          - file: configuration file
    """.format(
        target_path=target_path
    )

    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )

    jinja_tempfile = salt_master.state_tree.base.temp_file(
        "{}.jinja".format(jinja_name), jinja_contents
    )

    with sls_tempfile, jinja_tempfile:
        ret = salt_call_cli.run("state.apply", sls_name)
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        # Check to make sure the file was created
        assert target_path.is_file()
        # The type of new line, ie, `\n` vs `\r\n` is not important
        assert target_path.read_text() == "somegoodstuff"


def test_issue_60203(
    salt_master,
    salt_call_cli,
    tmp_path,
    salt_minion,
):
    target_path = tmp_path / "issue-60203-target.txt"
    sls_name = "issue-60203"
    sls_contents = """
    credentials exposed via file:
      file.managed:
        - name: /tmp/test.tar.gz
        - source: 'https://account:dontshowme@notahost.saltstack.io/files/test.tar.gz'
        - source_hash: 'https://account:dontshowme@notahost.saltstack.io/files/test.tar.gz.sha256'
    """
    sls_tempfile = salt_master.state_tree.base.temp_file(
        "{}.sls".format(sls_name), sls_contents
    )
    with sls_tempfile:
        ret = salt_call_cli.run("state.apply", sls_name)
        assert ret.exitcode == 1
        assert ret.json
        assert (
            "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            in ret.json
        )
        assert (
            "comment"
            in ret.json[
                "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            ]
        )
        assert (
            "Unable to manage"
            in ret.json[
                "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            ]["comment"]
        )
        assert (
            "/files/test.tar.gz.sha256"
            in ret.json[
                "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            ]["comment"]
        )
        assert (
            "dontshowme"
            not in ret.json[
                "file_|-credentials exposed via file_|-/tmp/test.tar.gz_|-managed"
            ]["comment"]
        )
