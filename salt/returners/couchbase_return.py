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
ret_minions: list of minions that have returned data
nocache: should we not cache the return data

JID/MINION_ID
=============
return: return_data
out: out_data

'''
import logging

try:
    import couchbase
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# TODO: try to import faster json libs, and use them with:
# >>> couchbase.set_json_converters(yajl.dumps, yajl.loads)


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'couchbase'


def __virtual__():
    if not HAS_DEPS:
        return False
    return __virtualname__


def _get_options():
    '''
    Get the couchbase options from salt. Apply defaults
    if required.
    '''
    server_host = __salt__['config.option']('couchbase.host')
    if not server_host:
        log.debug("Using default host.")
        server_host = "salt"

    server_port = __salt__['config.option']('couchbase.port')
    if not server_port:
        log.debug("Using default port.")
        server_host = 8091

    bucket_name = __salt__['config.option']('couchbase.bucket')
    if not bucket_name:
        log.debug("Using default bucket.")
        bucket_name = "salt"

    return {'host': server_host,
            'port': server_port,
            'bucket': bucket_name}

COUCHBASE_CONN = None

def _get_connection():
    '''
    Global function to access the couchbase connection (and make it if its closed)
    '''
    if COUCHBASE_CONN is None:
        opts = _get_options()
        COUCHBASE_CONN = Couchbase.connect(host=opts['host'],
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
        cb.add(jid, {'nocache': nocache})
    except couchbase.exceptions.KeyExistsError:
        return prep_jid(nocache=nocache)

    return jid


def returner(load):
    '''
    Return data to the local job cache
    '''
    serial = salt.payload.Serial(__opts__)
    jid_dir = _jid_dir(load['jid'])
    if os.path.exists(os.path.join(jid_dir, 'nocache')):
        return

    # do we need to rewrite the load?
    if load['jid'] == 'req' and bool(load.get('nocache', True)):
        with salt.utils.fopen(os.path.join(jid_dir, LOAD_P), 'w+b') as fp_:
            serial.dump(load, fp_)

    hn_dir = os.path.join(jid_dir, load['id'])

    try:
        os.mkdir(hn_dir)
    except OSError as e:
        if e.errno == errno.EEXIST:
            # Minion has already returned this jid and it should be dropped
            log.error(
                'An extra return was detected from minion {0}, please verify '
                'the minion, this could be a replay attack'.format(
                    load['id']
                )
            )
            return False
        elif e.errno == errno.ENOENT:
            log.error(
                'An inconsistency occurred, a job was received with a job id '
                'that is not present in the local cache: {jid}'.format(**load)
            )
            return False
        raise

    serial.dump(
        load['return'],
        # Use atomic open here to avoid the file being read before it's
        # completely written to. Refs #1935
        salt.utils.atomicfile.atomic_open(
            os.path.join(hn_dir, RETURN_P), 'w+b'
        )
    )

    if 'out' in load:
        serial.dump(
            load['out'],
            # Use atomic open here to avoid the file being read before
            # it's completely written to. Refs #1935
            salt.utils.atomicfile.atomic_open(
                os.path.join(hn_dir, OUT_P), 'w+b'
            )
        )


def save_load(jid, clear_load):
    '''
    Save the load to the specified jid
    '''
    jid_dir = _jid_dir(jid)

    serial = salt.payload.Serial(__opts__)

    # if you have a tgt, save that for the UI etc
    if 'tgt' in clear_load:
        ckminions = salt.utils.minions.CkMinions(__opts__)
        # Retrieve the minions list
        minions = ckminions.check_minions(
                clear_load['tgt'],
                clear_load.get('tgt_type', 'glob')
                )
        # save the minions to a cache so we can see in the UI
        try:
            serial.dump(
                minions,
                salt.utils.fopen(os.path.join(jid_dir, MINIONS_P), 'w+b')
                )
        except IOError:
            log.warning('Could not write job cache file for minions: {0}'.format(minions))

    # Save the invocation information
    try:
        serial.dump(
            clear_load,
            salt.utils.fopen(os.path.join(jid_dir, LOAD_P), 'w+b')
            )
    except IOError:
        log.warning('Could not write job cache file for minions: {0}'.format(minions))


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    jid_dir = _jid_dir(jid)
    if not os.path.exists(jid_dir):
        return {}
    serial = salt.payload.Serial(__opts__)

    ret = serial.load(salt.utils.fopen(os.path.join(jid_dir, LOAD_P), 'rb'))

    minions_path = os.path.join(jid_dir, MINIONS_P)
    if os.path.isfile(minions_path):
        ret['Minions'] = serial.load(salt.utils.fopen(minions_path, 'rb'))

    return ret


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    jid_dir = _jid_dir(jid)
    serial = salt.payload.Serial(__opts__)

    ret = {}
    # Check to see if the jid is real, if not return the empty dict
    if not os.path.isdir(jid_dir):
        return ret
    for fn_ in os.listdir(jid_dir):
        if fn_.startswith('.'):
            continue
        if fn_ not in ret:
            retp = os.path.join(jid_dir, fn_, RETURN_P)
            outp = os.path.join(jid_dir, fn_, OUT_P)
            if not os.path.isfile(retp):
                continue
            while fn_ not in ret:
                try:
                    ret_data = serial.load(
                        salt.utils.fopen(retp, 'rb'))
                    ret[fn_] = {'return': ret_data}
                    if os.path.isfile(outp):
                        ret[fn_]['out'] = serial.load(
                            salt.utils.fopen(outp, 'rb'))
                except Exception:
                    pass
    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    ret = {}
    for jid, job, t_path, final in _walk_through(_job_dir()):
        ret[jid] = _format_jid_instance(jid, job)
    return ret
