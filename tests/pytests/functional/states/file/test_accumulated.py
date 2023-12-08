import textwrap

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_issue_8343_accumulated_require_in(modules, tmp_path, state_tree):
    name = tmp_path / "testfile"
    sls_contents = f"""
    {name}:
      file.managed:
        - contents: |
                    #

    prepend-foo-accumulator-from-pillar:
      file.accumulated:
        - require_in:
          - file: prepend-foo-management
        - filename: {name}
        - text: |
                foo

    append-foo-accumulator-from-pillar:
      file.accumulated:
        - require_in:
          - file: append-foo-management
        - filename: {name}
        - text: |
                bar

    prepend-foo-management:
      file.blockreplace:
        - name: {name}
        - marker_start: "#-- start salt managed zonestart -- PLEASE, DO NOT EDIT"
        - marker_end: "#-- end salt managed zonestart --"
        - content: ''
        - prepend_if_not_found: True
        - backup: '.bak'
        - show_changes: True

    append-foo-management:
      file.blockreplace:
        - name: {name}
        - marker_start: "#-- start salt managed zoneend -- PLEASE, DO NOT EDIT"
        - marker_end: "#-- end salt managed zoneend --"
        - content: ''
        - append_if_not_found: True
        - backup: '.bak2'
        - show_changes: True
    """
    with pytest.helpers.temp_file(
        "issue-8343.sls", directory=state_tree, contents=sls_contents
    ):
        ret = modules.state.sls("issue-8343")
        for state_run in ret:
            assert state_run.result is True

    expected = textwrap.dedent(
        """\
    #-- start salt managed zonestart -- PLEASE, DO NOT EDIT
    foo
    #-- end salt managed zonestart --
    #
    #-- start salt managed zoneend -- PLEASE, DO NOT EDIT
    bar
    #-- end salt managed zoneend --
    """
    )

    assert name.read_text() == expected


def test_issue_11003_immutable_lazy_proxy_sum(modules, tmp_path, state_tree):
    # causes the Import-Module ServerManager error on Windows
    name = tmp_path / "testfile"
    sls_contents = f"""
    a{name}:
      file.absent:
        - name: {name}

    {name}:
      file.managed:
        - contents: |
                    #

    test-acc1:
      file.accumulated:
        - require_in:
          - file: final
        - filename: {name}
        - text: |
                bar

    test-acc2:
      file.accumulated:
        - watch_in:
          - file: final
        - filename: {name}
        - text: |
                baz

    final:
      file.blockreplace:
        - name: {name}
        - marker_start: "#-- start managed zone PLEASE, DO NOT EDIT"
        - marker_end: "#-- end managed zone"
        - content: ''
        - append_if_not_found: True
        - show_changes: True
    """
    with pytest.helpers.temp_file(
        "issue-11003.sls", directory=state_tree, contents=sls_contents
    ):
        ret = modules.state.sls("issue-11003")
        for state_run in ret:
            assert state_run.result is True

    contents = name.read_text().splitlines()
    begin = contents.index("#-- start managed zone PLEASE, DO NOT EDIT") + 1
    end = contents.index("#-- end managed zone")
    block_contents = contents[begin:end]
    for item in ("", "bar", "baz"):
        block_contents.remove(item)
    assert block_contents == []
