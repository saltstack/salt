"""test for pillar csvpillar.py"""

import salt.pillar.stack as stack
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class StackPillarTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        loader_globals = {
            "__grains__": {"os": "Debian", "os_family": "Debian"},
            "__opts__": {"saltenv": "dev", "pillarenv": "dev"},
        }
        return {stack: loader_globals}

    def mockStackPillar(self, mock_output, *args, **kwargs):
        # mock: jenv.get_template(filename).render(stack=stack)
        class mockJinja:
            def __call__(self, *args, **kwargs):
                return self

            render = MagicMock(side_effect=mock_output)

        with patch("os.path.isfile", MagicMock(return_value=True)), patch(
            "jinja2.environment.Environment.get_template", mockJinja()
        ), patch("glob.glob", MagicMock(return_value=["/path/to/stack.cfg"])):
            result = stack.ext_pillar(  # (minion_id, pillar, *args, **kwargs)
                "minion_id", {}, *args, **kwargs
            )
            return result

    def test_extpillar_stack1(self):

        mock_output = [
            "/path/to/filename.yml\n",  # mocked contents of /path/to/stack.cfg
            """
                foo: foo1 # jinja test
                bar: bar1
            """,  # mocked contents of filename.yml
        ]
        fake_dict = {"foo": "foo1", "bar": "bar1"}

        # config with a single file
        result = self.mockStackPillar(mock_output, "/path/to/stack.cfg")
        self.assertDictEqual(fake_dict, result)

        # config with a opts:saltenv
        result = self.mockStackPillar(
            mock_output,
            **{
                "opts:saltenv": {  # **kwargs
                    "dev": "/path/to/dev/static.cfg",
                }
            }
        )
        self.assertDictEqual(fake_dict, result)

        # config with a opts:saltenv and __env__ substitution
        result = self.mockStackPillar(
            mock_output,
            **{
                "opts:saltenv": {  # **kwargs
                    "__env__": "/path/to/__env__/dynamic.cfg",
                }
            }
        )
        self.assertDictEqual(fake_dict, result)

    def test_extpillar_stack_exceptions(self):

        # yaml indentation error
        mock_output = [
            "/path/to/filename.yml\n",  # mocked contents of /path/to/stack.cfg
            """
                foo: foo1
             bar: bar1  # yaml indentation error
            """,  # mocked contents of filename.yml
        ]
        self.assertRaises(
            Exception, self.mockStackPillar, mock_output, "/path/to/stack.cfg"
        )
