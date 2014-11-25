# -*- coding: utf-8 -*-
'''
Management of Glance images
===========================

:depends:   - glanceclient Python module
:configuration: See :py:mod:`salt.modules.glance` for setup instructions.

.. code-block:: yaml

    glance image present:
      glance.image_present:
        - name: Ubuntu
        - copy_from: 'https://cloud-images.ubuntu.com/trusty/current/
                        trusty-server-cloudimg-amd64-disk1.img'
        - container_format: bare
        - disk_format: qcow2
        - connection_user: admin
        - connection_password: admin_pass
        - connection_tenant: admin
        - connection_auth_url: 'http://127.0.0.1:5000/v2.0'

    glance image absent:
      glance.image_absent:
        - name: Ubuntu
        - disk_format: qcow2
        - connection_user: admin
        - connection_password: admin_pass
        - connection_tenant: admin
        - connection_auth_url: 'http://127.0.0.1:5000/v2.0'
'''
import logging
LOG = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if glance module is present in __salt__
    '''
    return 'glance' if 'glance.image_list' in __salt__ else False


def image_present(name,
                  disk_format='qcow2',
                  container_format='bare',
                  min_disk=None,
                  min_ram=None,
                  is_public=True,
                  protected=False,
                  checksum=None,
                  copy_from=None,
                  store=None,
                  profile=None,
                  **connection_args):
    '''
    Ensure that the glance image is present with the specified properties.

    name
        The name of the image to manage
    '''
    ret = {'name': name,
           'changes': {'name': name},
           'result': True,
           'comment': 'Image "{0}" will be updated'.format(name)}
    if __opts__.get('test', None):
        return ret
    existing_image = __salt__['glance.image_show'](
        name=name, profile=profile, **connection_args)
    non_null_arguments = _get_non_null_args(name=name,
                                            disk_format=disk_format,
                                            container_format=container_format,
                                            min_disk=min_disk,
                                            min_ram=min_ram,
                                            is_public=is_public,
                                            protected=protected,
                                            checksum=checksum,
                                            copy_from=copy_from,
                                            store=store)
    LOG.debug('running state glance.image_present with arguments {0}'.format(
        str(non_null_arguments)))
    if 'Error' in existing_image:
        non_null_arguments.update({'profile': profile})
        non_null_arguments.update(connection_args)
        ret['changes'] = __salt__['glance.image_create'](**non_null_arguments)
        if 'Error' in ret['changes']:
            ret['result'] = False
            ret['comment'] = 'Image "{0}" failed to create'.format(name)
        else:
            ret['comment'] = 'Image "{0}" created'.format(name)
        return ret
    # iterate over all given arguments
    # if anything is different delete and recreate
    for key in non_null_arguments:
        if key == 'copy_from':
            continue
        if existing_image[name].get(key, None) != non_null_arguments[key]:
            LOG.debug('{0} has changed to {1}'.format(
                key, non_null_arguments[key]))
            __salt__['glance.image_delete'](
                name=name, profile=profile, **connection_args)
            non_null_arguments.update({'profile': profile})
            non_null_arguments.update(connection_args)
            return image_present(**non_null_arguments)
    ret['changes'] = {}
    ret['comment'] = 'Image "{0}" present in correct state'.format(name)
    return ret


def image_absent(name, profile=None, **connection_args):
    '''
    Ensure that the glance image is absent.

    name
        The name of the image to manage
    '''
    ret = {'name': name,
           'changes': {'name': name},
           'result': True,
           'comment': 'Image "{0}" will be removed'.format(name)}
    if __opts__.get('test', None):
        return ret
    existing_image = __salt__['glance.image_show'](
        name=name, profile=profile, **connection_args)
    if 'Error' not in existing_image:
        __salt__['glance.image_delete'](
            name=name, profile=profile, **connection_args)
        existing_image = __salt__['glance.image_show'](
            name=name, profile=profile, **connection_args)
        if 'Error' not in existing_image:
            ret['result'] = False
            ret['comment'] = 'Image "{0}" can not be remove'.format(name)
            return ret
        ret['changes'] = {name: 'deleted'}
        ret['comment'] = 'Image "{0}" removed'.format(name)
        return ret
    ret['changes'] = {}
    ret['comment'] = 'Image "{0}" absent'.format(name)
    return ret


def _get_non_null_args(**kwargs):
    '''
    Return those kwargs which are not null
    '''
    return {key: kwargs[key] for key in kwargs if kwargs[key]} # pylint: disable=E0001
