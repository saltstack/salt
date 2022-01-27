import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_jinja_renderer_argline(state, state_tree):
    """
    This is a test case for https://github.com/saltstack/salt/issues/55124
    """
    renderer_contents = """

    import salt.utils.stringio


    def render(gpg_data, saltenv="base", sls="", argline="", **kwargs):
        '''
        Renderer which returns the text value of the SLS file, instead of a
        StringIO object.
        '''
        if salt.utils.stringio.is_readable(gpg_data):
            return gpg_data.getvalue()
        else:
            return gpg_data
    """
    sls_contents = """
    #!issue55124|jinja -s|yaml

    'Who am I?':
      cmd.run:
        - name: echo {{ salt.cmd.run('whoami') }}
    """
    with state_tree.base.temp_file(
        "_renderers/issue51499.py", renderer_contents
    ), state_tree.base.temp_file("issue-55124.sls", sls_contents):
        ret = state.sls("issue-55124")
        for state_return in ret:
            assert state_return.result is True
