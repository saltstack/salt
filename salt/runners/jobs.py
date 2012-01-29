'''
A conveniance system to manage jobs, both active and already run
'''

# Import Python Modules
import os

# Import Salt Modules
import salt.client

# Import Third party libs
import yaml

def active():
    '''
    Return a report on all actively running jobs from a job id centric
    perspective
    '''
    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    client = salt.client.LocalClient(__opts__['config'])
    active = client.cmd('*', 'saltutil.running', timeout=1)
    for minion, data in active.items():
        if not isinstance(data, tuple):
            continue
        for job in data:
            if not job['jid'] in ret:
                ret[job['jid']] = {'running': [],
                                   'returned': [],
                                   'function': job['fun'],
                                   'arguments': list(job['arg']),
                                   'target': job['tgt'],
                                   'target-type': job['tgt_type']}
            else:
                ret[job['jid']]['running'].append({minion: job['pid']})
    if os.path.isdir(job_dir):
        for jid in os.listdir(job_dir):
            if not jid in ret:
                continue
            jid_dir = os.path.join(job_dir, jid)
            if not os.path.isdir(jid_dir):
                continue
            for minion in os.listdir(jid_dir):
                if minion.startswith('.'):
                    continue
                if os.path.exists(os.path.join(jid_dir, minion)):
                    ret[jid]['returned'].append(minion)
    print yaml.dump(ret)

