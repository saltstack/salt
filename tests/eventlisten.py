# -*- coding: utf-8 -*-

'''
Use this script to dump the event data out to the terminal. It needs to know
what the sock_dir is.

This script is a generic tool to test event output
'''

# Import Python libs
from __future__ import print_function
import optparse
import pprint
import time
import os

# Import Salt libs
import salt.utils.event


def parse():
    '''
    Parse the script command line inputs
    '''
    parser = optparse.OptionParser()

    parser.add_option('-s',
            '--sock-dir',
            dest='sock_dir',
            default='/var/run/salt',
            help=('Statically define the directory holding the salt unix '
                  'sockets for communication'))
    parser.add_option('-n',
            '--node',
            dest='node',
            default='master',
            help=('State if this listener will attach to a master or a '
                  'minion daemon, pass "master" or "minion"'))

    parser.add_option('-f',
            '--func_count',
            default='',
            help=('Return a count of the number of minions which have '
                 'replied to a job with a given func.'))

    options, args = parser.parse_args()

    opts = {}

    for k, v in options.__dict__.items():
        if v is not None:
            opts[k] = v

    opts['sock_dir'] = os.path.join(opts['sock_dir'], opts['node'])

    if 'minion' in options.node:
        if args:
            opts['id'] = args[0]
            return opts

        opts['id'] = options.node

    return opts


def check_access_and_print_warning(sock_dir):
    '''
    Check if this user is able to access the socket
    directory and print a warning if not
    '''
    if (os.access(sock_dir, os.R_OK) and
            os.access(sock_dir, os.W_OK) and
            os.access(sock_dir, os.X_OK)):
        return
    else:
        print('WARNING: Events will not be reported'
              ' (not able to access {0})'.format(sock_dir))


#def listen(sock_dir, node):
def listen(opts):
    '''
    Attach to the pub socket and grab messages
    '''
    event = salt.utils.event.SaltEvent(
            opts['node'],
            opts['sock_dir']
            )
    check_access_and_print_warning(opts['sock_dir'])
    print(event.puburi)
    jid_counter = 0
    found_minions = []
    while True:
        ret = event.get_event(full=True)
        if ret is None:
            continue
        if opts['func_count']:
            data = ret.get('data', False)
            if data:
                if 'id' in data.keys() and data.get('id', False) not in found_minions:
                    if data['fun'] == opts['func_count']:
                        jid_counter += 1
                        found_minions.append(data['id'])
                        print('Reply received from [{0}]. Total replies now: [{1}].'.format(ret['data']['id'], jid_counter))
                    continue
        else:
            print('Event fired at {0}'.format(time.asctime()))
            print('*' * 25)
            print('Tag: {0}'.format(ret['tag']))
            print('Data:')
            pprint.pprint(ret['data'])


if __name__ == '__main__':
    opts = parse()
    listen(opts)
