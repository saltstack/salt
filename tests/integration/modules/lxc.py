# -*- coding: utf-8 -*-

'''
Test the lxc module
'''

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, skip_if_not_root, skip_if_binaries_missing
ensure_in_syspath('../../')

# Import salt libs
import integration


@skip_if_not_root
@skip_if_binaries_missing('lxc-start', message='LXC is not installed or minimal version not met')
class LXCModuleTest(integration.ModuleCase):
    '''
    Test the lxc module
    '''

    prefix = '_salttesting'

    def setUp(self):
        os = self.run_function('grains.item',
                               ['os', 'oscodename', 'osarch'])

        p = {'download':
             {'dist': os['os'].lower(),
              'arch': os['osarch'].lower(),
              'template': 'download',
              'release': os['oscodename'].lower()},
             'sshd': {'template': 'sshd'}}
        self.run_function('grains.setval', ['lxc.profile', p])

    def tearDown(self):
        '''
        Clean up any LXCs created.
        '''
        r = self.run_function('lxc.list')
        for k, v in r.items():
            for x in v:
                if x.startswith(self.prefix):
                    self.run_function('lxc.destroy', [x])

    def test_create_destroy(self):
        '''
        Test basic create/destroy of an LXC.
        '''

        r = self.run_function('lxc.create', [self.prefix],
                              template='sshd')
        self.assertEqual(r, {'created': True})
        self.assertTrue(self.run_function('lxc.exists', [self.prefix]))
        r = self.run_function('lxc.destroy', [self.prefix])
        self.assertEqual(r, {'state': None, 'change': True})
        self.assertFalse(self.run_function('lxc.exists', [self.prefix]))

    def test_init(self):
        '''
        Test basic init functionality.
        '''

        r = self.run_function('lxc.init', [self.prefix],
                              profile='sshd', seed=False)
        self.assertTrue(r.get('created', False))
        self.assertTrue(self.run_function('lxc.exists', [self.prefix]))

    def test_macvlan(self):
        '''
        Regression test for macvlan nic profile.
        '''

        p = {"macvlan": {"eth0": {
             "macvlan.mode": "bridge",
             "link": "eth0",
             "type": "macvlan"}}}

        self.run_function('grains.setval', ['lxc.nic', p])

        self.run_function('lxc.init', [self.prefix],
                          profile='sshd', nic='macvlan',
                          seed=False, start=False)

        f = '/var/lib/lxc/{0}/config'.format(self.prefix)
        conf = self.run_function('lxc.read_conf', [f])

        # Due to a segfault in lxc-destroy caused by invalid configs,
        # truncate the config.
        self.run_function('cmd.run', ['truncate -s 0 {0}'.format(f)])

        self.assertEqual(conf.get('lxc.network.type'), 'macvlan')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(LXCModuleTest)
