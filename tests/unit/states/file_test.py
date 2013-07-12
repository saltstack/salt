# Import python libs
import json

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import third party libs
import yaml

try:
    from mock import MagicMock, patch
    has_mock = True
except ImportError:
    has_mock = False

if has_mock:
    import salt.states.file as filestate
    filestate.__salt__ = {
        'file.manage_file': False
    }
    filestate.__opts__ = {'test': False}


@skipIf(has_mock is False, 'mock python module is unavailable')
class TestFileState(TestCase):

    def test_serialize(self):
        def returner(contents, *args, **kwargs):
            returner.returned = contents
        returner.returned = None


        filestate.__salt__ = {
            'file.manage_file': returner
        }

        dataset = {
            "foo": True,
            "bar": 42,
            "baz": [1, 2, 3],
            "qux": 2.0
        }

        filestate.serialize('/tmp', dataset)
        self.assertEquals(yaml.load(returner.returned), dataset)

        filestate.serialize('/tmp', dataset, formatter="yaml")
        self.assertEquals(yaml.load(returner.returned), dataset)

        filestate.serialize('/tmp', dataset, formatter="json")
        self.assertEquals(json.loads(returner.returned), dataset)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestFileState, needs_daemon=False)
