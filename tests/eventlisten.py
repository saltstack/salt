# -*- coding: utf-8 -*-

'''
Use this script to dump the event data out to the terminal. It needs to know
what the sock_dir is.

This script is a generic tool to test event output
'''

# Import Python libs
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
            help=('Staticly define the directory holding the salt unix '
                  'sockets for communication'))
    parser.add_option('-n',
            '--node',
            dest='node',
            default='master',
            help=('State if this listener will attach to a master or a '
                  'minion daemon, pass "master" or "minion"'))

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


def listen(sock_dir, node, id=None):
    '''
    Attach to the pub socket and grab messages
    '''
    event = salt.utils.event.SaltEvent(
            node,
            sock_dir,
            id=id
            )
    print event.puburi
    while True:
        ret = event.get_event(full=True)
        if ret is None:
            continue
        print('Event fired at {0}'.format(time.asctime()))
        print('*' * 25)
        print('Tag: {0}'.format(ret['tag']))
        print('Data:')
        pprint.pprint(ret['data'])


if __name__ == '__main__':
    opts = parse()
    listen(opts['sock_dir'], opts['node'], id=opts.get('id', ''))
