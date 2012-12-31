'''
A Salt runner module to mirror and aggregate the Salt execution module of the
same name
'''
# Import Python libs
import itertools

# Import salt libs
import salt.client
import salt.output

def doc():
    '''
    Collect all the sys.doc output from each minion and return the aggregate
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    all_docs = client.cmd('*', 'sys.doc', timeout=__opts__['timeout'])

    i = itertools.chain.from_iterable([i.items() for i in all_docs.values()])
    ret = dict(list(i))

    salt.output.display_output(ret, '', __opts__)
    return ret
