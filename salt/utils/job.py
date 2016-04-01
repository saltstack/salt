# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import logging

# Import Salt libs
import salt.minion
import salt.utils.verify
import salt.utils.jid
from salt.utils.event import tagify


log = logging.getLogger(__name__)


def store_job(opts, load, event=None, mminion=None):
    '''
    Store job information using the configured master_job_cache
    '''
    # Generate EndTime
    endtime = salt.utils.jid.jid_to_time(salt.utils.jid.gen_jid())
    # If the return data is invalid, just ignore it
    if any(key not in load for key in ('return', 'jid', 'id')):
        return False
    if not salt.utils.verify.valid_id(opts, load['id']):
        return False
    if mminion is None:
        mminion = salt.minion.MasterMinion(opts, states=False, rend=False)

    job_cache = opts['master_job_cache']
    if load['jid'] == 'req':
        # The minion is returning a standalone job, request a jobid
        load['arg'] = load.get('arg', load.get('fun_args', []))
        load['tgt_type'] = 'glob'
        load['tgt'] = load['id']

        prep_fstr = '{0}.prep_jid'.format(opts['master_job_cache'])
        try:
            load['jid'] = mminion.returners[prep_fstr](nocache=load.get('nocache', False))
        except KeyError:
            emsg = "Returner '{0}' does not support function prep_jid".format(job_cache)
            log.error(emsg)
            raise KeyError(emsg)

        # save the load, since we don't have it
        saveload_fstr = '{0}.save_load'.format(job_cache)
        try:
            mminion.returners[saveload_fstr](load['jid'], load)
        except KeyError:
            emsg = "Returner '{0}' does not support function save_load".format(job_cache)
            log.error(emsg)
            raise KeyError(emsg)
    elif salt.utils.jid.is_jid(load['jid']):
        # Store the jid
        jidstore_fstr = '{0}.prep_jid'.format(job_cache)
        try:
            mminion.returners[jidstore_fstr](False, passed_jid=load['jid'])
        except KeyError:
            emsg = "Returner '{0}' does not support function prep_jid".format(job_cache)
            log.error(emsg)
            raise KeyError(emsg)

    if event:
        # If the return data is invalid, just ignore it
        log.info('Got return from {id} for job {jid}'.format(**load))
        event.fire_event(load, tagify([load['jid'], 'ret', load['id']], 'job'))
        event.fire_ret_load(load)

    # if you have a job_cache, or an ext_job_cache, don't write to
    # the regular master cache
    if not opts['job_cache'] or opts.get('ext_job_cache'):
        return

    # otherwise, write to the master cache
    savefstr = '{0}.save_load'.format(job_cache)
    getfstr = '{0}.get_load'.format(job_cache)
    fstr = '{0}.returner'.format(job_cache)
    if 'fun' not in load and load.get('return', {}):
        ret_ = load.get('return', {})
        if 'fun' in ret_:
            load.update({'fun': ret_['fun']})
        if 'user' in ret_:
            load.update({'user': ret_['user']})
    try:
        if 'jid' in load \
                and 'get_load' in mminion.returners \
                and not mminion.returners[getfstr](load.get('jid', '')):
            mminion.returners[savefstr](load['jid'], load)
        mminion.returners[fstr](load)

        updateetfstr = '{0}.update_endtime'.format(job_cache)
        if (opts.get('job_cache_store_endtime')
                and updateetfstr in mminion.returners):
            mminion.returners[updateetfstr](load['jid'], endtime)

    except KeyError:
        emsg = "Returner '{0}' does not support function returner".format(job_cache)
        log.error(emsg)
        raise KeyError(emsg)


def store_minions(opts, jid, minions, mminion=None, syndic_id=None):
    '''
    Store additional minions matched on lower-level masters using the configured
    master_job_cache
    '''
    if mminion is None:
        mminion = salt.minion.MasterMinion(opts, states=False, rend=False)
    job_cache = opts['master_job_cache']
    minions_fstr = '{0}.save_minions'.format(job_cache)

    try:
        mminion.returners[minions_fstr](jid, minions, syndic_id=syndic_id)
    except KeyError:
        raise KeyError(
            'Returner \'{0}\' does not support function save_minions'.format(
                job_cache
            )
        )


def get_retcode(ret):
    '''
    Determine a retcode for a given return
    '''
    retcode = 0
    # if there is a dict with retcode, use that
    if isinstance(ret, dict) and ret.get('retcode', 0) != 0:
        return ret['retcode']
    # if its a boolean, False means 1
    elif isinstance(ret, bool) and not ret:
        return 1
    return retcode

# vim:set et sts=4 ts=4 tw=80:
