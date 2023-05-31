"""test for pillar stack pillar"""

import pytest

import salt.pillar.stack as stack
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    loader_globals = {
        "__grains__": {"os": "Debian", "os_family": "Debian"},
        "__opts__": {"saltenv": "dev", "pillarenv": "dev"},
    }
    return {stack: loader_globals}


def mock_stack_pillar(mock_output, *args, **kwargs):
    # mock: jenv.get_template(filename).render(stack=stack)
    class MockJinja:
        def __call__(self, *args, **kwargs):
            return self

        render = MagicMock(side_effect=mock_output)

    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "jinja2.environment.Environment.get_template", MockJinja()
    ), patch("glob.glob", MagicMock(return_value=["/path/to/stack.cfg"])):
        result = stack.ext_pillar(  # (minion_id, pillar, *args, **kwargs)
            "minion_id", {}, *args, **kwargs
        )
        return result


def test_extpillar_stack1():

    mock_output = [
        "/path/to/filename.yml\n",  # mocked contents of /path/to/stack.cfg
        """
            foo: foo1 # jinja test
            bar: bar1
        """,  # mocked contents of filename.yml
    ]
    fake_dict = {"foo": "foo1", "bar": "bar1"}

    # config with a single file
    result = mock_stack_pillar(mock_output, "/path/to/stack.cfg")
    assert fake_dict == result

    # config with a opts:saltenv
    result = mock_stack_pillar(
        mock_output,
        **{
            "opts:saltenv": {  # **kwargs
                "dev": "/path/to/dev/static.cfg",
            }
        }
    )
    assert fake_dict == result

    # config with a opts:saltenv and __env__ substitution
    result = mock_stack_pillar(
        mock_output,
        **{
            "opts:saltenv": {  # **kwargs
                "__env__": "/path/to/__env__/dynamic.cfg",
            }
        }
    )
    assert fake_dict == result


def test_extpillar_stack_exceptions():

    # yaml indentation error
    mock_output = [
        "/path/to/filename.yml\n",  # mocked contents of /path/to/stack.cfg
        """
                foo: foo1
            bar: bar1  # yaml indentation error
        """,  # mocked contents of filename.yml
    ]
    pytest.raises(Exception, mock_stack_pillar, mock_output, "/path/to/stack.cfg")
