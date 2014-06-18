# -*- coding: utf-8 -*-
'''
Simple returner for Couchbase. Optional configuration
settings are listed below, along with sane defaults.

couchbase.host:   'salt'
couchbase.port:   8091
couchbase.bucket: 'salt'

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


TODO: remove

Administrator
password


# TODO: auto-create the views (if you have passwords)

jid_returns
===========
function (doc, meta) {
  if (meta.id.indexOf('/') > -1){
    key_parts = meta.id.split('/');
    emit(key_parts[0], key_parts[1]);
  }
}

jids
=====
function (doc, meta) {
  if (meta.id.indexOf('/') === -1 && doc.load){
    emit(meta.id, null)
  }
}

'''
import logging

try:
    import couchbase
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# Import salt libs
import salt.utils

# TODO: try to import faster json libs, and use them with:
# >>> couchbase.set_json_converters(yajl.dumps, yajl.loads)


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'couchbase'


def __virtual__():
    if not HAS_DEPS:
        return False

    # TODO: verify bucket exists
    # TODO: verify/create view
    return __virtualname__


def _get_options():
    '''
    Get the couchbase options from salt. Apply defaults
    if required.
    '''
    return {'host': __opts__.get('couchbase.host', 'salt'),
            'port': __opts__.get('couchbase.port', 8091),
            'bucket': __opts__.get('couchbase.bucket', 'salt')}

COUCHBASE_CONN = None

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



#TODO: add to returner docs-- this is a new one
def prep_jid(nocache=False):
    '''
    Return a job id and prepare the job id directory
    This is the function responsible for making sure jids don't collide (unless its passed a jid)
    So do what you have to do to make sure that stays the case
    '''
    cb = _get_connection()

    jid = salt.utils.gen_jid()
    try:
        cb.add(str(jid), {'nocache': nocache})
    except couchbase.exceptions.KeyExistsError:
        return prep_jid(nocache=nocache)

    return jid


def returner(load):
    '''
    Return data to the local job cache
    '''
    cb = _get_connection()
    try:
        jid_doc = cb.get(load['jid'])
        if jid_doc.value['nocache'] is True:
            return
    except couchbase.exceptions.NotFoundError:
        log.error(
            'An inconsistency occurred, a job was received with a job id '
            'that is not present in the local cache: {jid}'.format(**load)
        )
        return False

    # TODO:??? This doens't make a lot of sense...
    '''
    # do we need to rewrite the load?
    if load['jid'] == 'req' and bool(load.get('nocache', True)):
        with salt.utils.fopen(os.path.join(jid_dir, LOAD_P), 'w+b') as fp_:
            serial.dump(load, fp_)
    '''

    hn_key = '{0}/{1}'.format(load['jid'], load['id'])
    try:
        ret_doc = {'return': load['return']}
        if 'out' in load:
            ret_doc['out'] = load['out']

        cb.add(hn_key, ret_doc)
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
    cb = _get_connection()

    try:
        jid_doc = cb.get(str(jid))
    except couchbase.exceptions.NotFoundError:
        log.warning('Could not write job cache file for minions: {0}'.format(minions))
        return False

    # if you have a tgt, save that for the UI etc
    if 'tgt' in clear_load:
        ckminions = salt.utils.minions.CkMinions(__opts__)
        # Retrieve the minions list
        minions = ckminions.check_minions(
                clear_load['tgt'],
                clear_load.get('tgt_type', 'glob')
                )
        # save the minions to a cache so we can see in the UI
        jid_doc.value['minions'] = minions

    jid_doc.value['load'] = clear_load

    cb.replace(str(jid),
               jid_doc.value,
               cas=jid_doc.cas,
               )



def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    cb = _get_connection()

    try:
        jid_doc = cb.get(str(jid))
    except couchbase.exceptions.NotFoundError:
        log.warning('Could not write job cache file for minions: {0}'.format(minions))
        return False

    ret = jid_doc.value['load']
    if 'minions' in jid_doc.value:
        ret['Minions'] = jid_doc.value['minions']

    return ret

def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    cb = _get_connection()

    ret = {}

    for result in cb.query('jid_returns', 'jid_returns', key=str(jid), include_docs=True):
        ret[result.value] = result.doc.value

    return ret

def get_jids():
    '''
    Return a list of all job ids
    '''
    cb = _get_connection()

    ret = {}

    for result in cb.query('jids', 'jids', include_docs=True):
        ret[result.key] = _format_jid_instance(result.key, result.doc.value['load'])

    return ret



def _format_job_instance(job):
    return {'Function': job.get('fun', 'unknown-function'),
            'Arguments': list(job.get('arg', [])),
            # unlikely but safeguard from invalid returns
            'Target': job.get('tgt', 'unknown-target'),
            'Target-type': job.get('tgt_type', []),
            'User': job.get('user', 'root')}


def _format_jid_instance(jid, job):
    ret = _format_job_instance(job)
    ret.update({'StartTime': salt.utils.jid_to_time(jid)})
    return ret
