'''
Test the hosts module
'''
# Import python libs
import os

# Import Salt libs
import daemon

class HostsModuleTest(daemon.ModuleCase):
    def setUp(self):
        self._hfn = [f.hosts_filename for f in monkey_pathed]
        self.files = os.path.join(TEMPLATES_DIR, 'files')
        self.hostspath = os.path.join(self.files, 'hosts')
        self.not_found = os.path.join(self.files, 'not_found')
        self.tmpfiles = []

    def tearDown(self):
        for i, f in enumerate(monkey_pathed):
            f.hosts_filename = self._hfn[i]
        for tmp in self.tmpfiles:
            os.remove(tmp)

    def tmp_hosts_file(self, src):
        tmpfile = path.join(self.files, 'tmp')
        self.tmpfiles.append(tmpfile)
        shutil.copy(src, tmpfile)
        return tmpfile

    def test_list_hosts(self):
        list_hosts.hosts_filename = self.hostspath
        hosts = list_hosts()
        self.assertEqual(len(hosts), 6)
        self.assertEqual(hosts['::1'], ['ip6-localhost', 'ip6-loopback'])
        self.assertEqual(hosts['127.0.0.1'], ['localhost', 'myname'])

    def test_list_hosts_nofile(self):
        list_hosts.hosts_filename = self.not_found
        hosts = list_hosts()
        self.assertEqual(hosts, {})

    def test_get_ip(self):
        list_hosts.hosts_filename = self.hostspath
        self.assertEqual(get_ip('myname'), '127.0.0.1')
        self.assertEqual(get_ip('othername'), '')
        list_hosts.hosts_filename = self.not_found
        self.assertEqual(get_ip('othername'), '')

    def test_get_alias(self):
        list_hosts.hosts_filename = self.hostspath
        self.assertEqual(get_alias('127.0.0.1'), ['localhost', 'myname'])
        self.assertEqual(get_alias('127.0.0.2'), [])
        list_hosts.hosts_filename = self.not_found
        self.assertEqual(get_alias('127.0.0.1'), [])

    def test_has_pair(self):
        list_hosts.hosts_filename = self.hostspath
        self.assertTrue(has_pair('127.0.0.1', 'myname'))
        self.assertFalse(has_pair('127.0.0.1', 'othername'))

    def test_set_host(self):
        tmp = self.tmp_hosts_file(self.hostspath)
        list_hosts.hosts_filename = tmp
        set_host.hosts_filename = tmp
        assert set_host('192.168.1.123', 'newip')
        self.assertTrue(has_pair('192.168.1.123', 'newip'))
        self.assertEqual(len(list_hosts()), 7)
        assert set_host('127.0.0.1', 'localhost')
        self.assertFalse(has_pair('127.0.0.1', 'myname'), 'should remove second entry')

    def test_add_host(self):
        tmp = self.tmp_hosts_file(self.hostspath)
        list_hosts.hosts_filename = tmp
        add_host.hosts_filename = tmp
        assert add_host('192.168.1.123', 'newip')
        self.assertTrue(has_pair('192.168.1.123', 'newip'))
        self.assertEqual(len(list_hosts()), 7)
        assert add_host('127.0.0.1', 'othernameip')
        self.assertEqual(len(list_hosts()), 7)

    def test_rm_host(self):
        tmp = self.tmp_hosts_file(self.hostspath)
        list_hosts.hosts_filename = tmp
        rm_host.hosts_filename = tmp
        assert has_pair('127.0.0.1', 'myname')
        assert rm_host('127.0.0.1', 'myname')
        assert not has_pair('127.0.0.1', 'myname')
        assert rm_host('127.0.0.1', 'unknown')
