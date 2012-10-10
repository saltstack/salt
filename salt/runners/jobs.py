'''
A convenience system to manage jobs, both active and already run
'''

# Import Python Modules
import os

# Import Salt Modules
import salt.client
import salt.payload
import salt.utils
from salt._compat import string_types
from salt.exceptions import SaltException

# Import Third party libs
import yaml


def active():
    '''
    Return a report on all actively running jobs from a job id centric
    perspective
    '''
    ret = {}
    client = salt.client.LocalClient(__opts__['conf_file'])
    active_ = client.cmd('*', 'saltutil.running', timeout=__opts__['timeout'])
    for minion, data in active_.items():
        if not isinstance(data, list):
            continue
        for job in data:
            if not job['jid'] in ret:
                ret[job['jid']] = {'Running': [],
                                   'Returned': [],
                                   'Function': job['fun'],
                                   'Arguments': list(job['arg']),
                                   'Target': job['tgt'],
                                   'Target-type': job['tgt_type']}
            else:
                ret[job['jid']]['Running'].append({minion: job['pid']})
    for jid in ret:
        jid_dir = salt.utils.jid_dir(
                jid,
                __opts__['cachedir'],
                __opts__['hash_type']
                )
        if not os.path.isdir(jid_dir):
            continue
        for minion in os.listdir(jid_dir):
            if minion.startswith('.'):
                continue
            if os.path.exists(os.path.join(jid_dir, minion)):
                ret[jid]['Returned'].append(minion)
    print(yaml.dump(ret))
    return ret


def lookup_jid(jid):
    '''
    Return the printout from a previously executed job
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])

    ret = {}
    for mid, data in client.get_full_returns(jid, [], 0).items():
        printout = salt.output.get_outputter(data.get('out', None))
        ret[mid] = data.get('ret')
        printout({mid: ret[mid]})

    return ret


def list_jobs():
    '''
    List all detectable jobs and associated functions
    '''
    serial = salt.payload.Serial(__opts__)
    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)
        for final in os.listdir(t_path):
            loadpath = os.path.join(t_path, final, '.load.p')
            if not os.path.isfile(loadpath):
                continue
            load = serial.load(open(loadpath, 'rb'))
            jid = load['jid']
            ret[jid] = {'Start Time': salt.utils.jid_to_time(jid),
                        'Function': load['fun'],
                        'Arguments': list(load['arg']),
                        'Target': load['tgt'],
                        'Target-type': load['tgt_type']}
    print(yaml.dump(ret))
    return ret

def print_job(job_id):
    '''
    Print job available details, including return data.
    '''
    serial = salt.payload.Serial(__opts__)
    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)
        for final in os.listdir(t_path):
            loadpath = os.path.join(t_path, final, '.load.p')
            if not os.path.isfile(loadpath):
                continue
            load = serial.load(open(loadpath, 'rb'))
            jid = load['jid']
            if job_id == jid:
                hosts_path = os.path.join(t_path, final)
                hosts_return = {}
                for host in os.listdir(hosts_path):
                    host_path = os.path.join(hosts_path, host)
                    if os.path.isdir(host_path):
                        returnfile = os.path.join(host_path, 'return.p')
                        if not os.path.isfile(returnfile):
                            continue
                        return_data = serial.load(open(returnfile, 'rb'))
                        hosts_return[host] = return_data
                        ret[jid] = {'Start Time': salt.utils.jid_to_time(jid),
                                    'Function': load['fun'],
                                    'Arguments': list(load['arg']),
                                    'Target': load['tgt'],
                                    'Target-type': load['tgt_type'],
                                    'Result': hosts_return}
                        salt.output.get_outputter('yaml')(ret)
    return ret
