# -*- coding: utf-8 -*-
import logging
import salt.minion
import salt.utils.verify
import salt.utils.jid
from salt.utils.event import tagify


log = logging.getLogger(__name__)


def store_job(opts, load, event=None, mminion=None):
    # If the return data is invalid, just ignore it
    if any(key not in load for key in ('return', 'jid', 'id')):
        return False
    if not salt.utils.verify.valid_id(opts, load['id']):
        return False
    if mminion is None:
        mminion = salt.minion.MasterMinion(opts, states=False, rend=False)
    if load['jid'] == 'req':
        # The minion is returning a standalone job, request a jobid
        load['arg'] = load.get('arg', load.get('fun_args', []))
        load['tgt_type'] = 'glob'
        load['tgt'] = load['id']
        prep_fstr = '{0}.prep_jid'.format(opts['master_job_cache'])
        load['jid'] = mminion.returners[prep_fstr](
            nocache=load.get('nocache', False))

        # save the load, since we don't have it
        saveload_fstr = '{0}.save_load'.format(opts['master_job_cache'])
        mminion.returners[saveload_fstr](load['jid'], load)
    elif salt.utils.jid.is_jid(load['jid']):
        # Store the jid
        jidstore_fstr = '{0}.prep_jid'.format(opts['master_job_cache'])
        mminion.returners[jidstore_fstr](False, passed_jid=load['jid'])
    if event:
        # If the return data is invalid, just ignore it
        log.info('Got return from {id} for job {jid}'.format(**load))
        event.fire_event(
            load, tagify([load['jid'], 'ret', load['id']], 'job'))
        event.fire_ret_load(load)

    # if you have a job_cache, or an ext_job_cache, don't write to
    # the regular master cache
    if not opts['job_cache'] or opts.get('ext_job_cache'):
        return

    # otherwise, write to the master cache
    fstr = '{0}.returner'.format(opts['master_job_cache'])
    mminion.returners[fstr](load)
# vim:set et sts=4 ts=4 tw=80:
