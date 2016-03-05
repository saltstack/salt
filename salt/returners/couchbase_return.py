# -*- coding: utf-8 -*-
'''
Simple returner for Couchbase. Optional configuration
settings are listed below, along with sane defaults.

couchbase.host:   'salt'
couchbase.port:   8091
couchbase.bucket: 'salt'
couchbase.skip_verify_views: False

  To use the couchbase returner, append '--return couchbase' to the salt command. ex:

    salt '*' test.ping --return couchbase


All of the return data will be stored in documents as follows:

JID
===
load: load obj
tgt_minions: list of minions targeted
nocache: should we not cache the return data

JID/MINION_ID
=============
return: return_data
out: out_data
'''
from __future__ import absolute_import

import logging

try:
    import couchbase
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# Import salt libs
import salt.utils
import salt.utils.jid

log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = 'couchbase'

# some globals
COUCHBASE_CONN = None
DESIGN_NAME = 'couchbase_returner'
VERIFIED_VIEWS = False


def __virtual__():
    if not HAS_DEPS:
        return False

    # try to load some faster json libraries. In order of fastest to slowest
    json = salt.utils.import_json()
    couchbase.set_json_converters(json.dumps, json.loads)

    return __virtualname__


def _get_options():
    '''
    Get the couchbase options from salt. Apply defaults
    if required.
    '''
    return {'host': __opts__.get('couchbase.host', 'salt'),
            'port': __opts__.get('couchbase.port', 8091),
            'bucket': __opts__.get('couchbase.bucket', 'salt')}


def _get_connection():
    '''
    Global function to access the couchbase connection (and make it if its closed)
    '''
    global COUCHBASE_CONN
    if COUCHBASE_CONN is None:
        opts = _get_options()
        COUCHBASE_CONN = couchbase.Couchbase.connect(host=opts['host'],
                                                     port=opts['port'],
                                                     bucket=opts['bucket'])
    return COUCHBASE_CONN


def _verify_views():
    '''
    Verify that you have the views you need. This can be disabled by
    adding couchbase.skip_verify_views: True in config
    '''
    global VERIFIED_VIEWS

    if VERIFIED_VIEWS or __opts__.get('couchbase.skip_verify_views', False):
        return
    cb_ = _get_connection()
    ddoc = {'views': {'jids': {'map': "function (doc, meta) { if (meta.id.indexOf('/') === -1 && doc.load){ emit(meta.id, null) } }"},
                      'jid_returns': {'map': "function (doc, meta) { if (meta.id.indexOf('/') > -1){ key_parts = meta.id.split('/'); emit(key_parts[0], key_parts[1]); } }"}
                      }
            }

    try:
        curr_ddoc = cb_.design_get(DESIGN_NAME, use_devmode=False).value
        if curr_ddoc['views'] == ddoc['views']:
            VERIFIED_VIEWS = True
            return
    except couchbase.exceptions.HTTPError:
        pass

    cb_.design_create(DESIGN_NAME, ddoc, use_devmode=False)
    VERIFIED_VIEWS = True


def _get_ttl():
    '''
    Return the TTL that we should store our objects with
    '''
    return __opts__['keep_jobs'] * 60 * 60  # keep_jobs is in hours


#TODO: add to returner docs-- this is a new one
def prep_jid(nocache=False, passed_jid=None):
    '''
    Return a job id and prepare the job id directory
    This is the function responsible for making sure jids don't collide (unless
    its passed a jid)
    So do what you have to do to make sure that stays the case
    '''
    if passed_jid is None:
        jid = salt.utils.jid.gen_jid()
    else:
        jid = passed_jid

    cb_ = _get_connection()

    try:
        cb_.add(str(jid),
               {'nocache': nocache},
               ttl=_get_ttl(),
               )
    except couchbase.exceptions.KeyExistsError:
        # TODO: some sort of sleep or something? Spinning is generally bad practice
        if passed_jid is None:
            return prep_jid(nocache=nocache)

    return jid


def returner(load):
    '''
    Return data to the local job cache
    '''
    cb_ = _get_connection()
    try:
        jid_doc = cb_.get(load['jid'])
        if jid_doc.value['nocache'] is True:
            return
    except couchbase.exceptions.NotFoundError:
        log.error(
            'An inconsistency occurred, a job was received with a job id '
            'that is not present in the local cache: {jid}'.format(**load)
        )
        return False

    hn_key = '{0}/{1}'.format(load['jid'], load['id'])
    try:
        ret_doc = {'return': load['return']}
        if 'out' in load:
            ret_doc['out'] = load['out']

        cb_.add(hn_key,
               ret_doc,
               ttl=_get_ttl(),
               )
    except couchbase.exceptions.KeyExistsError:
        log.error(
            'An extra return was detected from minion {0}, please verify '
            'the minion, this could be a replay attack'.format(
                load['id']
            )
        )
        return False


def save_load(jid, clear_load):
    '''
    Save the load to the specified jid
    '''
    cb_ = _get_connection()

    try:
        jid_doc = cb_.get(str(jid))
    except couchbase.exceptions.NotFoundError:
        log.warning('Could not write job cache file for jid: {0}'.format(jid))
        return False

    jid_doc.value['load'] = clear_load
    cb_.replace(str(jid), jid_doc.value, cas=jid_doc.cas, ttl=_get_ttl())

    # if you have a tgt, save that for the UI etc
    if 'tgt' in clear_load:
        ckminions = salt.utils.minions.CkMinions(__opts__)
        # Retrieve the minions list
        minions = ckminions.check_minions(
            clear_load['tgt'],
            clear_load.get('tgt_type', 'glob')
            )
        save_minions(jid, minions)


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    '''
    Save/update the minion list for a given jid. The syndic_id argument is
    included for API compatibility only.
    '''
    cb_ = _get_connection()

    try:
        jid_doc = cb_.get(str(jid))
    except couchbase.exceptions.NotFoundError:
        log.warning('Could not write job cache file for jid: {0}'.format(jid))
        return False

    # save the minions to a cache so we can see in the UI
    if 'minions' in jid_doc.value:
        jid_doc.value['minions'] = sorted(
            set(jid_doc.value['minions'] + minions)
        )
    else:
        jid_doc.value['minions'] = minions
    cb_.replace(str(jid), jid_doc.value, cas=jid_doc.cas, ttl=_get_ttl())


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    cb_ = _get_connection()

    try:
        jid_doc = cb_.get(str(jid))
    except couchbase.exceptions.NotFoundError:
        return {}

    ret = jid_doc.value['load']
    if 'minions' in jid_doc.value:
        ret['Minions'] = jid_doc.value['minions']

    return ret


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    cb_ = _get_connection()
    _verify_views()

    ret = {}

    for result in cb_.query(DESIGN_NAME, 'jid_returns', key=str(jid), include_docs=True):
        ret[result.value] = result.doc.value

    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    cb_ = _get_connection()
    _verify_views()

    ret = {}

    for result in cb_.query(DESIGN_NAME, 'jids', include_docs=True):
        ret[result.key] = _format_jid_instance(result.key, result.doc.value['load'])

    return ret


def _format_job_instance(job):
    '''
    Return a properly formatted job dict
    '''
    ret = {'Function': job.get('fun', 'unknown-function'),
           'Arguments': list(job.get('arg', [])),
           # unlikely but safeguard from invalid returns
           'Target': job.get('tgt', 'unknown-target'),
           'Target-type': job.get('tgt_type', []),
           'User': job.get('user', 'root')}

    if 'metadata' in job:
        ret['Metadata'] = job.get('metadata', {})
    else:
        if 'kwargs' in job:
            if 'metadata' in job['kwargs']:
                ret['Metadata'] = job['kwargs'].get('metadata', {})
    return ret


def _format_jid_instance(jid, job):
    '''
    Return a properly formatted jid dict
    '''
    ret = _format_job_instance(job)
    ret.update({'StartTime': salt.utils.jid.jid_to_time(jid)})
    return ret
