# -*- coding: utf-8 -*-
'''
A convenience system to manage jobs, both active and already run
'''

# Import python libs
import os

# Import salt libs
import salt.client
import salt.payload
import salt.utils
import salt.output
import salt.minion


def active():
    '''
    Return a report on all actively running jobs from a job id centric
    perspective

    CLI Example:

    .. code-block:: bash

        salt-run jobs.active
    '''
    ret = {}
    client = salt.client.LocalClient(__opts__['conf_file'])
    active_ = client.cmd('*', 'saltutil.running', timeout=__opts__['timeout'])
    for minion, data in active_.items():
        if not isinstance(data, list):
            continue
        for job in data:
            if not job['jid'] in ret:
                ret[job['jid']] = _format_job_instance(job)
                ret[job['jid']].update({'Running': [], 'Returned': []})
            else:
                ret[job['jid']]['Running'].append({minion: job['pid']})
    for jid in ret:
        jid_dir = salt.utils.jid_dir(
                jid,
                __opts__['cachedir'],
                __opts__['hash_type'])
        if not os.path.isdir(jid_dir):
            continue
        for minion in os.listdir(jid_dir):
            if minion.startswith('.'):
                continue
            if os.path.exists(os.path.join(jid_dir, minion)):
                ret[jid]['Returned'].append(minion)
    salt.output.display_output(ret, 'yaml', __opts__)
    return ret


def lookup_jid(jid, ext_source=None):
    '''
    Return the printout from a previously executed job

    CLI Example:

    .. code-block:: bash

        salt-run jobs.lookup_jid 20130916125524463507
    '''
    ret = {}
    if __opts__['ext_job_cache'] or ext_source:
        out = 'nested'
        returner = ext_source if ext_source else __opts__['ext_job_cache']
        mminion = salt.minion.MasterMinion(__opts__)
        data = mminion.returners['{0}.get_jid'.format(returner)](jid)
        for minion in data:
            if u'return' in data[minion]:
                ret[minion] = data[minion].get(u'return')
            else:
                ret[minion] = data[minion].get('return')
            if 'out' in data[minion]:
                out = data[minion]['out']
        salt.output.display_output(ret, out, __opts__)
        return ret

    # Fall back to the local job cache
    client = salt.client.LocalClient(__opts__['conf_file'])

    for mid, data in client.get_full_returns(jid, [], 0).items():
        ret[mid] = data.get('ret')
        salt.output.display_output(
                {mid: ret[mid]},
                data.get('out', None),
                __opts__)

    return ret


def list_job(jid):
    '''
    List a specific job given by its jid

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_job 20130916125524463507
    '''
    serial = salt.payload.Serial(__opts__)
    ret = {}
    jid_dir = salt.utils.jid_dir(jid, __opts__['cachedir'], __opts__['hash_type'])
    load_path = os.path.join(jid_dir, '.load.p')
    minions_path = os.path.join(jid_dir, '.minions.p')
    if os.path.isfile(load_path):
        load = serial.load(salt.utils.fopen(load_path, 'rb'))
        jid = load['jid']
        ret = _format_jid_instance(jid, load)
        ret.update({'jid': jid})
        if os.path.isfile(minions_path):
            minions = serial.load(salt.utils.fopen(minions_path, 'rb'))
            ret['Minions'] = minions

    salt.output.display_output(ret, 'yaml', __opts__)
    return ret


def list_jobs():
    '''
    List all detectable jobs and associated functions

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_jobs
    '''
    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    for jid, job, t_path, final in _walk_through(job_dir):
        ret[jid] = _format_jid_instance(jid, job)
    salt.output.display_output(ret, 'yaml', __opts__)
    return ret


def print_job(job_id):
    '''
    Print job available details, including return data.

    CLI Example:

    .. code-block:: bash

        salt-run jobs.print_job
    '''
    serial = salt.payload.Serial(__opts__)
    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    for jid, job, t_path, final in _walk_through(job_dir):
        if job_id == jid:
            hosts_path = os.path.join(t_path, final)
            hosts_return = {}
            for host in os.listdir(hosts_path):
                host_path = os.path.join(hosts_path, host)
                if os.path.isdir(host_path):
                    return_file = os.path.join(host_path, 'return.p')
                    if not os.path.isfile(return_file):
                        continue
                    return_data = serial.load(
                        salt.utils.fopen(return_file, 'rb')
                    )
                    hosts_return[host] = return_data
                    ret[jid] = _format_jid_instance(jid, job)
                    ret[jid].update({'Result': hosts_return})

    salt.output.display_output(ret, 'yaml', __opts__)
    return ret


def _format_job_instance(job):
    return {'Function': job['fun'],
            'Arguments': list(job['arg']),
            'Target': job['tgt'],
            'Target-type': job['tgt_type'],
            'User': job.get('user', 'root')}


def _format_jid_instance(jid, job):
    ret = _format_job_instance(job)
    ret.update({'StartTime': salt.utils.jid_to_time(jid)})
    return ret


def _walk_through(job_dir):
    serial = salt.payload.Serial(__opts__)

    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)

        for final in os.listdir(t_path):
            load_path = os.path.join(t_path, final, '.load.p')

            if not os.path.isfile(load_path):
                continue

            job = serial.load(salt.utils.fopen(load_path, 'rb'))
            jid = job['jid']
            yield jid, job, t_path, final
