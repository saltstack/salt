# Import python libs
import yaml

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class MatchTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):
    '''
    Test salt matchers
    '''
    _call_binary_ = 'salt'

    def test_list(self):
        '''
        test salt -L matcher
        '''
        data = self.run_salt('-L minion test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-L minion,sub_minion test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_compound(self):
        '''
        test salt compound matcher
        '''
        data = self.run_salt('-C "min* and G@test_grain:cheese" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-C "min* and not G@test_grain:foo" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-C "min* not G@test_grain:foo" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        match = 'P@test_grain:^cheese$ and * and G@test_grain:cheese'
        data = self.run_salt('-t 1 -C \'{0}\' test.ping'.format(match))
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        match = 'L@sub_minion and E@.*'
        data = self.run_salt('-t 1 -C "{0}" test.ping'.format(match))
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))

    def test_glob(self):
        '''
        test salt glob matcher
        '''
        data = self.run_salt('minion test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('"*" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_regex(self):
        '''
        test salt regex matcher
        '''
        data = self.run_salt('-E "^minion$" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-E ".*" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_grain(self):
        '''
        test salt grain matcher
        '''
        # First-level grain (string value)
        data = self.run_salt('-t 1 -G "test_grain:cheese" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-G "test_grain:spam" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))
        # First-level grain (list member)
        data = self.run_salt('-t 1 -G "planets:earth" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-G "planets:saturn" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))
        data = self.run_salt('-G "planets:pluto" test.ping')
        self.assertEqual(
            ''.join(data),
            'No minions matched the target. No command was sent, no jid was '
            'assigned.'
        )
        # Nested grain (string value)
        data = self.run_salt('-t 1 -G "level1:level2:foo" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-G "level1:level2:bar" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))
        # Nested grain (list member)
        data = self.run_salt('-t 1 -G "companions:one:ian" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-G "companions:two:jamie" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))

    def test_regrain(self):
        '''
        test salt grain matcher
        '''
        data = self.run_salt(
            '-t 1 --grain-pcre "test_grain:^cheese$" test.ping'
        )
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('--grain-pcre "test_grain:.*am$" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))

    def test_pillar(self):
        '''
        test pillar matcher
        '''
        # First-level pillar (string value)
        data = self.run_salt('-I "monty:python" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)
        # First-level pillar (string value, only in sub_minion)
        data = self.run_salt('-I "sub:sub_minion" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))
        # First-level pillar (list member)
        data = self.run_salt('-I "knights:Bedevere" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)
        # Nested pillar (string value)
        data = self.run_salt('-I "level1:level2:foo" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)
        # Nested pillar (list member)
        data = self.run_salt('-I "companions:three:sarah jane" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_exsel(self):
        data = self.run_salt('-X test.ping test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_ipcidr(self):
        subnets_data = self.run_salt('--out yaml \'*\' network.subnets')
        yaml_data = yaml.load('\n'.join(subnets_data))

        # We're just after the first defined subnet from 'minion'
        subnet = yaml_data['minion'][0]

        data = self.run_salt('-S {0} test.ping'.format(subnet))
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_static(self):
        '''
        test salt static call
        '''
        data = self.run_salt('minion test.ping --static')
        data = '\n'.join(data)
        self.assertIn('minion', data)

    def test_salt_documentation(self):
        '''
        Test to see if we're supporting --doc
        '''
        data = self.run_salt('-d \* user')
        self.assertIn('user.add:', data)

    def test_salt_documentation_arguments_not_assumed(self):
        '''
        Test to see if we're not auto-adding '*' and 'sys.doc' to the call
        '''
        data = self.run_salt('-d')
        self.assertIn('user.add:', data)
        data = self.run_salt('\'*\' -d')
        self.assertIn('user.add:', data)
        data = self.run_salt('\'*\' -d user')
        self.assertIn('user.add:', data)
        data = self.run_salt('\'*\' sys.doc -d user')
        self.assertIn('user.add:', data)
        data = self.run_salt('\'*\' sys.doc user')
        self.assertIn('user.add:', data)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MatchTest)
