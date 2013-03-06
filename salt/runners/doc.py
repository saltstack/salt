'''
A Salt runner module to mirror and aggregate the Salt execution module of the
same name
'''
# Import Python libs
import itertools

# Import salt libs
import salt.client
import salt.output


def __virtual__():
    '''
    Rename to sys
    '''
    return 'sys'


def doc():
    '''
    Collect all the sys.doc output from each minion and return the aggregate
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])

    docs = {}
    for ret in client.cmd_iter('*', 'sys.doc', timeout=__opts__['timeout']):
        for k,v in ret.items():
            docs.update(v)

    i = itertools.chain.from_iterable([i.items() for i in docs.values()])
    ret = dict(list(i))

    salt.output.display_output(ret, '', __opts__)
    return ret

# Still need to modify some of the backend for auth checks to make this work
def __list_functions(user=None):
    '''
    List all of the functions, optionally pass in a user to evaluate
    permissions on
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    funcs = {}
    gener = client.cmd_iter(
            '*',
            'sys.list_functions',
            timeout=__opts__['timeout'])
    for ret in gener:
        funcs.update(ret)
    if not user:
        salt.output.display_output(funcs, '', __opts__)
        return funcs
    for key, val in __opts__['external_auth'].items():
        if user in val:
            pass
