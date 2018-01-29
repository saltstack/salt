# -*- coding: utf-8 -*-
'''
Manage Kinesis Streams
======================

.. versionadded:: 2017.7.0

Create and destroy Kinesis streams. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit Kinesis credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    keyid: GKTADJGHEIQSXMKKRBJ08H
    key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    region: us-east-1

It's also possible to specify ``key``, ``keyid`` and ``region`` via a
profile, either passed in as a dict, or as a string to pull from
pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure Kinesis stream does not exist:
      boto_kinesis.absent:
        - name: new_stream
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        - region: us-east-1

    Ensure Kinesis stream exists:
      boto_kinesis.present:
        - name: new_stream
        - retention_hours: 168
        - enhanced_monitoring: ['ALL']
        - num_shards: 2
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        - region: us-east-1
'''
# Keep pylint from chocking on ret
# pylint: disable=undefined-variable
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)

__virtualname__ = 'boto_kinesis'


def __virtual__():
    '''
    Only load if boto_kinesis is available.
    '''
    if 'boto_kinesis.exists' in __salt__:
        return __virtualname__
    return False, 'The boto_kinesis module could not be loaded: boto libraries not found.'


def present(name,
            retention_hours=None,
            enhanced_monitoring=None,
            num_shards=None,
            do_reshard=True,
            region=None,
            key=None,
            keyid=None,
            profile=None):
    '''
    Ensure the kinesis stream is properly configured and scaled.

    name (string)
        Stream name

    retention_hours (int)
        Retain data for this many hours.
        AWS allows minimum 24 hours, maximum 168 hours.

    enhanced_monitoring (list of string)
        Turn on enhanced monitoring for the specified shard-level metrics.
        Pass in ['ALL'] or True for all metrics, [] or False for no metrics.
        Turn on individual metrics by passing in a list: ['IncomingBytes', 'OutgoingBytes']
        Note that if only some metrics are supplied, the remaining metrics will be turned off.

    num_shards (int)
        Reshard stream (if necessary) to this number of shards
        !!!!! Resharding is expensive! Each split or merge can take up to 30 seconds,
        and the reshard method balances the partition space evenly.
        Resharding from N to N+1 can require 2N operations.
        Resharding is much faster with powers of 2 (e.g. 2^N to 2^N+1) !!!!!

    do_reshard (boolean)
        If set to False, this script will NEVER reshard the stream,
        regardless of other input. Useful for testing.

    region (string)
        Region to connect to.

    key (string)
        Secret key to be used.

    keyid (string)
        Access key to be used.

    profile (dict)
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    comments = []
    changes_old = {}
    changes_new = {}

    # Ensure stream exists
    exists = __salt__['boto_kinesis.exists'](
        name,
        region,
        key,
        keyid,
        profile
    )
    if exists['result'] is False:
        if __opts__['test']:
            ret['result'] = None
            comments.append('Kinesis stream {0} would be created'.format(name))
            _add_changes(ret, changes_old, changes_new, comments)
            return ret
        else:
            is_created = __salt__['boto_kinesis.create_stream'](
                name,
                num_shards,
                region,
                key,
                keyid,
                profile
            )
            if 'error' in is_created:
                ret['result'] = False
                comments.append('Failed to create stream {0}: {1}'.format(name, is_created['error']))
                _add_changes(ret, changes_old, changes_new, comments)
                return ret

            comments.append('Kinesis stream {0} successfully created'.format(name))
            changes_new['name'] = name
            changes_new['num_shards'] = num_shards
    else:
        comments.append('Kinesis stream {0} already exists'.format(name))

    stream_response = __salt__['boto_kinesis.get_stream_when_active'](
        name,
        region,
        key,
        keyid,
        profile
    )
    if 'error' in stream_response:
        ret['result'] = False
        comments.append('Kinesis stream {0}: error getting description: {1}'
                        .format(name, stream_response['error']))
        _add_changes(ret, changes_old, changes_new, comments)
        return ret

    stream_details = stream_response['result']["StreamDescription"]

    # Configure retention hours
    if retention_hours is not None:
        old_retention_hours = stream_details["RetentionPeriodHours"]
        retention_matches = (old_retention_hours == retention_hours)
        if not retention_matches:
            if __opts__['test']:
                ret['result'] = None
                comments.append('Kinesis stream {0}: retention hours would be updated to {1}'
                                .format(name, retention_hours))
            else:
                if old_retention_hours > retention_hours:
                    retention_updated = __salt__['boto_kinesis.decrease_stream_retention_period'](
                        name,
                        retention_hours,
                        region,
                        key,
                        keyid,
                        profile
                    )
                else:
                    retention_updated = __salt__['boto_kinesis.increase_stream_retention_period'](
                        name,
                        retention_hours,
                        region,
                        key,
                        keyid,
                        profile
                    )

                if 'error' in retention_updated:
                    ret['result'] = False
                    comments.append('Kinesis stream {0}: failed to update retention hours: {1}'
                                    .format(name, retention_updated['error']))
                    _add_changes(ret, changes_old, changes_new, comments)
                    return ret

                comments.append('Kinesis stream {0}: retention hours was successfully updated'.format(name))
                changes_old['retention_hours'] = old_retention_hours
                changes_new['retention_hours'] = retention_hours

                # wait until active again, otherwise it will log a lot of ResourceInUseExceptions
                # note that this isn't required below; reshard() will itself handle waiting
                stream_response = __salt__['boto_kinesis.get_stream_when_active'](
                    name,
                    region,
                    key,
                    keyid,
                    profile
                )
                if 'error' in stream_response:
                    ret['result'] = False
                    comments.append('Kinesis stream {0}: error getting description: {1}'
                                    .format(name, stream_response['error']))
                    _add_changes(ret, changes_old, changes_new, comments)
                    return ret

                stream_details = stream_response['result']["StreamDescription"]
        else:
            comments.append('Kinesis stream {0}: retention hours did not require change, already set at {1}'
                            .format(name, old_retention_hours))
    else:
        comments.append('Kinesis stream {0}: did not configure retention hours'.format(name))

    # Configure enhanced monitoring
    if enhanced_monitoring is not None:
        if enhanced_monitoring is True or enhanced_monitoring == ['ALL']:
            # for ease of comparison; describe_stream will always return the full list of metrics, never 'ALL'
            enhanced_monitoring = [
                    "IncomingBytes",
                    "OutgoingRecords",
                    "IteratorAgeMilliseconds",
                    "IncomingRecords",
                    "ReadProvisionedThroughputExceeded",
                    "WriteProvisionedThroughputExceeded",
                    "OutgoingBytes"
                ]
        elif enhanced_monitoring is False or enhanced_monitoring == "None":
            enhanced_monitoring = []

        old_enhanced_monitoring = stream_details.get("EnhancedMonitoring")[0]["ShardLevelMetrics"]

        new_monitoring_set = set(enhanced_monitoring)
        old_monitoring_set = set(old_enhanced_monitoring)

        matching_metrics = new_monitoring_set.intersection(old_monitoring_set)
        enable_metrics = list(new_monitoring_set.difference(matching_metrics))
        disable_metrics = list(old_monitoring_set.difference(matching_metrics))

        if len(enable_metrics) != 0:
            if __opts__['test']:
                ret['result'] = None
                comments.append('Kinesis stream {0}: would enable enhanced monitoring for {1}'
                                .format(name, enable_metrics))
            else:

                metrics_enabled = __salt__['boto_kinesis.enable_enhanced_monitoring'](
                    name,
                    enable_metrics,
                    region,
                    key,
                    keyid,
                    profile
                )
                if 'error' in metrics_enabled:
                    ret['result'] = False
                    comments.append('Kinesis stream {0}: failed to enable enhanced monitoring: {1}'
                                    .format(name, metrics_enabled['error']))
                    _add_changes(ret, changes_old, changes_new, comments)
                    return ret

                comments.append('Kinesis stream {0}: enhanced monitoring was enabled for shard-level metrics {1}'
                                .format(name, enable_metrics))

        if len(disable_metrics) != 0:
            if __opts__['test']:
                ret['result'] = None
                comments.append('Kinesis stream {0}: would disable enhanced monitoring for {1}'
                                .format(name, disable_metrics))
            else:

                metrics_disabled = __salt__['boto_kinesis.disable_enhanced_monitoring'](
                    name,
                    disable_metrics,
                    region,
                    key,
                    keyid,
                    profile
                )
                if 'error' in metrics_disabled:
                    ret['result'] = False
                    comments.append('Kinesis stream {0}: failed to disable enhanced monitoring: {1}'
                                    .format(name, metrics_disabled['error']))
                    _add_changes(ret, changes_old, changes_new, comments)
                    return ret

                comments.append('Kinesis stream {0}: enhanced monitoring was disabled for shard-level metrics {1}'
                                .format(name, disable_metrics))

        if len(disable_metrics) == 0 and len(enable_metrics) == 0:
            comments.append('Kinesis stream {0}: enhanced monitoring did not require change, already set at {1}'
                            .format(name, (old_enhanced_monitoring if len(old_enhanced_monitoring) > 0 else "None")))
        elif not __opts__['test']:
            changes_old['enhanced_monitoring'] = (old_enhanced_monitoring if len(old_enhanced_monitoring) > 0
                                                  else "None")
            changes_new['enhanced_monitoring'] = (enhanced_monitoring if len(enhanced_monitoring) > 0
                                                  else "None")
    else:
        comments.append('Kinesis stream {0}: did not configure enhanced monitoring'.format(name))

    # Reshard stream if necessary
    min_hash_key, max_hash_key, full_stream_details = __salt__['boto_kinesis.get_info_for_reshard'](
        stream_details
    )
    old_num_shards = len(full_stream_details["OpenShards"])

    if num_shards is not None and do_reshard:
        num_shards_matches = (old_num_shards == num_shards)
        if not num_shards_matches:
            if __opts__['test']:
                ret['result'] = None
                comments.append('Kinesis stream {0}: would be resharded from {1} to {2} shards'
                                .format(name, old_num_shards, num_shards))
            else:
                log.info(
                    'Resharding stream from %s to %s shards, this could take '
                    'a while', old_num_shards, num_shards
                )
                # reshard returns True when a split/merge action is taken,
                # or False when no more actions are required
                continue_reshard = True
                while continue_reshard:
                    reshard_response = __salt__['boto_kinesis.reshard'](
                        name,
                        num_shards,
                        do_reshard,
                        region,
                        key,
                        keyid,
                        profile)

                    if 'error' in reshard_response:
                        ret['result'] = False
                        comments.append('Encountered error while resharding {0}: {1}'
                                        .format(name, reshard_response['error']))
                        _add_changes(ret, changes_old, changes_new, comments)
                        return ret

                    continue_reshard = reshard_response['result']

                comments.append('Kinesis stream {0}: successfully resharded to {1} shards'.format(name, num_shards))
                changes_old['num_shards'] = old_num_shards
                changes_new['num_shards'] = num_shards
        else:
            comments.append('Kinesis stream {0}: did not require resharding, remains at {1} shards'
                            .format(name, old_num_shards))
    else:
        comments.append('Kinesis stream {0}: did not reshard, remains at {1} shards'.format(name, old_num_shards))

    _add_changes(ret, changes_old, changes_new, comments)
    return ret


def absent(name,
           region=None,
           key=None,
           keyid=None,
           profile=None):
    '''
    Delete the kinesis stream, if it exists.

    name (string)
        Stream name

    region (string)
        Region to connect to.

    key (string)
        Secret key to be used.

    keyid (string)
        Access key to be used.

    profile (dict)
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    exists = __salt__['boto_kinesis.exists'](
        name,
        region,
        key,
        keyid,
        profile
    )
    if exists['result'] is False:
        ret['comment'] = 'Kinesis stream {0} does not exist'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Kinesis stream {0} would be deleted'.format(name)
        ret['result'] = None
        return ret

    is_deleted = __salt__['boto_kinesis.delete_stream'](
        name,
        region,
        key,
        keyid,
        profile
    )
    if 'error' in is_deleted:
        ret['comment'] = 'Failed to delete stream {0}: {1}'.format(name, is_deleted['error'])
        ret['result'] = False
    else:
        ret['comment'] = 'Deleted stream {0}'.format(name)
        ret['changes'].setdefault('old', 'Stream {0} exists'.format(name))
        ret['changes'].setdefault('new', 'Stream {0} deleted'.format(name))

    return ret


def _add_changes(ret, changes_old, changes_new, comments):
    ret['comment'] = ',\n'.join(comments)
    if changes_old:
        ret['changes']['old'] = changes_old
    if changes_new:
        ret['changes']['new'] = changes_new
