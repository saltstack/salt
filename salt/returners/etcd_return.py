# -*- coding: utf-8 -*-
'''
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

The contents if ".lock.p" contains the modifiedIndex of the of the ".load.p"
key and when configured via the "etcd.ttl" or "keep_jobs" will have the ttl
applied to it. When this file is expired via the ttl or explicitly removed by
the administrator, the job will then be scheduled for removal.

event
+++++
This key is essentially a namespace for all of the events (packages) that are
submitted to the returner. When an event is received, the package for the event
is written under this key using the "tag" parameter for its path. The
modifiedIndex for this key is then cached as the event id although the event id
can actually be arbitrary since the "index" key contains the real modifiedIndex
of the package key.

minion.job
++++++++++
Underneath the minion.job key is a list of minions ids. Each minion id contains
the jid of the last job that was returned by the minion. This key is used to
support the external job cache feature of Salt.

event.cache
+++++++++++
Underneath this key is a list of all of the events that were received by the
returner. As mentioned before, each event is identified by the modifiedIndex
of the key containing the event package. Underneath each event, there are
three sub-keys. These are the "index" key, the "tag" key, and the "lock" key.

The "index" key contains the modifiedIndex of the package that was stored under
the event key. This is used to determine the original creator for the event's
package and is used to keep track of whether the package for the event has
been modified by another event (since event tags can be overwritten preserving
the semantics of the original etcd returner).

The "lock" key is responsible for informing the maintenance service that the
event is still in use. If the returner is configured via the "etcd.ttl" or
the "keep_jobs" option, this key will have the ttl applied to it. When
the "lock" key has expired or is explicitly removed by the administrator, the
event and its tag will be scheduled for removal. The createdIndex for the
package path is written to this key in case an application wishes to identify
the package path by an index.

The other key under an event, is the "tag" key. The "tag" key simply contains
the path to the package that was registered as the tag attribute for the event.
The value of the "index" key corresponds to the modifiedIndex of this particular
path.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import time

# Import salt libs
import salt.utils.jid
import salt.utils.json
from salt.ext.six.moves import range
try:
    import salt.utils.etcd_util
    from salt.utils.etcd_util import etcd
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)

Schema = {
    "minion-fun": 'minion.job',
    "package-path": 'event',
    "event-cache": 'event.cache',
    "job-cache": 'job',
}

# Define the module's virtual name
__virtualname__ = 'etcd'


def __virtual__():
    '''
    Only return if python-etcd is installed
    '''
    if HAS_LIBS:
        return __virtualname__

    return False, 'Could not import etcd returner; python-etcd is not installed.'


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

    # If a minion is returning a standalone job, update the jid for the load
    # when it's saved since this job came directly from a minion.
    if ret['jid'] == 'req':
        new_jid = prep_jid(nocache=ret.get('nocache', False))
        log.debug('sdstack_etcd returner <returner> satisfying a new job id request ({jid:s}) with id {new:s} for {data}'.format(jid=ret['jid'], new=new_jid, data=ret))
        ret['jid'] = new_jid
        save_load(new_jid, ret)

    # Update the given minion in the external job cache with the current (latest job)
    # This is used by get_fun() to return the last function that was called
    minionp = '/'.join([path, Schema['minion-fun'], ret['id']])

    # We can use the ttl here because our minionp is actually linked to the job
    # which will expire according to the ttl anyways..
    log.debug("sdstack_etcd returner <returner> updating (last) job id of {minion:s} at {path:s} with job {jid:s}".format(jid=ret['jid'], minion=ret['id'], path=minionp))
    res = client.write(minionp, ret['jid'], ttl=ttl if ttl > 0 else None)
    if not res.newKey:
        log.debug("sdstack_etcd returner <returner> the previous job id {old:s} for {minion:s} at {path:s} was set to {new:s}".format(old=res._prev_node.value, minion=ret['id'], path=minionp, new=res.value))

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
            log.trace("sdstack_etcd returner <returner> unable to set field {field:s} for job {jid:s} at {path:s} to {result} due to exception ({exception})".format(field=field, jid=ret['jid'], path=fieldp, result=ret[field], exception=E))
            exceptions.append((E, field, ret[field]))
            continue
        log.trace("sdstack_etcd returner <returner> set field {field:s} for job {jid:s} at {path:s} to {result}".format(field=field, jid=ret['jid'], path=res.key, result=ret[field]))

    # Go back through all the exceptions that occurred while trying to write the
    # fields and log them.
    for E, field, value in exceptions:
        log.exception("sdstack_etcd returner <returner> exception ({exception}) was raised while trying to set the field {field:s} for job {jid:s} to {value}".format(exception=E, field=field, jid=ret['jid'], value=value))
    return


def save_load(jid, load, minions=None):
    '''
    Save the load to the specified jid.
    '''
    write_profile = __opts__.get('etcd.returner_write_profile')
    client, path, ttl = _get_conn(__opts__, write_profile)

    # Check if the specified jid is 'req', as only incorrect code will do this
    if jid == 'req':
        log.debug('sdstack_etcd returner <save_load> was called using a request job id ({jid:s}) with {data:s}'.format(jid=jid, data=load))

    # Build the paths that we'll use for registration of our job
    loadp = '/'.join([path, Schema['job-cache'], jid, '.load.p'])
    lockp = '/'.join([path, Schema['job-cache'], jid, '.lock.p'])

    ## Now we can just store the current load
    json = salt.utils.json.dumps(load)

    log.debug('sdstack_etcd returner <save_load> storing load data for job {jid:s} to {path:s} with {data:s}'.format(jid=jid, path=loadp, data=load))
    try:
        res = client.write(loadp, json, prevExist=False)

    # If the key already exists, then warn the user and update the key. There
    # isn't anything we can really do about this because it's up to Salt really.
    except etcd.EtcdAlreadyExist as E:
        node = client.read(loadp)
        node.value = json

        log.debug('sdstack_etcd returner <save_load> updating load data for job {jid:s} at {path:s} with {data:s}'.format(jid=jid, path=loadp, data=load))
        res = client.update(node)

    # If we failed here, it's okay because the lock won't get written so this
    # essentially means the job will get scheduled for deletion.
    except Exception as E:
        log.trace("sdstack_etcd returner <save_load> unable to store load for job {jid:s} to the path {path:s} due to exception ({exception}) being raised".format(jid=jid, path=loadp, exception=E))
        return

    # Check if the previous node value and the current node value are different
    # so we can let the user know that something changed and that some data
    # might've been lost.
    try:
        if not res.newKey:
            d1, d2 = salt.utils.json.loads(res.value), salt.utils.json.loads(res._prev_node.value)
            j1, j2 = salt.utils.json.dumps(res.value, sort_keys=True), salt.utils.json.dumps(res._prev_node.value, sort_keys=True)
            if j1 != j2:
                log.warning("sdstack_etcd returner <save_load> overwrote the load data for job {jid:s} at {path:s} with {data:s}. Old data was {old:s}".format(jid=jid, path=res.key, data=d1, old=d2))
    except Exception as E:
        log.debug("sdstack_etcd returner <save_load> unable to compare load data for job {jid:s} at {path:s} due to exception ({exception}) being raised".format(jid=jid, path=loadp, exception=E))
        if not res.newKey:
            log.trace("sdstack_etcd returner <save_load> -- old load data for job {jid:s}: {data:s}".format(jid=jid, data=res._prev_node.value))
        log.trace("sdstack_etcd returner <save_load> -- new load data for job {jid:s}: {data:s}".format(jid=jid, data=res.value))

    # Since this is when a job is being created, create a lock that we can
    # check to see if the job has expired. This allows a user to signal to
    # salt that it's okay to remove the entire key by removing this lock.
    log.trace('sdstack_etcd returner <save_load> writing lock file for job {jid:s} at {path:s} using index {index:d}'.format(jid=jid, path=lockp, index=res.modifiedIndex))

    try:
        res = client.write(lockp, res.modifiedIndex, ttl=ttl if ttl > 0 else None)
        if res.ttl is not None:
            log.trace('sdstack_etcd returner <save_load> job {jid:s} at {path:s} will expire in {ttl:d} seconds'.format(jid=jid, path=res.key, ttl=res.ttl))

    except Exception as E:
        log.trace("sdstack_etcd returner <save_load> unable to write lock for job {jid:s} to the path {path:s} due to exception ({exception}) being raised".format(jid=jid, path=lockp, exception=E))

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
        log.debug('sdstack_etcd returner <save_minions> was called with a request job id ({jid:s}) for minions {minions:s}'.format(jid=jid, minions=repr(minions)))

    # Figure out the path that our job should be at
    jobp = '/'.join([path, Schema['job-cache'], jid])
    loadp = '/'.join([jobp, '.load.p'])

    # Now we can try and read the load out of it.
    try:
        load = client.read(loadp)

    # If it doesn't exist, then bitch and complain because somebody lied to us
    except etcd.EtcdKeyNotFound as E:
        log.error('sdstack_etcd returner <save_minions> was called with an invalid job id ({jid:s}) for minions {minions:s}'.format(jid=jid, minions=repr(minions)))
        return

    log.debug('sdstack_etcd returner <save_minions> adding minions{syndics:s} for job {jid:s} to {path:s}'.format(jid=jid, path=jobp, syndics='' if syndic_id is None else ' from syndic {0}'.format(syndic_id)))

    # Iterate through all of the minions we received and update both the job
    # and minion-fun cache with what we know. Most of the other returners
    # don't do this, but it is definitely being called and is necessary for
    # syndics to actually work.
    exceptions = []
    for minion in minions:
        minionp = '/'.join([path, Schema['minion-fun'], minion])

        # Go ahead and write the job to the minion-fun cache and log if we've
        # overwritten an already existing job id.
        log.debug('sdstack_etcd returner <save_minions> writing (last) job id of {minion:s}{syndics:s} at {path:s} with job {jid:s}'.format(jid=jid, path=minionp, minion=minion, syndics='' if syndic_id is None else ' from syndic {0}'.format(syndic_id)))
        try:
            client.write(minionp, jid, ttl=load.ttl, prevExist=False)

        # If the minion already exists, then that's fine as we'll just update it
        # and move on.
        except etcd.EtcdAlreadyExist as E:
            node = client.read(minionp)

            log.debug('sdstack_etcd returner <save_minions> updating previous job id ({old:s}) of {minion:s}{syndics:s} at {path:s} with job {jid:s}'.format(old=node.value, minion=minion, jid=jid, path=node.key, syndics='' if syndic_id is None else ' from syndic {0}'.format(syndic_id)))

            node.value = jid
            client.update(node)

        except Exception as E:
            log.trace("sdstack_etcd returner <save_minions> unable to write job id {jid:s} for minion {minion:s} to {path:s} due to exception ({exception})".format(jid=jid, minion=minion, path=minionp, exception=E))
            exceptions.append((E, 'job', minion))

        # Now we can try and update the job. We don't have much, just the jid,
        # the minion, and the master id (syndic_id)
        resultp = '/'.join([jobp, minion])

        # One... (jid)
        try:
            res = client.write('/'.join([resultp, 'jid']), jid)

        except Exception as E:
            log.trace("sdstack_etcd returner <save_minions> unable to write job id {jid:s} to the result for the minion {minion:s} at {path:s} due to exception ({exception})".format(jid=jid, minion=minion, path='/'.join([resultp, 'jid']), exception=E))
            exceptions.append((E, 'result.jid', minion))

        # Two... (id)
        try:
            res = client.write('/'.join([resultp, 'id']), minion)

        except Exception as E:
            log.trace("sdstack_etcd returner <save_minions> unable to write minion id {minion:s} to the result for job {jid:s} at {path:s} due to exception ({exception})".format(jid=jid, minion=minion, path='/'.join([resultp, 'id']), exception=E))
            exceptions.append((E, 'result.id', minion))

        # Three... (master_id)
        try:
            if syndic_id is not None:
                res = client.write('/'.join([resultp, 'master_id']), syndic_id)

        except Exception as E:
            log.trace("sdstack_etcd returner <save_minions> unable to write master_id {syndic:s} to the result for job {jid:s} at {path:s} due to exception ({exception})".format(jid=jid, path='/'.join([resultp, 'master_id']), syndic=syndic_id, exception=E))
            exceptions.append((E, 'result.master_id', minion))

        # Crruuunch.

    # Go back through all the exceptions that occurred while trying to write the
    # fields and log them.
    for E, field, minion in exceptions:
        if field == 'job':
            log.exception("sdstack_etcd returner <save_minions> exception ({exception}) was raised while trying to update the function cache for minion {minion:s} to job {jid:s}".format(exception=E, minion=minion, jid=jid))
            continue
        log.exception("sdstack_etcd returner <save_minions> exception ({exception}) was raised while trying to update the {field:s} field in the result for job {jid:s} belonging to minion {minion:s}".format(exception=E, field=field, minion=minion, jid=jid))
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
    except etcd.EtcdKeyNotFound as E:
        log.debug('sdstack_etcd returner <_purge_jobs> no jobs were found at {path:s}'.format(path=jobp))
        return 0

    # Iterate through all of the children at our job path while looking for
    # the .lock.p key. If one isn't found, then we can remove this job because
    # it has expired.
    count = 0
    for job in jobs.leaves:
        if not job.dir:
            log.warning('sdstack_etcd returner <_purge_jobs> found a non-job at {path:s} {expire:s}'.format(path=job.key, expire='that will need to be manually removed' if job.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=job.ttl)))
            continue
        jid = job.key.split('/')[-1]

        # Build our lock path that we'll use to see if the job is alive
        lockp = '/'.join([job.key, '.lock.p'])

        # Ping it to see if it's alive
        log.trace('sdstack_etcd returner <_purge_jobs> checking lock for job {jid:s} at {path:s}'.format(jid=jid, path=lockp))
        try:
            res = client.read(lockp)

            log.debug('sdstack_etcd returner <_purge_jobs> job {jid:s} at {path:s} is still alive and {expire:s}'.format(jid=jid, path=res.key, expire='will need to be manually removed' if res.ttl is None else 'will expire in {ttl:d} seconds'.format(ttl=res.ttl)))

        # It's not, so the job is dead and we can remove it
        except etcd.EtcdKeyNotFound as E:
            log.debug('sdstack_etcd returner <_purge_jobs> job {jid:s} at {path:s} has expired'.format(jid=jid, path=lockp))

            res = client.delete(job.key, recursive=True)
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
    for ev in cache.leaves:
        if not ev.dir:
            log.warning('sdstack_etcd returner <_purge_events> found a non-event at {path:s} {expire:s}'.format(path=ev.key, expire='that will need to be manually removed' if ev.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=ev.ttl)))
            continue

        # Figure out the event id from the key path
        try:
            event = int(ev.key.split('/')[-1])
        except ValueError:
            log.warning('sdstack_etcd returner <_purge_events> found an incorrectly structured event at {path:s} {expire:s}'.format(path=ev.key, expire='that will need to be manually removed' if ev.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=ev.ttl)))
            continue

        # Build all of the event paths that we're going to use
        ev_lockp = '/'.join([ev.key, 'lock'])
        ev_indexp = '/'.join([ev.key, 'index'])
        ev_tagp = '/'.join([ev.key, 'tag'])

        # Ping the event lock to see if it's actually alive
        try:
            ev_lock = client.read(ev_lockp)

            log.debug('sdstack_etcd returner <_purge_events> event {event:d} at {path:s} is still alive and {expire:s}'.format(event=event, path=ev.key, expire='will need to be manually removed' if ev_lock.ttl is None else 'will expire in {ttl:d} seconds'.format(ttl=ev_lock.ttl)))
            continue

        except etcd.EtcdKeyNotFound as E:
            log.debug('sdstack_etcd returner <_purge_events> event {event:d} at {path:s} has expired and will be removed'.format(event=event, path=ev.key))

        # Now that we know the event is dead, we can read the index so that
        # we can check it against the actual event later.
        log.trace('sdstack_etcd returner <_purge_events> reading modifiedIndex for event {event:d} at {path:s}'.format(event=event, path=ev_indexp))
        try:
            ev_index = client.read(ev_indexp)

        # If we can't find the index here, then we just remove the event because
        # we have no way to detect whether the event tag actually belongs to us.
        # So in this case, we're done.
        except etcd.EtcdKeyNotFound as E:
            log.warning('sdstack_etcd returner <_purge_events> event {event:d} at {path:s} is corrupt (missing id) and will be removed'.format(event=event, path=ev.key))

            log.debug('sdstack_etcd returner <_purge_events> removing corrupt event {event:d} at {path:s}'.format(event=event, path=ev.key))
            res = client.delete(ev.key, recursive=True)

            count += 1
            continue

        # Now we grab the tag because this is what we'll check the ev_index against
        log.trace('sdstack_etcd returner <_purge_events> reading tag for event {event:d} at {path:s}'.format(event=event, path=ev_tagp))
        try:
            ev_tag = client.read(ev_tagp)

        # If the tag key doesn't exist, then the current entry in our cache doesn't
        # even matter because we can't do anything without a tag. So similar to
        # before, we just remove it and cycle to the next event.
        except etcd.EtcdKeyNotFound as E:
            log.warning('sdstack_etcd returner <_purge_events> event {event:d} at {path:s} is corrupt (missing tag) and will be removed'.format(event=event, path=ev.key))

            log.debug('sdstack_etcd returner <_purge_events> removing corrupt event {event:d} at {path:s}'.format(event=event, path=ev.key))
            client.delete(ev.key, recursive=True)

            count += 1
            continue

        ## Everything is valid, so now we can properly remove the package (if the
        ## current event is the owner), and then we can remove the cache entry.

        # Remove the package associated with the current event index
        log.trace('sdstack_etcd returner <_purge_events> removing package for event {event:d} at {path:s}'.format(event=event, path=ev_tag.value))
        packagep = ev_tag.value.split('/')

        # Try and remove the package path that was cached while checking that
        # its modifiedIndex is what we expect. If it's not, then we know that
        # we're not the only person that's using this event and so we don't
        # need to delete it yet, because another event will do it eventually.
        basep = [path, Schema['package-path']]
        try:
            res = client.delete('/'.join(basep + packagep), prevIndex=ev_index.value)

        # Our package is in use by someone else, so we can simply remove the cache
        # entry and then cycle to the next event.
        except etcd.EtcdCompareFailed as E:
            log.debug('sdstack_etcd returner <_purge_events> refusing to remove package for event {event:d} at {path:s} as it is still in use'.format(event=event, path='/'.join(basep + packagep[:])))
            count += 1

            # Remove the whole event cache entry
            log.debug('sdstack_etcd returner <_purge_events> removing (duplicate) event {event:d} at {path:s}'.format(event=event, path=ev.key))
            res = client.delete(ev.key, recursive=True)
            continue

        # Walk through each component of the package path trying to remove them unless the directory is not empty
        packagep.pop(-1)
        log.debug('sdstack_etcd returner <_purge_events> (recursively) removing parent keys for event {event:d} package at {path:s}'.format(event=event, path='/'.join(basep + packagep[:])))
        for i in range(len(packagep), 0, -1):
            log.trace('sdstack_etcd returner <_purge_events> removing directory for event {event:d} package at {path:s}'.format(event=event, path='/'.join(basep + packagep[:i])))
            try:
                client.delete('/'.join(basep + packagep[:i]), dir=True)
            except etcd.EtcdDirNotEmpty as E:
                log.debug('sdstack_etcd returner <_purge_events> Unable to remove directory for event {event:d} package at {path:s} due to other tags under it still being in use ({exception})'.format(path='/'.join(basep + packagep[:i]), event=event, exception=E))
                break
            continue

        # Remove the whole event cache entry now that we've properly removed the package
        log.debug('sdstack_etcd returner <_purge_events> removing event {event:d} at {path:s}'.format(event=event, path=ev.key))
        res = client.delete(ev.key, recursive=True)

        count += 1

    return count


def clean_old_jobs():
    '''
    Called in the master's event loop every loop_interval. Removes any jobs,
    and returns that are older than the etcd.ttl option (seconds), or the
    keep_jobs option (hours).

    :return:
    '''

    # First we'll purge the jobs...
    jobc = _purge_jobs()
    if jobc > 0:
        log.trace('sdstack_etcd returner <clean_old_jobs> successfully removed {count:d} jobs'.format(count=jobc))

    # ...and then we'll purge the events
    eventsc = _purge_events()
    if eventsc > 0:
        log.trace('sdstack_etcd returner <clean_old_jobs> successfully removed {count:d} events'.format(count=eventsc))

    # Log that we hit a cleanup iteration
    log.debug('sdstack_etcd returner <clean_old_jobs> completed purging jobs and events')


def get_load(jid):
    '''
    Return the load data that marks a specified jid.
    '''
    read_profile = __opts__.get('etcd.returner_read_profile')
    client, path, _ = _get_conn(__opts__, read_profile)

    # Figure out the path that our job should be at
    loadp = '/'.join([path, Schema['job-cache'], jid, '.load.p'])

    # Read it. If EtcdKeyNotFound was raised then the key doesn't exist and so
    # we need to return None, because that's what our caller expects on a
    # non-existent job.
    log.debug('sdstack_etcd returner <get_load> reading load data for job {jid:s} from {path:s}'.format(jid=jid, path=loadp))
    try:
        res = client.read(loadp)
    except etcd.EtcdKeyNotFound as E:
        log.error("sdstack_etcd returner <get_load> could not find job {jid:s} at the path {path:s}".format(jid=jid, path=loadp))
        return None
    log.debug('sdstack_etcd returner <get_load> found load data for job {jid:s} at {path:s} with value {data}'.format(jid=jid, path=res.key, data=res.value))
    return salt.utils.json.loads(res.value)


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed.
    '''
    client, path, _ = _get_conn(__opts__)

    # Figure out the path that our job should be at
    resultsp = '/'.join([path, Schema['job-cache'], jid])

    # Try and read the job directory. If we have a missing key exception then no
    # minions have returned anything yet and so we return an empty dict for the
    # caller.
    log.debug('sdstack_etcd returner <get_jid> reading minions that have returned results for job {jid:s} at {path:s}'.format(jid=jid, path=resultsp))
    try:
        results = client.read(resultsp)
    except etcd.EtcdKeyNotFound as E:
        log.trace('sdstack_etcd returner <get_jid> unable to read job {jid:s} from {path:s}'.format(jid=jid, path=resultsp))
        return {}

    # Iterate through all of the children at our job path that are directories.
    # Anything that is a directory should be a minion that contains some results.
    log.debug('sdstack_etcd returner <get_jid> iterating through minions with results for job {jid:s} from {path:s}'.format(jid=results.key.split('/')[-1], path=results.key))
    ret = {}
    for item in results.leaves:
        if not item.dir:
            continue

        # Extract the minion name from the key in the job, and use it to build
        # the path to the return value
        comps = item.key.split('/')
        returnp = '/'.join([resultsp, comps[-1], 'return'])

        # Now we know the minion and the path to the return for its job, we can
        # just grab it. If the key exists, but the value is missing entirely,
        # then something that shouldn't happen has happened.
        log.trace('sdstack_etcd returner <get_jid> grabbing result from minion {minion:s} for job {jid:s} at {path:s}'.format(minion=comps[-1], jid=jid, path=returnp))
        try:
            result = client.read(returnp, recursive=True)
        except etcd.EtcdKeyNotFound as E:
            log.debug("sdstack_etcd returner <get_jid> returned nothing from minion {minion:s} for job {jid:s} at {path:s}".format(minion=comps[-1], jid=jid, path=returnp))
            continue

        # Aggregate any keys that we found into a dictionary
        res = {}
        for item in result.leaves:
            name = item.key.split('/')[-1]
            try:
                res[name] = salt.utils.json.loads(item.value)

            # We use a general exception here instead of ValueError jic someone
            # changes the semantics of salt.utils.json.loads out from underneath us
            except Exception as E:
                log.warning("sdstack_etcd returner <get_jid> unable to decode field {name:s} from minion {minion:s} for job {jid:s} at {path:s}".format(minion=comps[-1], jid=jid, path=item.key, name=name))
                res[name] = item.value
            continue

        # We found something, so update our return dict for the minion id with
        # the results that it returned.
        ret[comps[-1]] = res
        log.debug("sdstack_etcd returner <get_jid> job {jid:s} from minion {minion:s} at path {path:s} returned {result}".format(minion=comps[-1], jid=jid, path=result.key, result=res))
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
        minions = client.read(minionsp)
    except etcd.EtcdKeyNotFound as E:
        return {}

    # Walk through the list of all the minions that have a jid registered,
    # and cross reference this with the job returns.
    log.debug('sdstack_etcd returner <get_fun> iterating through minions for function {fun:s} at {path:s}'.format(fun=fun, path=minions.key))
    ret = {}
    for minion in minions.leaves:
        if minion.dir:
            log.warning('sdstack_etcd returner <get_fun> found a non-minion at {path:s} {expire:s}'.format(path=minion.key, expire='that will need to be manually removed' if minion.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=minion.ttl)))
            continue

        # Now that we have a minion and it's last jid, we use it to fetch the
        # function field (fun) that was registered by returner().
        jid, comps = minion.value, minion.key.split('/')
        funp = '/'.join([path, Schema['job-cache'], jid, comps[-1], 'fun'])

        # Try and read the field, and skip it if it doesn't exist or wasn't
        # registered for some reason.
        log.trace('sdstack_etcd returner <get_fun> reading function from minion {minion:s} for job {jid:s} at {path:s}'.format(minion=comps[-1], jid=jid, path=funp))
        try:
            res = client.read(funp)
        except etcd.EtcdKeyNotFound as E:
            log.debug("sdstack_etcd returner <get_fun> returned nothing from minion {minion:s} for job {jid:s} at path {path:s}".format(minion=comps[-1], jid=jid, path=funp))
            continue

        # Check if the function field (fun) matches what the user is looking for
        # If it does, then we can just add the minion to our results
        log.trace('sdstack_etcd returner <get_fun> decoding json data from minion {minion:s} for job {jid:s} at {path:s}'.format(minion=comps[-1], jid=jid, path=funp))
        data = salt.utils.json.loads(res.value)
        if data == fun:
            ret[comps[-1]] = str(data)
            log.debug("sdstack_etcd returner <get_fun> found job {jid:s} for minion {minion:s} using {fun:s} at {path:s}".format(minion=comps[-1], fun=data, jid=jid, path=minion.key))
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
        jobs = client.read(jobsp)
    except etcd.EtcdKeyNotFound as E:
        return []

    # Anything that's a directory is a job id. Since that's all we're returning,
    # aggregate them into a list.
    log.debug("sdstack_etcd returner <get_jids> iterating through jobs at {path:s}".format(path=jobs.key))
    ret = {}
    for job in jobs.leaves:
        if not job.dir:
            log.warning('sdstack_etcd returner <get_jids> found a non-job at {path:s} {expire:s}'.format(path=job.key, expire='that will need to be manually removed' if job.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=job.ttl)))
            continue

        jid = job.key.split('/')[-1]
        loadp = '/'.join([job.key, '.load.p'])

        # Now we can load the data from the job
        try:
            res = client.read(loadp)
        except etcd.EtcdKeyNotFound as E:
            log.error("sdstack_etcd returner <get_jids> could not find job data {jid:s} at the path {path:s}".format(jid=jid, path=loadp))
            continue

        # Decode the load data so we can stash the job data for our caller
        try:
            data = salt.utils.json.loads(res.value)

        # If we can't decode the json, then we're screwed so log it in case the user cares
        except Exception as E:
            log.error("sdstack_etcd returner <get_jids> could not decode data for job {jid:s} at the path {path:s} due to exception ({exception}) being raised. Data was {data:s}".format(jid=jid, path=loadp, exception=E, data=res.value))
            continue

        # Cool. Everything seems to be good...
        ret[jid] = salt.utils.jid.format_jid_instance(jid, data)
        log.trace("sdstack_etcd returner <get_jids> found job {jid:s} at {path:s}".format(jid=jid, path=job.key))

    log.debug("sdstack_etcd returner <get_jids> found {count:d} jobs at {path:s}".format(count=len(ret), path=jobs.key))
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
        minions = client.read(minionsp)
    except etcd.EtcdKeyNotFound as E:
        return []

    # We can just walk through everything that isn't a directory. This path
    # is simply a list of minions and the last job that each one returned.
    log.debug('sdstack_etcd returner <get_minions> iterating through minions at {path:s}'.format(path=minions.key))
    ret = []
    for minion in minions.leaves:
        if minion.dir:
            log.warning('sdstack_etcd returner <get_minions> found a non-minion at {path:s} {expire:s}'.format(path=minion.key, expire='that will need to be manually removed' if minion.ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=minion.ttl)))
            continue
        comps = str(minion.key).split('/')
        log.trace("sdstack_etcd returner <get_minions> found minion {minion:s} at {path:s}".format(minion=comps[-1], path=minion.key))
        ret.append(comps[-1])
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

        # Each event that we receive should already come with these properties,
        # but we add these just in case the schema changes as a result of a
        # refactor or something. Some of the other returns also include a
        # timestamp despite the time only having meaning to the minion that
        # it's coming from. We'll include it in case the user wants it too
        # for some reason.

        package = dict(event)
        package.setdefault('master_id', __opts__['id'])
        package.setdefault('timestamp', time.time())

        # Use the tag from the event package to build a watchable path
        packagep = '/'.join([path, Schema['package-path'], package['tag']])

        # Now we can write the event package into the event path
        log.debug("sdstack_etcd returner <event_return> writing package into event path at {path:s}".format(path=packagep))
        json = salt.utils.json.dumps(package)
        try:
            # Try and write the event if it doesn't exist
            res = client.write(packagep, json, prevExist=False)

        # If the event doesn't actually exist, then just modify it instead of re-creating it
        # and tampering with the createdIndex
        except etcd.EtcdAlreadyExist as E:
            log.trace("sdstack_etcd returner <event_return> fetching already existing event with the tag {name:s} at {path:s}".format(name=package['tag'], path=packagep))
            node = client.read(packagep)

            log.debug("sdstack_etcd returner <event_return> updating package for event ({event:d}) with the tag {name:s} at {path:s}".format(event=node.modifiedIndex, name=package['tag'], path=packagep))
            node.value = json
            res = client.update(node)

        except Exception as E:
            log.trace("sdstack_etcd returner <event_return> unable to write event with the tag {name:s} into {path:s} due to exception ({exception}) being raised".format(name=package['tag'], path=packagep, exception=E))
            exceptions.append((E, package))
            continue

        # From now on, we can use the modifiedIndex of our tag path as our event
        # identifier. Despite usage of the modifiedIndex as a unique identifier,
        # this identifer can be arbitrary as the index sub-key is responsible
        # for determining ownership of the event package that was registered.
        event = res.modifiedIndex
        log.trace("sdstack_etcd returner <event_return> wrote event {event:d} with the tag {name:s} to {path:s} using {data}".format(path=res.key, event=event, name=package['tag'], data=res.value))

        # Now we'll need to store the modifiedIndex for said event so that we can
        # use it to determine ownership. This modifiedIndex is what links the
        # actual event with the tag. If we were using the etcd3 api, then we
        # could make these 3 writes (index, tag, and lock) atomic. But we're
        # not, and so this is a manual effort and potentially racy depending on
        # the uniqueness of the modifiedIndex (which etcd guarantees unique)

        basep = '/'.join([path, Schema['event-cache'], str(event)])

        # Here we'll write our modifiedIndex to our event cache.
        indexp = '/'.join([basep, 'index'])
        try:
            # If the event is a new key, then we can simply cache it without concern
            if res.newKey:
                log.trace("sdstack_etcd returner <event_return> writing new event {event:d} with the modifiedIndex {index:d} for the tag {name:s} at {path:s}".format(path=indexp, event=event, index=res.modifiedIndex, name=package['tag']))
                client.write(indexp, res.modifiedIndex, prevExist=False)

            # Otherwise, the event was updated and thus we need to update our cache too
            else:
                log.trace("sdstack_etcd returner <event_return> updating event {event:d} with the tag {name:s} at {path:s} with the modifiedIndex {index:d}".format(path=indexp, event=event, index=res.modifiedIndex, name=package['tag']))
                client.write(indexp, res.modifiedIndex)

        except etcd.EtcdAlreadyExist as E:
            log.error("sdstack_etcd returner <event_return> unable to write modifiedIndex {index:d} for tag {name:s} to event {event:d} due to the event already existing".format(event=event, index=res.modifiedIndex, name=package['tag']))
            exceptions.append((E, package))
            continue

        # If we got here, then we should be able to write the tag using the event index
        tagp = '/'.join([basep, 'tag'])
        try:
            log.trace("sdstack_etcd returner <event_return> updating event {event:d} at {path:s} with tag {name:s}".format(path=tagp, event=event, name=package['tag']))
            client.write(tagp, package['tag'])

        except Exception as E:
            log.trace("sdstack_etcd returner <event_return> unable to update event {event:d} at {path:s} with tag {name:s} due to exception ({exception}) being raised".format(path=tagp, name=package['tag'], event=event, exception=E))
            exceptions.append((E, package))
            continue

        # Now that both have been written, let's write our lock to actually enable the event
        lockp = '/'.join([basep, 'lock'])
        try:
            log.trace("sdstack_etcd returner <event_return> writing lock for event {event:d} with the tag {name:s} to {path:s} {expire:s}".format(path=lockp, event=event, name=package['tag'], expire='that will need to be manually removed' if ttl is None else 'that will expire in {ttl:d} seconds'.format(ttl=ttl)))
            client.write(lockp, res.createdIndex, ttl=ttl if ttl > 0 else None)

        # If we can't write the lock, it's fine because the maintenance thread
        # will purge this event from the cache anyways if it's not written.
        except Exception as E:
            log.error("sdstack_etcd returner <event_return> unable to write lock for event {event:d} with the tag {name:s} to {path:s} due to exception ({exception}) being raised".format(path=lockp, name=package['tag'], event=event, exception=E))
            exceptions.append((E, package))

        continue

    # Go back through all of the exceptions that occurred and log them.
    for E, pack in exceptions:
        log.exception("sdstack_etcd returner <event_return> exception ({exception}) was raised while trying to write event {name:s} with the data {data}".format(exception=E, name=pack['tag'], data=pack))
    return


def get_jids_filter(count, filter_find_job=True):
    '''
    Return a list of all job ids
    :param int count: show not more than the count of most recent jobs
    :param bool filter_find_jobs: filter out 'saltutil.find_job' jobs
    '''
    read_profile = __opts__.get('etcd.returner_read_profile')
    client, path, ttl = _get_conn(__opts__, read_profile)

    # Enumerate all the jobs that are available.
    jobsp = '/'.join([path, Schema['job-cache']])

    # Fetch all the jobs. If the key doesn't exist, then it's likely that no
    # jobs have been created yet so return an empty list to the caller.
    log.debug("sdstack_etcd returner <get_jids_filter> listing jobs at {path:s}".format(path=jobsp))
    try:
        jobs = client.read(jobsp, sorted=True)
    except etcd.EtcdKeyNotFound as E:
        return []

    # Anything that's a directory is a job id. Since that's all we're returning,
    # aggregate them into a list. We do this ahead of time in order to conserve
    # memory by avoiding just decoding everything here
    log.debug("sdstack_etcd returner <get_jids_filter> collecting jobs at {path:s}".format(path=jobs.key))
    jids = []
    for job in jobs.leaves:
        if not job.dir:
            continue
        jids.append(job.key.split('/')[-1])

    log.debug("sdstack_etcd returner <get_jids_filter> collecting {count:d} job loads at {path:s}".format(path=jobs.key, count=count))
    ret = []
    for jid in jids[-count:]:

        # Figure out the path to .load.p from the current jid
        loadp = '/'.join([jobsp, jid, '.load.p'])

        # Now we can load the data from the job
        try:
            res = client.read(loadp)
        except etcd.EtcdKeyNotFound as E:
            log.error("sdstack_etcd returner <get_jids_filter> could not find job data {jid:s} at the path {path:s}".format(jid=jid, path=loadp))
            continue

        # Decode the load data so we can stash it for the caller
        try:
            data = salt.utils.json.loads(res.value)

        # If we can't decode the json, then we're screwed so log it in case the user cares
        except Exception as E:
            log.error("sdstack_etcd returner <get_jids_filter> could not decode data for job {jid:s} at the path {path:s} due to exception ({exception}) being raised. Data was {data:s}".format(jid=jid, path=loadp, exception=E, data=res.value))
            continue

        if filter_find_job and data['fun'] == 'saltutil.find_job':
            continue

        ret.append(salt.utils.jid.format_jid_instance_ext(jid, data))
    return ret
