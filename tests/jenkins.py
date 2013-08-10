#!/usr/bin/env python
'''
This script is used to test salt from a jenkins server, specifically
jenkins.satstack.com.

This script is intended to be shell centric!!
'''

import subprocess
import hashlib
import random
import optparse


def run(platform, provider):
    '''
    RUN!
    '''
    htag = hashlib.md5(str(random.randint(1, 100000000))).hexdigest()[:6] 
    vm_name = '{0}{1}'.format(platform, htag)
    subprocess.call(
            'salt-cloud -p {0}_{1} {2}'.format(provider, platform, vm_name),
            shell=True)
    # Run tests here
    subprocess.call(
            'salt {0} state.sls testrun'.format(vm_name),
            shell=True)
    # Clean up the vm
    subprocess.call(
            'salt-cloud -d {0} -y'.format(vm_name),
            shell=True)
