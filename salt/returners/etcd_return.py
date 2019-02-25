# -*- coding: utf-8 -*-
"""
Return data to an etcd server or cluster

:depends: - python-etcd

In order to return to an etcd server, a profile should be created in the master
configuration file:

.. code-block:: yaml

    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 2379

It is technically possible to configure etcd without using a profile, but this
is not considered to be a best practice, especially when multiple etcd servers
or clusters are available.

.. code-block:: yaml

    etcd.host: 127.0.0.1
    etcd.port: 2379

Additionally, two more options must be specified in the top-level configuration
in order to use the etcd returner:

.. code-block:: yaml

    etcd.returner: my_etcd_config
    etcd.returner_root: /salt/return

The ``etcd.returner`` option specifies which configuration profile to use. The
``etcd.returner_root`` option specifies the path inside etcd to use as the root
of the returner system.

Once the etcd options are configured, the returner may be used:

CLI Example:

    salt '*' test.ping --return etcd

A username and password can be set:

.. code-block:: yaml

    etcd.username: larry  # Optional; requires etcd.password to be set
    etcd.password: 123pass  # Optional; requires etcd.username to be set

Authentication with username and password, currently requires the
``master`` branch of ``python-etcd``.

You may also specify different roles for read and write operations. First,
create the profiles as specified above. Then add:

.. code-block:: yaml

    etcd.returner_read_profile: my_etcd_read
    etcd.returner_write_profile: my_etcd_write

Etcd Returner Schema
--------------------
The etcd returner has the following schema underneath the path set in the profile:

job
+++
The job key contains the jid of each job that has been returned. Underneath this
job are two special keys. One of them is ".load.p" which contains information
about the job when it was created. The other key is ".lock.p" which is responsible
for whether the job is still valid or it is scheduled to be cleaned up.

The contents if ".lock.p" contains the modificationIndex of the of the ".load.p"
key and when configured via the "etcd.ttl" or "keep_jobs" will have the ttl
applied to it. When this file is expired via the ttl or explicitly removed by
the administrator, the job will then be scheduled for removal.

event
+++++
This key is essentially a namespace for all of the events that are submitted
to Salt. When an event is received, the data for the event is written under
this key using the "tag" parameter at its path. The creationIndex for this key
is then cached in order to determine whether it should be scheduled for
removal or not.

minion.job
++++++++++
Underneath the minion.job key is a list of minions ids. Each minion id contains
the jid of the last job that was returned by the minion. This key is used to
support the external job cache feature of Salt.

event.cache
+++++++++++
Underneath this key is a list of all of the events that were received by the
returner. Each event is identified by its creationIndex when the event was
registered under the "event" key that was described previously. Each event
under this key contains two keys. One of which is "id", and the other which
is "tag".

The "id" key contains the latest modificationIndex of the most recent event
that was reigstered under the event key. This is used to determine whether
the data for the event has been modified. When configured via the "etcd.ttl"
or the "keep_jobs" option, this key will have the ttl applied to it. When
the "id" key has expired or explicitly removed by the administrator, the
event and its tag will be scheduled for removal.

The other key under each event, is the "tag" key. The "tag" key simply
contains the path to the tag that was registered with the event. The value
of the "id" key points to the modificationIndex of this particular path.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.utils.jid
import salt.utils.json

try:
    import salt.utils.etcd_util
    from salt.utils.etcd_util import etcd
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)

Schema = {
    "minion-fun": 'minion.job',
    "event-path": 'event',
    "event-cache": 'event.cache',
    "job-cache": 'job',
}

# Define the module's virtual name
__virtualname__ = "etcd"


def __virtual__():
    """
    Only return if python-etcd is installed
    """
    if HAS_LIBS:
        return __virtualname__

    return False, "Could not import etcd returner; python-etcd is not installed."


def _get_conn(opts, profile=None):
    '''
    Establish a connection to an etcd profile.
    '''
    if profile is None:
        profile = opts.get('etcd.returner')

    # Grab the returner_root from the options
    path = opts.get('etcd.returner_root', '/salt/return')

    # Calculate the time-to-live for a job while giving etcd.ttl priority.
    # The etcd.ttl option specifies the number of seconds, whereas the keep_jobs
    # option specifies the number of hours. If any of these values are zero,
    # then jobs are forever persistent.

    ttl = opts.get('etcd.ttl', int(opts.get('keep_jobs', 0)) * 60 * 60)

    # Grab a connection using etcd_util, and then return the EtcdClient
    # from one of its attributes
    wrapper = salt.utils.etcd_util.get_conn(opts, profile)
    return wrapper.client, path, ttl


def returner(ret):
    '''
    Return data to an etcd profile.
    '''
    write_profile = __opts__.get('etcd.returner_write_profile')
    client, path, ttl = _get_conn(__opts__, write_profile)

    # If a minion is returning a standalone job, update it with a new jid, and
    # save it to ensure it can be queried similar to the mysql returner.
    if ret['jid'] == 'req':
        jid = prep_jid(nocache=ret.get('nocache', False))
        log.debug('sdstack_etcd returner <returner> satisfying request for new job id request with {jid:s}'.format(jid=jid))
        ret['jid'] = jid
        save_load(jid, ret)

    # Update the given minion in the external job cache with the current (latest job)
    # This is used by get_fun() to return the last function that was called
    minionp = '/'.join([path, Schema['minion-fun'], ret['id']])

    # We can use the ttl here because our minionp is actually linked to the job
    # which will expire according to the ttl anyways..
    log.debug("sdstack_etcd returner <returner> updating (last) job id of {id:s} at {path:s} with job {jid:s}".format(jid=ret['jid'], id=ret['id'], path=minionp))
    res = client.write(minionp, ret['jid'], ttl=ttl if ttl > 0 else None)
    if hasattr(res, '_prev_node'):
        log.trace("sdstack_etcd returner <returner> the previous job id {old:s} for {id:s} at {path:s} was set to {new:s}".format(old=res._prev_node.value, id=ret['id'], path=minionp, new=res.value))

    # Figure out the path for the specified job and minion
    jobp = '/'.join([path, Schema['job-cache'], ret['jid'], ret['id']])
    log.debug("sdstack_etcd returner <returner> writing job data for {jid:s} to {path:s} with {data}".format(jid=ret['jid'], path=jobp, data=ret))

    # Iterate through all the fields in the return dict and dump them under the
    # jobs/$jid/id/$field key. We aggregate all the exceptions so that if an
    # error happens, the rest of the fields will still be written.
    exceptions = []
    for field in ret:
        fieldp = '/'.join([jobp, field])
        data = salt.utils.json.dumps(ret[field])
        try:
            res = client.write(fieldp, data)
        except Exception as E:
            log.trace("sdstack_etcd returner <returner> unable to set field {field:s} for job {jid:s} at {path:s} to {result}".format(field=field, jid=ret['jid'], path=fieldp, result=ret[field]))
            exceptions.append((E, field, ret[field]))
            continue
        log.trace("sdstack_etcd returner <returner> set field {field:s} for job {jid:s} at {path:s} to {result}".format(field=field, jid=ret['jid'], path=res.key, result=ret[field]))

    # Go back through all the exceptions that occurred while trying to write the
    # fields and log them.
    for e, field, value in exceptions:
        log.exception("sdstack_etcd returner <returner> exception ({exception:s}) was raised while trying to set the field {field:s} for job {jid:s} to {value}".format(exception=e, field=field, jid=ret['jid'], value=value))
    return


def save_load(jid, load, minions=None):
    '''
    Save the load to the specified jid.
    '''
    write_profile = __opts__.get('etcd.returner_write_profile')
    client, path, ttl = _get_conn(__opts__, write_profile)

    # Check if the specified jid is 'req', as only incorrect code will do that
    if jid == 'req':
        log.warning('sdstack_etcd returner <save_load> was called with a request job id ({jid:s}) with {data:s}'.format(jid=jid, data=load))

    # Figure out the path using jobs/$jid/.load.p
    loadp = '/'.join([path, Schema['job-cache'], jid, '.load.p'])
    log.debug('sdstack_etcd returner <save_load> setting load data for job {jid:s} at {path:s} with {data:s}'.format(jid=jid, path=loadp, data=load))

    # Now we can just store the current load
    data = salt.utils.json.dumps(load)
    res = client.write(loadp, data)

    log.trace('sdstack_etcd returner <save_load> saved load data for job {jid:s} at {path:s} with {data}'.format(jid=jid, path=res.key, data=load))

    # Since this is when a job is being created, create a lock that we can
    # check to see if the job has expired. This allows a user to signal to
    # salt that its okey to remove the entire key by removing this lock.
    lockp = '/'.join([path, Schema['job-cache'], jid, '.lock.p'])
    log.trace('sdstack_etcd returner <save_load> writing lock file for job {jid:s} at {path:s} using index {index:d}'.format(jid=jid, path=lockp, index=res.modifiedIndex))
    res = client.write(lockp, res.modifiedIndex, ttl=ttl if ttl > 0 else None)

    if res.ttl is not None:
        log.trace('sdstack_etcd returner <save_load> job {jid:s} at {path:s} will expire in {ttl:d} seconds'.format(jid=jid, path=res.key, ttl=res.ttl))

    return


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    '''
    Save/update the minion list for a given jid. The syndic_id argument is
    included for API compatibility only.
    '''
    write_profile = __opts__.get('etcd.returner_write_profile')
    client, path, _ = _get_conn(__opts__, write_profile)

    # Check if the specified jid is 'req', as only incorrect code will do that
    if jid == 'req':
        log.warning('sdstack_etcd returner <save_minions> was called with a request job id ({jid:s}) for minions {minions:s}'.format(jid=jid, minions=repr(minions)))

    # Figure out the path that our job should be at
    jobp = '/'.join([path, Schema['job-cache'], jid])
    log.debug('sdstack_etcd returner <save_minions> adding minions for job {jid:s} to {path:s}'.format(jid=jid, path=jobp))

    # Iterate through all of the minions and add a directory for them to the job path
    for minion in set(minions):
        minionp = '/'.join([path, minion])
        res = client.write(minionp, None, dir=True)
        log.trace('sdstack_etcd returner <save_minions> added minion {id:s} for job {jid:s} to {path:s}'.format(id=minion, jid=jid, path=res.key))
    return


def _purge_jobs():
    write_profile = __opts__.get('etcd.returner_write_profile')
    client, path, _ = _get_conn(__opts__, write_profile)

    # Figure out the path that our jobs should exist at
    jobp = '/'.join([path, Schema['job-cache']])

    # Try and read the job directory. If we have a missing key exception then no
    # minions have returned anything yet and so we can simply leave.
    log.trace('sdstack_etcd returner <_purge_jobs> reading jobs at {path:s}'.format(path=jobp))
    try:
        jobs = client.read(jobp)
    except salt.utils.etcd_util.etcd.EtcdKeyNotFound as E:
        return 0

    # Iterate through all of the children at our job path while looking for
    # the .lock.p key. If one isn't found, then we can remove this job because
    # it has expired.
    count = 0
    for job in jobs.leaves:
        if not job.dir:
            log.warning('sdstack_etcd returner <_purge_jobs> found a non-job at {path:s} {expire:s}'.format(path=job.key, expire='that will need to be manually removed' if job.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=job.ttl)))
            continue

        # Build our lock path
        lockp = '/'.join([job.key, '.lock.p'])

        # Ping it to see if it's alive
        log.trace('sdstack_etcd returner <_purge_jobs> checking lock for job {jid:s} at {path:s}'.format(jid=job.key.split('/')[-1], path=lockp))
        try:
            client.read(lockp)

        # It's not, so the job is dead and we can remove it
        except etcd.EtcdKeyNotFound as E:
            res = client.delete(job.key, recursive=True)
            log.debug('sdstack_etcd returner <_purge_jobs> job {jid:s} at {path:s} has expired'.format(jid=res.key.split('/')[-1], path=res.key))
            count += 1
        continue
    log.trace('sdstack_etcd returner <_purge_jobs> purged {count:d} jobs'.format(count=count))
    return count


def _purge_events():
    write_profile = __opts__.get('etcd.returner_write_profile')
    client, path, _ = _get_conn(__opts__, write_profile)

    # Figure out the path that our event cache should exist at
    cachep = '/'.join([path, Schema['event-cache']])

    # Try and read the event cache directory. If we have a missing key exception then no
    # events have been cached and so we can simply leave.
    log.trace('sdstack_etcd returner <_purge_events> reading event cache at {path:s}'.format(path=cachep))
    try:
        cache = client.read(cachep)
    except etcd.EtcdKeyNotFound as E:
        return 0

    # Iterate through all of the children at our cache path while looking for
    # the id key. If one isn't found, then we can remove this event because
    # it has expired.
    count = 0
    for event in cache.leaves:
        if not event.dir:
            log.warning('sdstack_etcd returner <_purge_events> found a non-event at {path:s} {expire:s}'.format(path=event.key, expire='that will need to be manually removed' if event.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=event.ttl)))
            continue

        # Figure out the cache index from the key path
        try:
            index = int(event.key.split('/')[-1])
        except ValueError:
            log.warning('sdstack_etcd returner <_purge_events> found an incorrectly formatted event at {path:s} {expire:s}'.format(path=event.key, expire='that will need to be manually removed' if event.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=event.ttl)))
            continue

        # Build our index and tag paths
        ev_indexp = '/'.join([event.key, 'id'])
        ev_tagp = '/'.join([event.key, 'tag'])

        # Grab the actual tag from our ev_indexp in case we need to remove it. If this key
        # doesn't exist, then the current entry in our cache doesn't even matter
        # because we can't do anything without a tag
        log.trace('sdstack_etcd returner <_purge_events> reading tag for event index {index:d} at {path:s}'.format(index=index, path=ev_tagp))
        try:
            ev_tag = client.read(ev_tagp)

        except Exception as E:
            log.warning('sdstack_etcd returner <_purge_events> unable to find path to event for index {expire:s} which should be at {path:p}'.format(path=ev_tagp, expire='that will need to be manually removed' if event.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=event.ttl)))

            log.debug('sdstack_etcd returner <_purge_events> removing event cache at {path:s}'.format(path=event.key))
            client.delete(event.key, recursive=True)
            count += 1
            continue

        # Ping the index to see if it's alive
        log.trace('sdstack_etcd returner <_purge_events> reading modification index for event index {index:d} at {path:s}'.format(index=index, path=ev_indexp))
        try:
            ev_index = client.read(ev_indexp)
            alive = True

        # It's not, so the job is dead and we can remove it
        except etcd.EtcdKeyNotFound as E:
            alive = False

        # Cycle to the next event iteration if it's still alive
        if alive:
            log.trace('sdstack_etcd returner <_purge_events> event {index:d} at {path:s} is still alive'.format(index=index, path=event.key))
            continue

        ## Remove the event cache and its tag
        log.debug('sdstack_etcd returner <_purge_events> event {index:d} at {path:s} has expired'.format(index=index, path=event.key))

        # Remove the whole event cache entry
        log.trace('sdstack_etcd returner <_purge_events> (recursively) removing cache for event {index:d} at {path:s}'.format(index=index, path=event.key))
        res = client.delete(event.key, recursive=True)

        # Remove the old event tag
        log.trace('sdstack_etcd returner <_purge_events> removing tag for event {index:d} at {path:s}'.format(index=index, path=ev_tag.value))
        comp = ev_tag.value.split('/')
        try:
            res = client.delete('/'.join([path, Schema['event-path']] + comp), prevIndex=ev_index.value)

        except etcd.EtcdCompareFailed as E:
            log.warning('sdstack_etcd returner <_purge_events> event tag at {path:s} does not match modification index {mod:d}'.format(path=ev_tag.value, mod=ev_index.value))
            log.trace('sdstack_etcd returner <_purge_events> forcefully removing event tag at {path:s}'.format(path=ev_tag.value))
            res = client.delete('/'.join([path, Schema['event-path']] + comp))

        # Remove the last component (the key), so we can walk through the directories trying to remove them one-by-one
        comp.pop(-1)
        count += 1

        # Descend trying to clean up every parent directory
        log.debug('sdstack_etcd returner <_purge_events> recursively removing directories for event {index:d} at {path:s}'.format(index=index, path='/'.join(comp[:i])))
        for i in range(len(comp), 0, -1):
            log.trace('sdstack_etcd returner <_purge_events> removing directory for event {index:d} at {path:s}'.format(index=index, path='/'.join(comp[:i])))
            try:
                client.delete('/'.join([path, Schema['event-path']] + comp[:i]), dir=True)
            except Exception as E:
                log.debug('sdstack_etcd returner <_purge_events> exception ({exception:s}) was raised while trying to remove directory at {path:s}'.format(path='/'.join([path, Schema['event-path']], comp[:i]), exception=E))
                break;
            continue
        continue
    return count


def clean_old_jobs():
    '''
    Called in the master's event loop every loop_interval. Removes any jobs,
    and returns that are older than the etcd.ttl option (seconds), or the
    keep_jobs option (hours).

    :return:
    '''

    jobc = _purge_jobs()
    if jobc > 0:
        log.trace('sdstack_etcd returner <clean_old_jobs> successfully removed {count:d} jobs'.format(count=jobc))

    eventsc = _purge_events()
    if eventsc > 0:
        log.trace('sdstack_etcd returner <clean_old_jobs> successfully removed {count:d} events'.format(count=eventsc))

    log.debug('sdstack_etcd returner <clean_old_jobs> completed purging jobs and events')


def get_load(jid):
    '''
    Return the load data that marks a specified jid.
    '''
    read_profile = __opts__.get('etcd.returner_read_profile')
    client, path, _ = _get_conn(__opts__, read_profile)

    # Figure out the path that our job should be at
    loadp = '/'.join([path, Schema['job-cache'], jid, '.load.p'])
    log.debug('sdstack_etcd returner <get_load> reading load data for job {jid:s} from {path:s}'.format(jid=jid, path=loadp))

    # Read it. If EtcdKeyNotFound was raised then the key doesn't exist and so
    # we need to return None, because that's what our caller expects on a
    # non-existent job.
    try:
        res = client.read(loadp)
    except etcd.EtcdKeyNotFound as E:
        log.error("sdstack_etcd returner <get_load> could not find job {jid:s} at the path {path:s}".format(jid=jid, path=loadp))
        return None
    log.trace('sdstack_etcd returner <get_load> found load data for job {jid:s} at {path:s} with value {data}'.format(jid=jid, path=res.key, data=res.value))
    return salt.utils.json.loads(res.value)


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed.
    '''
    client, path, _ = _get_conn(__opts__)

    # Figure out the path that our job should be at
    jobp = '/'.join([path, Schema['job-cache'], jid])

    # Try and read the job directory. If we have a missing key exception then no
    # minions have returned anything yet and so we return an empty dict for the
    # caller.
    log.debug('sdstack_etcd returner <get_jid> reading job fields for job {jid:s} from {path:s}'.format(jid=jid, path=jobp))
    try:
        items = client.read(jobp)
    except etcd.EtcdKeyNotFound as E:
        return {}

    # Iterate through all of the children at our job path that are directories.
    # Anything that is a directory should be a minion that contains some results.
    log.debug('sdstack_etcd returner <get_jid> iterating through minion results for job {jid:s} from {path:s}'.format(jid=items.key.split('/')[-1], path=items.key))
    ret = {}
    for item in items.leaves:
        if not item.dir:
            continue

        # Extract the minion name from the key in the job, and use it to build
        # the path to the return value
        comps = str(item.key).split('/')
        returnp = '/'.join([path, Schema['job-cache'], jid, comps[-1], 'return'])

        # Now we know the minion and the path to the return for its job, we can
        # just grab it. If the key exists, but the value is missing entirely,
        # then something that shouldn't happen has happened.
        log.trace('sdstack_etcd returner <get_jid> grabbing result from minion {id:s} for job {jid:s} at {path:s}'.format(id=comps[-1], jid=jid, path=items.returnp))
        try:
            res = client.read(returnp)
        except etcd.EtcdKeyNotFound as E:
            log.debug("sdstack_etcd returner <get_jid> returned nothing from minion {id:s} for job {jid:s} at {path:s}".format(id=comps[-1], jid=jid, path=returnp))
            continue

        # We found something, so update our return dict with the minion id and
        # the result that it returned.
        ret[comps[-1]] = {'return': salt.utils.json.loads(res.value)}
        log.trace("sdstack_etcd returner <get_jid> job {jid:s} from minion {id:s} at path {path:s} returned {result}".format(id=comps[-1], jid=jid, path=res.key, result=res.value))
    return ret


def get_fun(fun):
    '''
    Return a dict containing the last function called for all the minions that have called a function.
    '''
    client, path, _ = _get_conn(__opts__)

    # Find any minions that had their last function registered by returner()
    minionsp = '/'.join([path, Schema['minion-fun']])

    # If the minions key isn't found, then no minions registered a function
    # and thus we need to return an empty dict so the caller knows that
    # nothing is available.
    log.debug('sdstack_etcd returner <get_fun> reading minions at {path:s} for function {fun:s}'.format(path=minionsp, fun=fun))
    try:
        items = client.read(minionsp)
    except etcd.EtcdKeyNotFound as E:
        return {}

    # Walk through the list of all the minions that have a jid registered,
    # and cross reference this with the job returns.
    log.debug('sdstack_etcd returner <get_fun> iterating through minions for function {fun:s} at {path:s}'.format(fun=fun, path=items.key))
    ret = {}
    for item in items.leaves:

        # Now that we have a minion and it's last jid, we use it to fetch the
        # function field (fun) that was registered by returner().
        comps = str(item.key).split('/')
        funp = '/'.join([path, Schema['job-cache'], str(item.value), comps[-1], 'fun'])

        # Try and read the field, and skip it if it doesn't exist or wasn't
        # registered for some reason.
        log.trace('sdstack_etcd returner <get_fun> reading function from minion {id:s} for job {jid:s} at {path:s}'.format(id=comps[-1], jid=str(item.value), path=funp))
        try:
            res = client.read(funp)
        except etcd.EtcdKeyNotFound as E:
            log.debug("sdstack_etcd returner <get_fun> returned nothing from minion {id:s} for job {jid:s} at path {path:s}".format(id=comps[-1], jid=str(item.value), path=funp))
            continue

        # Check if the function field (fun) matches what the user is looking for
        # If it does, then we can just add the minion to our results
        log.trace('sdstack_etcd returner <get_fun> decoding json data from minion {id:s} for job {jid:s} at {path:s}'.format(id=comps[-1], jid=str(item.value), path=funp))
        data = salt.utils.json.loads(res.value)
        if data == fun:
            ret[comps[-1]] = str(data)
            log.trace("sdstack_etcd returner <get_fun> found job {jid:s} for minion {id:s} using {fun:s} at {path:s}".format(jid=comps[-1], fun=data, id=item.value, path=item.key))
        continue
    return ret


def get_jids():
    '''
    Return a list of all job ids that have returned something.
    '''
    client, path, _ = _get_conn(__opts__)

    # Enumerate all the jobs that are available.
    jobsp = '/'.join([path, Schema['job-cache']])

    # Fetch all the jobs. If the key doesn't exist, then it's likely that no
    # jobs have been created yet so return an empty list to the caller.
    log.debug("sdstack_etcd returner <get_jids> listing jobs at {path:s}".format(path=jobsp))
    try:
        items = client.read(jobsp)
    except etcd.EtcdKeyNotFound as E:
        return []

    # Anything that's a directory is a job id. Since that's all we're returning,
    # aggregate them into a list.
    log.debug("sdstack_etcd returner <get_jids> iterating through jobs at {path:s}".format(path=items.key))
    ret = []
    for item in items.leaves:
        comps = str(item.key).split('/')
        if item.dir:
            jid = comps[-1]
            ret.append(jid)
            log.trace("sdstack_etcd returner <get_jids> found job {jid:s} at {path:s}".format(jid=comps[-1], path=item.key))
        continue
    return ret


def get_minions():
    '''
    Return a list of all minions that have returned something.
    '''
    client, path, _ = _get_conn(__opts__)

    # Find any minions that have returned anything
    minionsp = '/'.join([path, Schema['minion-fun']])

    # If no minions were found, then nobody has returned anything recently. In
    # this case, return an empty last for the caller.
    log.debug('sdstack_etcd returner <get_minions> reading minions at {path:s}'.format(path=minionsp))
    try:
        items = client.read(minionsp)
    except etcd.EtcdKeyNotFound as E:
        return []

    # We can just walk through everything that isn't a directory. This path
    # is simply a list of minions and the last job that each one returned.
    log.debug('sdstack_etcd returner <get_minions> iterating through minions at {path:s}'.format(path=items.key))
    ret = []
    for item in items.leaves:
        if not item.dir:
            comps = str(item.key).split('/')
            ret.append(comps[-1])
            log.trace("sdstack_etcd returner <get_minions> found minion {id:s} at {path:s}".format(id=comps[-1], path=item.key))
        continue
    return ret


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id.
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)


def event_return(events):
    '''
    Return event to etcd server

    Requires that configuration enabled via 'event_return'
    option in master config.
    '''
    write_profile = __opts__.get('etcd.returner_write_profile')
    client, path, ttl = _get_conn(__opts__, write_profile)

    # Iterate through all the events, and add them to the events path based
    # on the tag that is labeled in each event. We aggregate all errors into
    # a list so the writing of the events are as atomic as possible.
    log.debug("sdstack_etcd returner <event_return> iterating through {count:d} events to write into our profile".format(count=len(events)))
    exceptions = []
    for event in events:

        # Package the event data into a value to write into our etcd profile
        package = {
            'tag': event.get('tag', ''),
            'data': event.get('data', ''),
            'master_id': __opts__['id'],
        }

        # Use the tag from the event package to build a watchable path
        eventp = '/'.join([path, Schema['event-path'], package['tag']])

        # Now we can write the event package into the event path
        log.debug("sdstack_etcd returner <event_return> writing package into event path at {path:s}".format(path=eventp))
        try:
            json = salt.utils.json.dumps(package)
            res = client.write(eventp, json)

        except Exception as E:
            log.trace("sdstack_etcd returner <event_return> unable to write event with the tag {name:s} into the path {path:s} due to exception ({exception}) being raised".format(name=package['tag'], path=eventp, exception=E))
            exceptions.append((E, package))
            continue

        log.trace("sdstack_etcd returner <event_return> wrote event ({index:d}) with the tag {name:s} to {path:s} using {data}".format(path=res.key, name=package['tag'], data=res.value, index=res.createdIndex))

        # Next we need to cache the index for said event so that we can use it to
        # determine whether it is ready to be purged or not. We do this by using
        # the modifiedIndex to write the tag into a cache.

        try:
            # If the event is a new key, then we can simply cache it with the specified ttl
            if res.newKey:
                log.trace("sdstack_etcd returner <event_return> writing new id ({id:d}) to {path:s} for the new event {index:d} with the tag {name:s} {expire:s}".format(path='/'.join([path, Schema['event-cache'], str(res.createdIndex), 'id']), id=res.createdIndex, index=res.modifiedIndex, name=package['tag'], expire='that will need to be manually removed' if ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=ttl)))
                client.write('/'.join([path, Schema['event-cache'], str(res.createdIndex), 'id']), res.modifiedIndex, prevExist=False, ttl=ttl if ttl > 0 else None)

            # Otherwise, the event was updated and thus we need to update our cache too
            else:
                log.trace("sdstack_etcd returner <event_return> updating id ({id:s}) at {path:s} for the new event {index:d} with the tag {name:s} {expire:s}".format(path='/'.join([path, Schema['event-cache'], str(res.createdIndex), 'id']), id=res.createdIndex, index=res.modifiedIndex, name=package['tag'], expire='that will need to be manually removed' if ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=ttl)))
                client.write('/'.join([path, Schema['event-cache'], str(res.createdIndex), 'id']), res.modifiedIndex, prevValue=res._prev_node.modifiedIndex, ttl=ttl if ttl > 0 else None)

        except etcd.EtcdCompareFailed as E:
            log.error("sdstack_etcd returner <event_return> unable to update cache for {index:d} due to non-matching modification index ({mod:d})".format(index=res.createdIndex, mod=res._prev_node.modifiedIndex))

        except etcd.EtcdAlreadyExist as E:
            log.error("sdstack_etcd returner <event_return> unable to cache event for {index:d} due to event already existing".format(index=res.createdIndex))

        # If we got here, then we should be able to write the tag under the current index
        try:
            log.trace("sdstack_etcd returner <event_return> updating cached tag at {path:s} for the event {index:d} with the tag {name:s}".format(path='/'.join([path, Schema['event-cache'], str(res.createdIndex), 'tag']), index=res.createdIndex, name=package['tag']))
            client.write('/'.join([path, Schema['event-cache'], str(res.createdIndex), 'tag']), package['tag'])

        except Exception as E:
            log.trace("sdstack_etcd returner <event_return> unable to cache tag {name:s} under index {index:d} due to exception ({exception}) being raised".format(name=package['tag'], index=res.createdIndex, exception=E))
            exceptions.append((E, package))

        continue

    # Go back through all of the exceptions that occurred and log them.
    for e, pack in exceptions:
        log.exception("sdstack_etcd returner <event_return> exception ({exception}) was raised while trying to write event {name:s} with the data {data}".format(exception=e, name=pack['tag'], data=pack))
    return
