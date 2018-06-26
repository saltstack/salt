# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals
import sys
import salt.client.ssh
import salt.utils.parsers
from salt.utils.verify import verify_log


class SaltSSH(salt.utils.parsers.SaltSSHOptionParser):
    '''
    Used to Execute the salt ssh routine
    '''

    def run(self):
        if '-H' in sys.argv or '--hosts' in sys.argv:
            sys.argv += ['x', 'x']  # Hack: pass a mandatory two options
                                    # that won't be used anyways with -H or --hosts
        if '--bootstrap' == sys.argv[1]:
            sys.argv.remove('--bootstrap')
            sys.argv += ['-r', '\
                if grep -q "SUSE" /etc/os-release ; then\
                    zypper -n in python python-xml ;\
                elif [ -e /etc/debian_version ] ; then\
                    apt --yes install python ;\
                else\
                    echo "please add support for your OS to salt-ssh bootstrap" ;\
                    exit 6 ;\
                fi']
        self.parse_args()
        self.setup_logfile_logger()
        verify_log(self.config)

        ssh = salt.client.ssh.SSH(self.config)
        ssh.run()
