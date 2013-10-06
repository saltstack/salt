# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')
ensure_in_syspath('../../')

# Import Salt libs
import salt.config
from salt.state import HighState


OPTS = salt.config.minion_config(None)
OPTS['id'] = 'match'
OPTS['file_client'] = 'local'
OPTS['file_roots'] = dict(base=['/tmp'])
OPTS['test'] = False
OPTS['grains'] = salt.loader.grains(OPTS)


class HighStateTestCase(TestCase):
    def setUp(self):
        self.highstate = HighState(OPTS)
        self.highstate.push_active()

    def tearDown(self):
        self.highstate.pop_active()

    def test_top_matches_with_list(self):
        top = {'env': {'match': ['state1', 'state2'], 'nomatch': ['state3']}}
        matches = self.highstate.top_matches(top)
        self.assertEqual(matches, {'env': ['state1', 'state2']})

    def test_top_matches_with_string(self):
        top = {'env': {'match': 'state1', 'nomatch': 'state2'}}
        matches = self.highstate.top_matches(top)
        self.assertEqual(matches, {'env': ['state1']})

if __name__ == '__main__':
    from integration import run_tests
    run_tests(HighStateTestCase, needs_daemon=False)
