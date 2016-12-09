# -*- coding: utf-8 -*-
'''
Management of PostgreSQL clusters
=================================

The postgres_cluster state module is used to manage PostgreSQL clusters.
Clusters can be set as either absent or present

.. code-block:: yaml

    create cluster 9.3 main:
      postgres_cluster.present:
          - name: 'main'
          - version: '9.3'
'''
from __future__ import absolute_import


def __virtual__():
    '''
    Only load if the deb_postgres module is present
    '''
    if 'postgres.cluster_exists' not in __salt__:
        return (False, 'Unable to load postgres module.  Make sure `postgres.bins_dir` is set.')
    return True


def present(version,
            name,
            port=None,
            encoding=None,
            locale=None,
            datadir=None):
    '''
    Ensure that the named cluster is present with the specified properties.
    For more information about all of these options see man pg_createcluster(1)

    version
        Version of the postgresql cluster

    name
        The name of the cluster

    port
        Cluster port

    encoding
        The character encoding scheme to be used in this database

    locale
        Locale with which to create cluster

    datadir
        Where the cluster is stored

        .. versionadded:: 2015.XX
    '''
    msg = 'Cluster {0}/{1} is already present'.format(version, name)
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': msg}

    if __salt__['postgres.cluster_exists'](version, name):
        # check cluster config is correct
        infos = __salt__['postgres.cluster_list'](verbose=True)
        info = infos['{0}/{1}'.format(version, name)]
        # TODO: check locale en encoding configs also
        if any((port != info['port'] if port else False,
                datadir != info['datadir'] if datadir else False,)):
            ret['comment'] = 'Cluster {0}/{1} has wrong parameters ' \
                             'which couldn\'t be changed on fly.' \
                                 .format(version, name)
            ret['result'] = False
        return ret

    # The cluster is not present, add it!
    if __opts__.get('test'):
        ret['result'] = None
        msg = 'Cluster {0}/{1} is set to be created'
        ret['comment'] = msg.format(version, name)
        return ret
    cluster = __salt__['postgres.cluster_create'](
        version=version,
        name=name,
        port=port,
        locale=locale,
        encoding=encoding,
        datadir=datadir)
    if cluster:
        msg = 'The cluster {0}/{1} has been created'
        ret['comment'] = msg.format(version, name)
        ret['changes']['{0}/{1}'.format(version, name)] = 'Present'
    else:
        msg = 'Failed to create cluster {0}/{1}'
        ret['comment'] = msg.format(version, name)
        ret['result'] = False
    return ret


def absent(version,
           name):
    '''
    Ensure that the named cluster is absent

    version
        Version of the postgresql server of the cluster to remove

    name
        The name of the cluster to remove

        .. versionadded:: 2015.XX
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if cluster exists and remove it
    if __salt__['postgres.cluster_exists'](version, name):
        if __opts__.get('test'):
            ret['result'] = None
            msg = 'Cluster {0}/{1} is set to be removed'
            ret['comment'] = msg.format(version, name)
            return ret
        if __salt__['postgres.cluster_remove'](version, name, True):
            msg = 'Cluster {0}/{1} has been removed'
            ret['comment'] = msg.format(version, name)
            ret['changes'][name] = 'Absent'
            return ret

    # fallback
    ret['comment'] = 'Cluster {0}/{1} is not present, so it cannot ' \
                     'be removed'.format(version, name)
    return ret
