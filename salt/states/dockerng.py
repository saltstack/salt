# -*- coding: utf-8 -*-
'''
Management of Docker containers

.. versionadded:: 2015.8.0


This is the state module to accompany the :mod:`dockerng
<salt.modules.dockerng>` execution module.


Why Make a Second Docker State Module?
--------------------------------------

We have received a lot of feedback on our Docker support. In the process of
implementing recommended improvements, it became obvious that major changes
needed to be made to the functions and return data. In the end, a complete
rewrite was done.

The changes being too significant, it was decided that making a separate
execution module and state module (called ``dockerng``) would be the best
option. This will give users a couple release cycles to modify their scripts,
SLS files, etc. to use the new functionality, rather than forcing users to
change everything immediately.

In the **Nitrogen** release of Salt (due in 2017), this execution module will
take the place of the default Docker execution module, and backwards-compatible
naming will be maintained for a couple releases after that to allow users time
to replace references to ``dockerng`` with ``docker``.


.. note::

    To pull from a Docker registry, authentication must be configured. See
    :ref:`here <docker-authentication>` for more information on how to
    configure access to docker registries in :ref:`Pillar <pillar>` data.
'''

from __future__ import absolute_import
import copy
import logging
import sys
import traceback

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError
# pylint: disable=no-name-in-module,import-error
from salt.modules.dockerng import (
    CLIENT_TIMEOUT,
    STOP_TIMEOUT,
    VALID_CREATE_OPTS,
    _validate_input,
    _get_repo_tag,
)
# pylint: enable=no-name-in-module,import-error
import salt.utils
import salt.ext.six as six

# Enable proper logging
log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Define the module's virtual name
__virtualname__ = 'dockerng'


def __virtual__():
    '''
    Only load if the dockerng execution module is available
    '''
    if 'dockerng.version' in __salt__:
        global _validate_input  # pylint: disable=global-statement
        _validate_input = salt.utils.namespaced_function(
            _validate_input, globals()
        )
        return __virtualname__
    return (False, __salt__.missing_fun_string('dockerng.version'))


def _format_comments(comments):
    '''
    DRY code for joining comments together and conditionally adding a period at
    the end.
    '''
    ret = '. '.join(comments)
    if len(comments) > 1:
        ret += '.'
    return ret


def _map_port_from_yaml_to_docker(port):
    '''
    docker-py interface is not very nice:
    While for ``port_bindings`` they support:

    .. code-block:: python

        '8888/tcp'

    For ``ports``, it has to be transformed into:

    .. code-block:: python

        (8888, 'tcp')

    '''
    if isinstance(port, six.string_types):
        port, sep, protocol = port.partition('/')
        if protocol:
            return int(port), protocol
        return int(port)
    return port


def _prep_input(kwargs):
    '''
    Repack (if necessary) data that should be in a dict but is easier to
    configure in an SLS file as a dictlist. If the data type is a string, then
    skip repacking and let _validate_input() try to sort it out.
    '''
    for kwarg in ('environment', 'lxc_conf'):
        kwarg_value = kwargs.get(kwarg)
        if kwarg_value is not None \
                and not isinstance(kwarg_value, six.string_types):
            err = ('Invalid {0} configuration. See the documentation for '
                   'proper usage.'.format(kwarg))
            if salt.utils.is_dictlist(kwarg_value):
                new_kwarg_value = salt.utils.repack_dictlist(kwarg_value)
                if not kwarg_value:
                    raise SaltInvocationError(err)
                kwargs[kwarg] = new_kwarg_value
            if not isinstance(kwargs[kwarg], dict):
                raise SaltInvocationError(err)


def _compare(actual, create_kwargs, defaults_from_image):
    '''
    Compare the desired configuration against the actual configuration returned
    by dockerng.inspect_container
    '''
    def _get(path, default=None):
        return salt.utils.traverse_dict(actual, path, default, delimiter=':')

    def _image_get(path, default=None):
        return salt.utils.traverse_dict(defaults_from_image, path, default,
                                        delimiter=':')
    ret = {}
    for item, config in six.iteritems(VALID_CREATE_OPTS):
        try:
            data = create_kwargs[item]
        except KeyError:
            try:
                data = _image_get(config['image_path'])
            except KeyError:
                if config.get('get_default_from_container'):
                    data = _get(config['path'])
                else:
                    data = config.get('default')

        log.trace('dockerng.running: comparing ' + item)
        conf_path = config['path']
        if isinstance(conf_path, tuple):
            actual_data = [_get(x) for x in conf_path]
        else:
            actual_data = _get(conf_path, default=config.get('default'))
        log.trace('dockerng.running ({0}): desired value: {1}'
                  .format(item, data))
        log.trace('dockerng.running ({0}): actual value: {1}'
                  .format(item, actual_data))

        # 'create' comparison params
        if item == 'detach':
            # Something unique here. Two fields to check, if both are False
            # then detach is True
            actual_detach = all(x is False for x in actual_data)
            log.trace('dockerng.running ({0}): munged actual value: {1}'
                      .format(item, actual_detach))
            if actual_detach != data:
                ret.update({item: {'old': actual_detach, 'new': data}})
            continue

        elif item == 'environment':
            if actual_data is None:
                actual_data = []
            actual_env = {}
            for env_var in actual_data:
                try:
                    key, val = env_var.split('=', 1)
                except (AttributeError, ValueError):
                    log.warning(
                        'Unexpected environment variable in inspect '
                        'output {0}'.format(env_var)
                    )
                    continue
                else:
                    actual_env[key] = val
            log.trace('dockerng.running ({0}): munged actual value: {1}'
                        .format(item, actual_env))
            env_diff = {}
            for key in data:
                actual_val = actual_env.get(key)
                if data[key] != actual_val:
                    env_ptr = env_diff.setdefault(item, {})
                    env_ptr.setdefault('old', {})[key] = actual_val
                    env_ptr.setdefault('new', {})[key] = data[key]
            if env_diff:
                ret.update(env_diff)
            continue

        elif item == 'ports':
            # Munge the desired configuration instead of the actual
            # configuration here, because the desired configuration is a
            # list of ints or tuples, and that won't look as good in the
            # nested outputter as a simple comparison of lists of
            # port/protocol pairs (as found in the "actual" dict).
            if actual_data is None:
                actual_data = []
            if data is None:
                data = []
            actual_ports = sorted(actual_data)
            desired_ports = []
            for port_def in data:
                if isinstance(port_def, six.integer_types):
                    port_def = str(port_def)
                if isinstance(port_def, (tuple, list)):
                    desired_ports.append('{0}/{1}'.format(*port_def))
                elif '/' not in port_def:
                    desired_ports.append('{0}/tcp'.format(port_def))
                else:
                    desired_ports.append(port_def)
            # Ports declared in docker file should be part of desired_ports.
            desired_ports.extend([
                k for k in _image_get(config['image_path']) or [] if
                k not in desired_ports])
            desired_ports.sort()
            log.trace('dockerng.running ({0}): munged actual value: {1}'
                      .format(item, actual_ports))
            log.trace('dockerng.running ({0}): munged desired value: {1}'
                      .format(item, desired_ports))
            if actual_ports != desired_ports:
                ret.update({item: {'old': actual_ports,
                                   'new': desired_ports}})
            continue

        elif item == 'volumes':
            if actual_data is None:
                actual_data = []
            if data is None:
                data = []
            actual_volumes = sorted(actual_data)
            # Volumes declared in docker file should be part of desired_volumes.
            desired_volumes = sorted(list(data) + [
                k for k in _image_get(config['image_path']) or [] if
                k not in data])

            if actual_volumes != desired_volumes:
                ret.update({item: {'old': actual_volumes,
                                   'new': desired_volumes}})

        elif item == 'binds':
            if actual_data is None:
                actual_data = {}
            if data is None:
                data = {}
            actual_binds = []
            for bind in actual_data:
                bind_parts = bind.split(':')
                if len(bind_parts) == 2:
                    actual_binds.append(bind + ':rw')
                else:
                    actual_binds.append(bind)
            desired_binds = []
            for host_path, bind_data in six.iteritems(data):
                desired_binds.append(
                    '{0}:{1}:{2}'.format(
                        host_path,
                        bind_data['bind'],
                        'ro' if bind_data['ro'] else 'rw'
                    )
                )
            actual_binds.sort()
            desired_binds.sort()
            if actual_binds != desired_binds:
                ret.update({item: {'old': actual_binds,
                                   'new': desired_binds}})
                continue

        elif item == 'port_bindings':
            if actual_data is None:
                actual_data = {}
            if data is None:
                data = {}
            actual_binds = []
            for container_port, bind_list in six.iteritems(actual_data):
                if container_port.endswith('/tcp'):
                    container_port = container_port[:-4]
                for bind_data in bind_list:
                    # Port range will have to be updated for future Docker
                    # versions (see
                    # https://github.com/docker/docker/issues/10220).  Note
                    # that Docker 1.5.0 (released a few weeks after the fix
                    # was merged) does not appear to have this fix in it,
                    # so we're probably looking at 1.6.0 for this fix.
                    if bind_data['HostPort'] == '' or \
                            49153 <= int(bind_data['HostPort']) <= 65535:
                        host_port = ''
                    else:
                        host_port = bind_data['HostPort']
                    if bind_data['HostIp'] in ('0.0.0.0', ''):
                        if host_port:
                            bind_def = (host_port, container_port)
                        else:
                            bind_def = (container_port,)
                    else:
                        bind_def = (bind_data['HostIp'],
                                    host_port,
                                    container_port)
                    actual_binds.append(':'.join(bind_def))

            desired_binds = []
            for container_port, bind_list in six.iteritems(data):
                try:
                    if container_port.endswith('/tcp'):
                        container_port = container_port[:-4]
                except AttributeError:
                    # The port's protocol was not specified, so it is
                    # assumed to be TCP. Thus, according to docker-py usage
                    # examples, the port was passed as an int. Convert it
                    # to a string here.
                    container_port = str(container_port)
                for bind_data in bind_list:
                    if isinstance(bind_data, tuple):
                        try:
                            host_ip, host_port = bind_data
                            host_port = str(host_port)
                        except ValueError:
                            host_ip = bind_data[0]
                            host_port = ''
                        bind_def = '{0}:{1}:{2}'.format(
                            host_ip, host_port, container_port
                        )
                    else:
                        if bind_data is not None:
                            bind_def = '{0}:{1}'.format(
                                bind_data, container_port
                            )
                        else:
                            bind_def = container_port
                    desired_binds.append(bind_def)
            actual_binds.sort()
            desired_binds.sort()
            log.trace('dockerng.running ({0}): munged actual value: {1}'
                        .format(item, actual_binds))
            log.trace('dockerng.running ({0}): munged desired value: {1}'
                        .format(item, desired_binds))
            if actual_binds != desired_binds:
                ret.update({item: {'old': actual_binds,
                                    'new': desired_binds}})
                continue

        elif item == 'links':
            if actual_data is None:
                actual_data = []
            if data is None:
                data = []
            actual_links = []
            for link in actual_data:
                try:
                    link_name, alias_info = link.split(':')
                except ValueError:
                    log.error(
                        'Failed to compare link {0}, unrecognized format'
                        .format(link)
                    )
                    continue
                container_name, _, link_alias = alias_info.rpartition('/')
                if not container_name:
                    log.error(
                        'Failed to interpret link alias from {0}, '
                        'unrecognized format'.format(alias_info)
                    )
                    continue
                actual_links.append((link_name, link_alias))
            actual_links.sort()
            desired_links = sorted(data)
            if actual_links != desired_links:
                ret.update({item: {'old': actual_links,
                                    'new': desired_links}})
                continue

        elif item == 'extra_hosts':
            if actual_data is None:
                actual_data = {}
            if data is None:
                data = {}
            actual_hosts = sorted(actual_data)
            desired_hosts = sorted(
                ['{0}:{1}'.format(x, y) for x, y in six.iteritems(data)]
            )
            if actual_hosts != desired_hosts:
                ret.update({item: {'old': actual_hosts,
                                   'new': desired_hosts}})
                continue

        elif item == 'dns':
            # Sometimes docker daemon returns `None` and
            # sometimes `[]`. We have to deal with it.
            if bool(actual_data) != bool(data):
                ret.update({item: {'old': actual_data, 'new': data}})

        elif item == 'dns_search':
            # Sometimes docker daemon returns `None` and
            # sometimes `[]`. We have to deal with it.
            if bool(actual_data) != bool(data):
                ret.update({item: {'old': actual_data, 'new': data}})

        elif item == 'labels':
            if actual_data is None:
                actual_data = {}
            if data is None:
                data = {}
            image_labels = _image_get(config['image_path'], default={})
            if image_labels is not None:
                image_labels = image_labels.copy()
                if isinstance(data, list):
                    data = dict((k, '') for k in data)
                image_labels.update(data)
                data = image_labels
            if actual_data != data:
                ret.update({item: {'old': actual_data, 'new': data}})
                continue

        elif item == 'security_opt':
            if actual_data is None:
                actual_data = []
            if data is None:
                data = []
            actual_data = sorted(set(actual_data))
            desired_data = sorted(set(data))
            log.trace('dockerng.running ({0}): munged actual value: {1}'
                      .format(item, actual_data))
            log.trace('dockerng.running ({0}): munged desired value: {1}'
                      .format(item, desired_data))
            if actual_data != desired_data:
                ret.update({item: {'old': actual_data,
                                   'new': desired_data}})
            continue

        elif item in ('cmd', 'command', 'entrypoint'):
            if (actual_data is None and item not in create_kwargs and
                    _image_get(config['image_path'])):
                # It appears we can't blank values defined on Image layer,
                # So ignore the diff.
                continue
            if actual_data != data:
                ret.update({item: {'old': actual_data, 'new': data}})
            continue

        elif isinstance(data, list):
            # Compare two sorted lists of items. Won't work for "command"
            # or "entrypoint" because those are both shell commands and the
            # original order matters. It will, however, work for "volumes"
            # because even though "volumes" is a sub-dict nested within the
            # "actual" dict sorted(somedict) still just gives you a sorted
            # list of the dictionary's keys. And we don't care about the
            # value for "volumes", just its keys.
            if actual_data is None:
                actual_data = []
            actual_data = sorted(actual_data)
            desired_data = sorted(data)
            log.trace('dockerng.running ({0}): munged actual value: {1}'
                        .format(item, actual_data))
            log.trace('dockerng.running ({0}): munged desired value: {1}'
                        .format(item, desired_data))
            if actual_data != desired_data:
                ret.update({item: {'old': actual_data,
                                    'new': desired_data}})
            continue

        else:
            # Generic comparison, works on strings, numeric types, and
            # booleans
            if actual_data != data:
                ret.update({item: {'old': actual_data, 'new': data}})
    return ret


def _find_volume(name):
    '''
    Find volume by name on minion
    '''
    docker_volumes = __salt__['dockerng.volumes']()['Volumes']
    if docker_volumes:
        volumes = [v for v in docker_volumes if v['Name'] == name]
        if volumes:
            return volumes[0]

    return None


def _get_defaults_from_image(image_id):
    return __salt__['dockerng.inspect_image'](image_id)


def image_present(name,
                  build=None,
                  load=None,
                  force=False,
                  insecure_registry=False,
                  client_timeout=CLIENT_TIMEOUT,
                  **kwargs):
    '''
    Ensure that an image is present. The image can either be pulled from a
    Docker registry, built from a Dockerfile, or loaded from a saved image.
    Image names can be specified either using ``repo:tag`` notation, or just
    the repo name (in which case a tag of ``latest`` is assumed).
    Repo identifier is mandatory, we don't assume the default repository
    is docker hub.

    If neither of the ``build`` or ``load`` arguments are used, then Salt will
    pull from the :ref:`configured registries <docker-authentication>`. If the
    specified image already exists, it will not be pulled unless ``force`` is
    set to ``True``. Here is an example of a state that will pull an image from
    the Docker Hub:

    .. code-block:: yaml

        myuser/myimage:mytag:
          dockerng.image_present

    build
        Path to directory on the Minion containing a Dockerfile

        .. code-block:: yaml

            myuser/myimage:mytag:
              dockerng.image_present:
                - build: /home/myuser/docker/myimage

        The image will be built using :py:func:`dockerng.build
        <salt.modules.dockerng.build>` and the specified image name and tag
        will be applied to it.

    load
        Loads a tar archive created with :py:func:`dockerng.load
        <salt.modules.dockerng.load>` (or the ``docker load`` Docker CLI
        command), and assigns it the specified repo and tag.

        .. code-block:: yaml

            myuser/myimage:mytag:
              dockerng.image_present:
                - load: salt://path/to/image.tar

    force : False
        Set this parameter to ``True`` to force Salt to pull/build/load the
        image even if it is already present.

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        the state, but for receiving a response from the API.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if build is not None and load is not None:
        ret['comment'] = 'Only one of \'build\' or \'load\' is permitted.'
        return ret

    # Ensure that we have repo:tag notation
    image = ':'.join(_get_repo_tag(name))
    all_tags = __salt__['dockerng.list_tags']()

    if image in all_tags:
        if not force:
            ret['result'] = True
            ret['comment'] = 'Image \'{0}\' already present'.format(name)
            return ret
        else:
            try:
                image_info = __salt__['dockerng.inspect_image'](name)
            except Exception as exc:
                ret['comment'] = \
                    'Unable to get info for image \'{0}\': {1}'.format(name, exc)
                return ret
    else:
        image_info = None

    if build:
        action = 'built'
    elif load:
        action = 'loaded'
    else:
        action = 'pulled'

    if __opts__['test']:
        ret['result'] = None
        if (image in all_tags and force) or image not in all_tags:
            ret['comment'] = 'Image \'{0}\' will be {1}'.format(name, action)
            return ret

    if build:
        try:
            image_update = __salt__['dockerng.build'](path=build, image=image)
        except Exception as exc:
            ret['comment'] = (
                'Encountered error building {0} as {1}: {2}'
                .format(build, image, exc)
            )
            return ret
        if image_info is None or image_update['Id'] != image_info['Id'][:12]:
            ret['changes'] = image_update

    elif load:
        try:
            image_update = __salt__['dockerng.load'](path=load, image=image)
        except Exception as exc:
            ret['comment'] = (
                'Encountered error loading {0} as {1}: {2}'
                .format(load, image, exc)
            )
            return ret
        if image_info is None or image_update.get('Layers', []):
            ret['changes'] = image_update

    else:
        try:
            image_update = __salt__['dockerng.pull'](
                image,
                insecure_registry=insecure_registry,
                client_timeout=client_timeout
            )
        except Exception as exc:
            ret['comment'] = (
                'Encountered error pulling {0}: {1}'
                .format(image, exc)
            )
            return ret
        if (image_info is not None and image_info['Id'][:12] == image_update
                .get('Layers', {})
                .get('Already_Pulled', [None])[0]):
            # Image was pulled again (because of force) but was also
            # already there. No new image was available on the registry.
            pass
        elif image_info is None or image_update.get('Layers', {}).get('Pulled'):
            # Only add to the changes dict if layers were pulled
            ret['changes'] = image_update

    ret['result'] = image in __salt__['dockerng.list_tags']()

    if not ret['result']:
        # This shouldn't happen, failure to pull should be caught above
        ret['comment'] = 'Image \'{0}\' could not be {1}'.format(name, action)
    elif not ret['changes']:
        ret['comment'] = (
            'Image \'{0}\' was {1}, but there were no changes'
            .format(name, action)
        )
    else:
        ret['comment'] = 'Image \'{0}\' was {1}'.format(name, action)
    return ret


def image_absent(name=None, images=None, force=False):
    '''
    Ensure that an image is absent from the Minion. Image names can be
    specified either using ``repo:tag`` notation, or just the repo name (in
    which case a tag of ``latest`` is assumed).

    images
        Run this state on more than one image at a time. The following two
        examples accomplish the same thing:

        .. code-block:: yaml

            remove_images:
              dockerng.image_absent:
                - names:
                  - busybox
                  - centos:6
                  - nginx

        .. code-block:: yaml

            remove_images:
              dockerng.image_absent:
                - images:
                  - busybox
                  - centos:6
                  - nginx

        However, the second example will be a bit quicker since Salt will do
        all the deletions in a single run, rather than executing the state
        separately on each image (as it would in the first example).

    force : False
        Salt will fail to remove any images currently in use by a container.
        Set this option to true to remove the image even if it is already
        present.

        .. note::

            This option can also be overridden by Pillar data. If the Minion
            has a pillar variable named ``dockerng.running.force`` which is
            set to ``True``, it will turn on this option. This pillar variable
            can even be set at runtime. For example:

            .. code-block:: bash

                salt myminion state.sls docker_stuff pillar="{dockerng.force: True}"

            If this pillar variable is present and set to ``False``, then it
            will turn off this option.

            For more granular control, setting a pillar variable named
            ``dockerng.force.image_name`` will affect only the named image.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not name and not images:
        ret['comment'] = 'One of \'name\' and \'images\' must be provided'
        return ret
    elif images is not None:
        targets = []
        for target in images:
            try:
                targets.append(':'.join(_get_repo_tag(target)))
            except TypeError:
                # Don't stomp on images with unicode characters in Python 2,
                # only force image to be a str if it wasn't already (which is
                # very unlikely).
                targets.append(':'.join(_get_repo_tag(str(target))))
    elif name:
        try:
            targets = [':'.join(_get_repo_tag(name))]
        except TypeError:
            targets = [':'.join(_get_repo_tag(str(name)))]

    pre_tags = __salt__['dockerng.list_tags']()
    to_delete = [x for x in targets if x in pre_tags]
    log.debug('targets = {0}'.format(targets))
    log.debug('to_delete = {0}'.format(to_delete))

    if not to_delete:
        ret['result'] = True
        if len(targets) == 1:
            ret['comment'] = 'Image \'{0}\' is not present'.format(name)
        else:
            ret['comment'] = 'All specified images are not present'
        return ret

    if __opts__['test']:
        ret['result'] = None
        if len(to_delete) == 1:
            ret['comment'] = ('Image \'{0}\' will be removed'
                              .format(to_delete[0]))
        else:
            ret['comment'] = ('The following images will be removed: {0}'
                              .format(', '.join(to_delete)))
        return ret

    result = __salt__['dockerng.rmi'](*to_delete, force=force)
    post_tags = __salt__['dockerng.list_tags']()
    failed = [x for x in to_delete if x in post_tags]

    if failed:
        if [x for x in to_delete if x not in post_tags]:
            ret['changes'] = result
            ret['comment'] = (
                'The following image(s) failed to be removed: {0}'
                .format(', '.join(failed))
            )
        else:
            ret['comment'] = 'None of the specified images were removed'
            if 'Errors' in result:
                ret['comment'] += (
                    '. The following errors were encountered: {0}'
                    .format('; '.join(result['Errors']))
                )
    else:
        ret['changes'] = result
        if len(to_delete) == 1:
            ret['comment'] = 'Image \'{0}\' was removed'.format(to_delete[0])
        else:
            ret['comment'] = (
                'The following images were removed: {0}'
                .format(', '.join(to_delete))
            )
        ret['result'] = True

    return ret


def running(name,
            image=None,
            force=False,
            stop_timeout=STOP_TIMEOUT,
            validate_ip_addrs=True,
            watch_action='force',
            client_timeout=CLIENT_TIMEOUT,
            start=True,
            **kwargs):
    '''
    Ensure that a container with a specific configuration is present and
    running

    name
        Name of the container

    image
        Image to use for the container. Image names can be specified either
        using ``repo:tag`` notation, or just the repo name (in which case a tag
        of ``latest`` is assumed).

        .. note::

            This state will pull the image if it is not present. However, if
            the image needs to be built from a Dockerfile or loaded from a
            saved image, or if you would like to use requisites to trigger a
            replacement of the container when the image is updated, then the
            :py:func:`dockerng.image_present
            <salt.modules.dockerng.image_present>` should be used to manage the
            image.

    force : False
        Set this parameter to ``True`` to force Salt to re-create the container
        irrespective of whether or not it is configured as desired.

    stop_timeout : 10
        If the container needs to be replaced, the container will be stopped
        using :py:func:`dockerng.stop <salt.modules.dockerng.stop>`. The value
        of this parameter will be passed to :py:func:`dockerng.stop
        <salt.modules.dockerng.stop>` as the ``timeout`` value, telling Docker
        how long to wait for a graceful shutdown before killing the container.

    validate_ip_addrs : True
        For parameters which accept IP addresses as input, IP address
        validation will be performed. To disable, set this to ``False``

    watch_action : force
        Control what type of action is taken when this state :ref:`watches
        <requisites-watch>` another state that has changes. The default action
        is ``force``, which runs the state with ``force`` set to ``True``,
        triggering a rebuild of the container.

        If any other value is passed, it will be assumed to be a kill signal.
        If the container matches the specified configuration, and is running,
        then the action will be to send that signal to the container. Kill
        signals can be either strings or numbers, and are defined in the
        **Standard Signals** section of the ``signal(7)`` manpage. Run ``man 7
        signal`` on a Linux host to browse this manpage. For example:

        .. code-block:: yaml

            mycontainer:
              dockerng.running:
                - image: busybox
                - watch_action: SIGHUP
                - watch:
                  - file: some_file

        .. note::

            If the container differs from the specified configuration, or is
            not running, then instead of sending a signal to the container, the
            container will be re-created/started and no signal will be sent.

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        this function, but for receiving a response from the API.

        .. note::

            This is only used if Salt needs to pull the requested image.


    **CONTAINER CONFIGURATION PARAMETERS**

    command or cmd
        Command to run in the container

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - command: bash

        OR

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - cmd: bash

        .. versionchanged:: 2015.8.1
            ``cmd`` is now also accepted

    hostname
        Hostname of the container. If not provided, and if a ``name`` has been
        provided, the ``hostname`` will default to the ``name`` that was
        passed.

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - hostname: web1

        .. warning::

            ``hostname`` cannot be set if ``network_mode`` is set to ``host``.
            The below example will result in an error:

            .. code-block:: yaml

                foo:
                  dockerng.running:
                    - image: bar/baz:latest
                    - hostname: web1
                    - network_mode: host

    domainname
        Domain name of the container

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - hostname: domain.tld


    interactive : False
        Leave stdin open

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - interactive: True

    tty : False
        Attach TTYs

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - tty: True

    detach : True
        If ``True``, run the container's command in the background (daemon
        mode)

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - detach: False

    user
        User under which to run docker

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - user: foo

    memory : 0
        Memory limit. Can be specified in bytes or using single-letter units
        (i.e. ``512M``, ``2G``, etc.). A value of ``0`` (the default) means no
        memory limit.

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - memory: 512M

    memory_swap : -1
        Total memory limit (memory plus swap). Set to ``-1`` to disable swap. A
        value of ``0`` means no swap limit.

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - memory_swap: 1G

    mac_address
        MAC address to use for the container. If not specified, a random MAC
        address will be used.

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - mac_address: 01:23:45:67:89:0a

    network_disabled : False
        If ``True``, networking will be disabled within the container

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - network_disabled: True

    working_dir
        Working directory inside the container

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - working_dir: /var/log/nginx

    entrypoint
        Entrypoint for the container

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - entrypoint: "mycmd --arg1 --arg2"

        The entrypoint can also be specified as a list of arguments:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - entrypoint:
                  - mycmd
                  - --arg1
                  - --arg2

    environment
        Either a list of variable/value mappings, or a list of strings in the
        format ``VARNAME=value``. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - environment:
                  - VAR1: value
                  - VAR2: value

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - environment:
                  - VAR1=value
                  - VAR2=value

        .. note::

            Values must be strings. Otherwise it will be considered
            as an error.

    ports
        A list of ports to expose on the container. Can either be a
        comma-separated list or a YAML list. If the protocol is omitted, the
        port will be assumed to be a TCP port. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - ports: 1111,2222/udp

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - ports:
                  - 1111
                  - 2222/udp

    volumes : None
        List of directories to expose as volumes. Can either be a
        comma-separated list or a YAML list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - volumes: /mnt/vol1,/mnt/vol2

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - volumes:
                  - /mnt/vol1
                  - /mnt/vol2

    cpu_shares
        CPU shares (relative weight)

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - cpu_shares: 0.5

    cpuset
        CPUs on which which to allow execution, specified as a string
        containing a range (e.g. ``0-3``) or a comma-separated list of CPUs
        (e.g. ``0,1``).

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - cpuset: "0,1"

    binds
        Files/directories to bind mount. Each bind mount should be passed in
        the format ``<host_path>:<container_path>:<read_only>``, where
        ``<read_only>`` is one of ``rw`` (for read-write access) or ``ro`` (for
        read-only access).

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - binds: /srv/www:/var/www:ro,/etc/foo.conf:/usr/local/etc/foo.conf:rw

        Binds can be passed as a YAML list instead of a comma-separated list:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - binds:
                  - /srv/www:/var/www:ro
                  - /home/myuser/conf/foo.conf:/etc/foo.conf:rw

        Optionally, the read-only information can be left off the end and the
        bind mount will be assumed to be read-write. The example below is
        equivalent to the one above:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - binds:
                  - /srv/www:/var/www:ro
                  - /home/myuser/conf/foo.conf:/etc/foo.conf

    port_bindings
        Bind exposed ports. Port bindings should be passed in the same way as
        the ``--publish`` argument to the ``docker run`` CLI command:

        - ``ip:hostPort:containerPort`` - Bind a specific IP and port on the
          host to a specific port within the container.
        - ``ip::containerPort`` - Bind a specific IP and an ephemeral port to a
          specific port within the container.
        - ``hostPort:containerPort`` - Bind a specific port on all of the
          host's interfaces to a specific port within the container.
        - ``containerPort`` - Bind an ephemeral port on all of the host's
          interfaces to a specific port within the container.

        Multiple bindings can be separated by commas, or passed as a Python
        list. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - port_bindings: "5000:5000,2123:2123/udp,8080"

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - port_bindings:
                  - 5000:5000
                  - 2123:2123/udp
                  - "8080"

        .. note::

            When configuring bindings for UDP ports, the protocol must be
            passed in the ``containerPort`` value, as seen in the examples
            above.

    lxc_conf
        Additional LXC configuration parameters to set before starting the
        container.

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - lxc_conf:
                  - lxc.utsname: docker

        .. note::

            These LXC configuration parameters will only have the desired
            effect if the container is using the LXC execution driver, which
            has not been the default for some time.

    publish_all_ports : False
        Allocates a random host port for each port exposed using the ``ports``
        parameter

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - ports: 8080
                - publish_all_ports: True

    links
        Link this container to another. Links should be specified in the format
        ``<container_name_or_id>:<link_alias>``. Multiple links can be passed,
        either as a comma separated list or a YAML list. The below two examples
        are equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - links: web1:link1,web2:link2

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - links:
                  - web1:link1
                  - web2:link2

    dns
        List of DNS nameservers. Can be passed as a comma-separated list or a
        YAML list. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - dns: 8.8.8.8,8.8.4.4

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - dns:
                  - 8.8.8.8
                  - 8.8.4.4

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

    dns_search
        List of DNS search domains. Can be passed as a comma-separated list
        or a YAML list. The below two examples are equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - dns_search: foo1.domain.tld,foo2.domain.tld

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - dns_search:
                  - foo1.domain.tld
                  - foo2.domain.tld

    volumes_from
        Container names or IDs from which the container will get volumes. Can
        be passed as a comma-separated list or a YAML list. The below two
        examples are equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - volumes_from: foo

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - volumes_from:
                  - foo

    network_mode : bridge
        One of the following:

        - ``bridge`` - Creates a new network stack for the container on the
          docker bridge
        - ``null`` - No networking (equivalent of the Docker CLI argument
          ``--net=none``)
        - ``container:<name_or_id>`` - Reuses another container's network stack
        - ``host`` - Use the host's network stack inside the container
        - Any name that identifies an existing network that might be created
          with ``dockerng.network_present``.

          .. warning::

                Using ``host`` mode gives the container full access to the
                hosts system's services (such as D-bus), and is therefore
                considered insecure.

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - network_mode: null

    restart_policy
        Set a restart policy for the container. Must be passed as a string in
        the format ``policy[:retry_count]`` where ``policy`` is one of
        ``always`` or ``on-failure``, and ``retry_count`` is an optional limit
        to the number of retries. The retry count is ignored when using the
        ``always`` restart policy.

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - restart_policy: on-failure:5

            bar:
              dockerng.running:
                - image: bar/baz:latest
                - restart_policy: always

    cap_add
        List of capabilities to add within the container. Can be passed as a
        comma-separated list or a Python list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - cap_add: SYS_ADMIN,MKNOD

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - cap_add:
                  - SYS_ADMIN
                  - MKNOD

        .. note::

            This option requires Docker 1.2.0 or newer.

    cap_drop
        List of capabilities to drop within the container. Can be passed as a
        comma-separated list or a Python list. The below two examples are
        equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - cap_drop: SYS_ADMIN,MKNOD

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - cap_drop:
                  - SYS_ADMIN
                  - MKNOD

        .. note::

            This option requires Docker 1.2.0 or newer.
    privileged
        Give extended privileges to container.

        .. code-block:: yaml
            foo:
              docker.running:
                - image: bar/baz:lates
                - privileged: True

    extra_hosts
        Additional hosts to add to the container's /etc/hosts file. Can be
        passed as a comma-separated list or a Python list. The below two
        exampels are equivalent:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - extra_hosts: web1:10.9.8.7,web2:10.9.8.8

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - extra_hosts:
                  - web1:10.9.8.7
                  - web2:10.9.8.8

        .. note::

            To skip IP address validation, use ``validate_ip_addrs=False``

        .. note::

            This option requires Docker 1.3.0 or newer.

    pid_mode
        Set to ``host`` to use the host container's PID namespace within the
        container

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - pid_mode: host

        .. note::

            This option requires Docker 1.5.0 or newer.

    ulimits
        List of ulimits. These limits should be passed in
        the format ``<ulimit_name>:<soft_limit>:<hard_limit>``, with the hard
        limit being optional.

        .. versionadded:: 2016.3.6,2016.11.4,Nitrogen

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - ulimits: nofile=1024:1024,nproc=60

        Ulimits can be passed as a YAML list instead of a comma-separated list:

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - ulimits:
                  - nofile=1024:1024
                  - nproc=60

    labels
        Add Metadata to the container. Can be a list of strings/dictionaries
        or a dictionary of strings (keys and values).

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - labels:
                    - LABEL1
                    - LABEL2

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - labels:
                    KEY1: VALUE1
                    KEY2: VALUE2

        .. code-block:: yaml

            foo:
              dockerng.running:
                - image: bar/baz:latest
                - labels:
                  - KEY1: VALUE1
                  - KEY2: VALUE2

    start : True
        Set to ``False`` to suppress starting of the container if it exists,
        matches the desired configuration, but is not running. This is useful
        for data-only containers, or for non-daemonized container processes,
        such as the django ``migrate`` and ``collectstatic`` commands. In
        instances such as this, the container only needs to be started the
        first time.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if image is None:
        ret['comment'] = 'The \'image\' argument is required'
        return ret

    if 'cmd' in kwargs:
        if 'command' in kwargs:
            ret['comment'] = (
                'Only one of \'command\' and \'cmd\' can be used. Both '
                'arguments are equivalent.'
            )
            ret['result'] = False
            return ret
        kwargs['command'] = kwargs.pop('cmd')

    try:
        image = ':'.join(_get_repo_tag(image))
    except TypeError:
        image = ':'.join(_get_repo_tag(str(image)))

    if image not in __salt__['dockerng.list_tags']():
        try:
            # Pull image
            pull_result = __salt__['dockerng.pull'](
                image,
                client_timeout=client_timeout,
            )
        except Exception as exc:
            comments = ['Failed to pull {0}: {1}'.format(image, exc)]
            ret['comment'] = _format_comments(comments)
            return ret
        else:
            ret['changes']['image'] = pull_result

    image_id = __salt__['dockerng.inspect_image'](image)['Id']

    if name not in __salt__['dockerng.list_containers'](all=True):
        pre_config = {}
    else:
        try:
            pre_config = __salt__['dockerng.inspect_container'](name)
            try:
                current_image_id = pre_config['Image']
            except KeyError:
                ret['comment'] = (
                    'Unable to detect current image for container \'{0}\'. '
                    'This might be due to a change in the Docker API.'
                    .format(name)
                )
                return ret
        except CommandExecutionError as exc:
            ret['comment'] = ('Error occurred checking for existence of '
                              'container \'{0}\': {1}'.format(name, exc))
            return ret

    # Don't allow conflicting options to be set
    if kwargs.get('publish_all_ports') \
            and kwargs.get('port_bindings') is not None:
        ret['comment'] = 'Cannot mix publish_all_ports=True and port_bindings'
        return ret
    if kwargs.get('hostname') is not None \
            and kwargs.get('network_mode') == 'host':
        ret['comment'] = 'Cannot mix hostname with network_mode=True'
        return ret

    # Strip __pub kwargs and divide the remaining arguments into the ones for
    # container creation and the ones for starting containers.
    create_kwargs = salt.utils.clean_kwargs(**copy.deepcopy(kwargs))
    send_signal = create_kwargs.pop('send_signal', False)

    invalid_kwargs = set(create_kwargs.keys()).difference(set(VALID_CREATE_OPTS.keys()))
    if invalid_kwargs:
        ret['comment'] = (
            'The following arguments are invalid: {0}'
            .format(', '.join(invalid_kwargs))
        )
        return ret

    # Input validation
    try:
        # Repack any dictlists that need it
        _prep_input(create_kwargs)
        # Perform data type validation and, where necessary, munge
        # the data further so it is in a format that can be passed
        # to dockerng.create.
        _validate_input(create_kwargs,
                        validate_ip_addrs=validate_ip_addrs)

        defaults_from_image = _get_defaults_from_image(image_id)
        if create_kwargs.get('binds') is not None:
            # Be smart and try to provide `volumes` argument derived from the
            # "binds" configuration.
            auto_volumes = [x['bind'] for x in six.itervalues(create_kwargs['binds'])]
            actual_volumes = create_kwargs.setdefault('volumes', [])
            actual_volumes.extend([v for v in auto_volumes if
                                   v not in actual_volumes])
        if create_kwargs.get('port_bindings') is not None:
            # Be smart and try to provide `ports` argument derived from
            # the "port_bindings" configuration.
            auto_ports = [_map_port_from_yaml_to_docker(port)
                          for port in create_kwargs['port_bindings']]
            actual_ports = create_kwargs.setdefault('ports', [])
            actual_ports.extend([p for p in auto_ports if
                                 p not in actual_ports])

    except SaltInvocationError as exc:
        ret['comment'] = '{0}'.format(exc)
        return ret

    changes_needed = {}
    if force:
        # No need to check the container config if force=True, or the image was
        # updated in the block above.
        new_container = True
    else:
        # Only compare the desired configuration if the named container is
        # already present. If it is not, pre_config will be an empty dict,
        # hence "not pre_config" will tell us if the named container is
        # present.
        if not pre_config:
            new_container = True
        else:
            if current_image_id != image_id:
                # Image name doesn't match, so there's no need to check the
                # container configuration.
                new_container = True
            else:
                # Container is the correct image, let's check the container
                # config and see if we need to replace the container
                defaults_from_image = _get_defaults_from_image(image_id)
                try:
                    changes_needed = _compare(pre_config, create_kwargs,
                                              defaults_from_image)
                    if changes_needed:
                        log.debug(
                            'dockerng.running: Analysis of container \'{0}\' '
                            'reveals the following changes need to be made: '
                            '{1}'.format(name, changes_needed)
                        )
                    else:
                        log.debug(
                            'dockerng.running: Container \'{0}\' already '
                            'matches the desired configuration'.format(name)
                        )
                except Exception as exc:
                    exc_info = ''.join(traceback.format_tb(sys.exc_info()[2]))
                    msg = (
                        'Uncaught exception "{0}" encountered while comparing '
                        'existing container against desired configuration.'
                        .format(exc)
                    )
                    log.error(msg + ' Exception info follows:\n' + exc_info)
                    ret['comment'] = \
                        msg + ' See minion log for exception info.'
                    return ret
                new_container = bool(changes_needed)

    if __opts__['test']:
        if not new_container:
            ret['result'] = True
            ret['comment'] = (
                'Container \'{0}\' is already configured as specified'
                .format(name)
            )
        else:
            ret['result'] = None
            ret['comment'] = 'Container \'{0}\' will be '.format(name)
            if pre_config and force:
                ret['comment'] += 'forcibly replaced'
            else:
                ret['comment'] += 'created' if not pre_config else 'replaced'
        return ret

    comments = []
    if not pre_config:
        pre_state = None
    else:
        pre_state = __salt__['dockerng.state'](name)

    if new_container:
        if pre_config:
            # Container exists, stop if necessary, then remove and recreate
            if pre_state != 'stopped':
                result = __salt__['dockerng.stop'](name,
                                                   timeout=stop_timeout,
                                                   unpause=True)['result']
                if result is not True:
                    comments.append(
                        'Container was slated to be replaced, but the '
                        'container could not be stopped.'
                    )
                    ret['comment'] = _format_comments(comments)
                    return ret

            # Remove existing container
            removed_ids = __salt__['dockerng.rm'](name)
            if not removed_ids:
                comments.append('Failed to remove container {0}'.format(name))
                ret['comment'] = _format_comments(comments)
                return ret

            # Removal was successful, add the list of removed IDs to the
            # changes dict.
            ret['changes']['removed'] = removed_ids

        if image not in __salt__['dockerng.list_tags']():
            try:
                # Pull image
                pull_result = __salt__['dockerng.pull'](
                    image,
                    client_timeout=client_timeout,
                )
            except Exception as exc:
                comments.append('Failed to pull {0}: {1}'.format(image, exc))
                ret['comment'] = _format_comments(comments)
                return ret
            else:
                ret['changes']['image'] = pull_result

        try:
            # Create new container
            create_result = __salt__['dockerng.create'](
                image,
                name=name,
                validate_ip_addrs=False,
                # Already validated input
                validate_input=False,
                client_timeout=client_timeout,
                **create_kwargs
            )
        except Exception as exc:
            comments.append('Failed to create new container: {0}'.format(exc))
            ret['comment'] = _format_comments(comments)
            return ret

        # Creation of new container was successful, add the return data to the
        # changes dict.
        ret['changes']['added'] = create_result

    if new_container or (pre_state != 'running' and start):
        try:
            # Start container
            __salt__['dockerng.start'](
                name,
            )
        except Exception as exc:
            comments.append(
                'Failed to start new container \'{0}\': {1}'
                .format(name, exc)
            )
            ret['comment'] = _format_comments(comments)
            return ret

        post_state = __salt__['dockerng.state'](name)
        if pre_state != post_state:
            # If the container changed states at all, note this change in the
            # return dict.
            comments.append(
                 'Container \'{0}\' changed state.'.format(name)
            )
            ret['changes']['state'] = {'old': pre_state, 'new': post_state}

    if changes_needed:
        try:
            post_config = __salt__['dockerng.inspect_container'](name)
            defaults_from_image = _get_defaults_from_image(image_id)
            changes_still_needed = _compare(post_config, create_kwargs,
                                            defaults_from_image)
            if changes_still_needed:
                log.debug(
                    'dockerng.running: Analysis of container \'{0}\' after '
                    'creation/replacement reveals the following changes still '
                    'need to be made: {1}'.format(name, changes_still_needed)
                )
            else:
                log.debug(
                    'dockerng.running: Changes successfully applied to '
                    'container \'{0}\''.format(name)
                )
        except Exception as exc:
            exc_info = ''.join(traceback.format_tb(sys.exc_info()[2]))
            msg = (
                'Uncaught exception "{0}" encountered while comparing '
                'new container\'s configuration against desired configuration'
                .format(exc)
            )
            log.error(msg + '. Exception info follows:\n' + exc_info)
            comments.extend([msg, 'See minion log for exception info'])
            ret['comment'] = _format_comments(comments)
            return ret

        if changes_still_needed:
            diff = ret['changes'].setdefault('diff', {})
            failed = []
            for key in changes_needed:
                if key not in changes_still_needed:
                    # Change was applied successfully
                    diff[key] = changes_needed[key]
                else:
                    # Change partially (or not at all) applied
                    old = changes_needed[key]['old']
                    new = changes_still_needed[key]['old']
                    if old != new:
                        diff[key] = {'old': old, 'new': new}
                    failed.append(key)
            comments.append(
                'Failed to apply configuration for the following parameters: '
                '{0}'.format(', '.join(failed))
            )
            ret['comment'] = _format_comments(comments)
            return ret
        else:
            # No necessary changes detected on post-container-replacement
            # check. The diffs will be the original changeset detected in
            # pre-flight check.
            ret['changes']['diff'] = changes_needed
            comments.append('Container \'{0}\' was replaced'.format(name))
    else:
        if not new_container:
            if send_signal:
                try:
                    __salt__['dockerng.signal'](name, signal=watch_action)
                except CommandExecutionError as exc:
                    comments.append(
                        'Failed to signal container: {0}'.format(exc)
                    )
                    ret['comment'] = _format_comments(comments)
                    return ret
                else:
                    ret['changes']['signal'] = watch_action
                    comments.append(
                        'Sent signal {0} to container'.format(watch_action)
                    )
            elif ret['changes']:
                if not comments:
                    log.warning(
                        'dockerng.running: we detected changes without '
                        'a specific comment for container \'{0}\'.'.format(
                            name)
                    )
                    comments.append('Container \'{0}\' changed.'.format(name))
            else:
                # Container was not replaced, no necessary changes detected
                # in pre-flight check, and no signal sent to container
                comments.append(
                    'Container \'{0}\' is already configured as specified'
                    .format(name)
                )
        else:
            msg = 'Container \'{0}\' was '.format(name)
            if pre_config and force:
                msg += 'forcibly replaced'
            else:
                msg += 'created' if not pre_config else 'replaced'
            comments.append(msg)

            if pre_config and image != pre_config['Config']['Image']:
                diff = ret['changes'].setdefault('diff', {})
                diff['image'] = {'old': pre_config['Config']['Image'],
                                 'new': image}
                comments.append(
                    'Image changed from \'{0}\' to \'{1}\''
                    .format(pre_config['Config']['Image'], image)
                )

    ret['comment'] = _format_comments(comments)
    ret['result'] = True
    return ret


def stopped(name=None,
            containers=None,
            stop_timeout=STOP_TIMEOUT,
            unpause=False,
            error_on_absent=True):
    '''
    Ensure that a container (or containers) is stopped

    name
        Name or ID of the container

    containers
        Run this state on more than one container at a time. The following two
        examples accomplish the same thing:

        .. code-block:: yaml

            stopped_containers:
              dockerng.stopped:
                - names:
                  - foo
                  - bar
                  - baz

        .. code-block:: yaml

            stopped_containers:
              dockerng.stopped:
                - containers:
                  - foo
                  - bar
                  - baz

        However, the second example will be a bit quicker since Salt will stop
        all specified containers in a single run, rather than executing the
        state separately on each image (as it would in the first example).

    stop_timeout : 10
        Timeout for graceful shutdown of the container. If this timeout is
        exceeded, the container will be killed.

    unpause : False
        Set to ``True`` to unpause any paused containers before stopping. If
        unset, then an error will be raised for any container that was paused.

    error_on_absent : True
        By default, this state will return an error if any of the specified
        containers are absent. Set this to ``False`` to suppress that error.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not name and not containers:
        ret['comment'] = 'One of \'name\' and \'containers\' must be provided'
        return ret
    if containers is not None:
        if not isinstance(containers, list):
            ret['comment'] = 'containers must be a list'
            return ret
        targets = []
        for target in containers:
            if not isinstance(target, six.string_types):
                target = str(target)
            targets.append(target)
    elif name:
        if not isinstance(name, six.string_types):
            targets = [str(name)]
        else:
            targets = [name]

    containers = {}
    for target in targets:
        try:
            c_state = __salt__['dockerng.state'](target)
        except CommandExecutionError:
            containers.setdefault('absent', []).append(target)
        else:
            containers.setdefault(c_state, []).append(target)

    errors = []
    if error_on_absent and 'absent' in containers:
        errors.append(
            'The following container(s) are absent: {0}'.format(
                ', '.join(containers['absent'])
            )
        )

    if not unpause and 'paused' in containers:
        ret['result'] = False
        errors.append(
            'The following container(s) are paused: {0}'.format(
                ', '.join(containers['paused'])
            )
        )

    if errors:
        ret['result'] = False
        ret['comment'] = '. '.join(errors)
        return ret

    to_stop = containers.get('running', []) + containers.get('paused', [])

    if not to_stop:
        ret['result'] = True
        if len(targets) == 1:
            ret['comment'] = 'Container \'{0}\' is '.format(targets[0])
        else:
            ret['comment'] = 'All specified containers are '
        if 'absent' in containers:
            ret['comment'] += 'absent or '
        ret['comment'] += 'not running'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = (
            'The following container(s) will be stopped: {0}'
            .format(', '.join(to_stop))
        )
        return ret

    stop_errors = []
    for target in to_stop:
        changes = __salt__['dockerng.stop'](target,
                                             timeout=stop_timeout,
                                             unpause=unpause)
        if changes['result'] is True:
            ret['changes'][target] = changes
        else:
            if 'comment' in changes:
                stop_errors.append(changes['comment'])
            else:
                stop_errors.append(
                    'Failed to stop container \'{0}\''.format(target)
                )

    if stop_errors:
        ret['comment'] = '; '.join(stop_errors)
        return ret

    ret['result'] = True
    ret['comment'] = (
        'The following container(s) were stopped: {0}'
        .format(', '.join(to_stop))
    )
    return ret


def absent(name, force=False):
    '''
    Ensure that a container is absent

    name
        Name of the container

    force : False
        Set to ``True`` to remove the container even if it is running

    Usage Examples:

    .. code-block:: yaml

        mycontainer:
          dockerng.absent

        multiple_containers:
          dockerng.absent:
            - names:
              - foo
              - bar
              - baz
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if name not in __salt__['dockerng.list_containers'](all=True):
        ret['result'] = True
        ret['comment'] = 'Container \'{0}\' does not exist'.format(name)
        return ret

    pre_state = __salt__['dockerng.state'](name)
    if pre_state != 'stopped' and not force:
        ret['comment'] = ('Container is running, set force to True to '
                          'forcibly remove it')
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('Container \'{0}\' will be removed'.format(name))
        return ret

    try:
        ret['changes']['removed'] = __salt__['dockerng.rm'](name, force=force)
    except Exception as exc:
        ret['comment'] = ('Failed to remove container \'{0}\': {1}'
                          .format(name, exc))
        return ret

    if name in __salt__['dockerng.list_containers'](all=True):
        ret['comment'] = 'Failed to remove container \'{0}\''.format(name)
    else:
        if force and pre_state != 'stopped':
            method = 'Forcibly'
        else:
            method = 'Successfully'
        ret['comment'] = '{0} removed container \'{1}\''.format(method, name)
        ret['result'] = True
    return ret


def network_present(name, driver=None, containers=None):
    '''
    Ensure that a network is present.

    name
        Name of the network

    driver
        Type of driver for that network.

    containers:
        List of container names that should be part of this network
    Usage Examples:

    .. code-block:: yaml

        network_foo:
          dockerng.network_present


    .. code-block:: yaml

        network_bar:
          dockerng.network_present
            - name: bar
            - containers:
                - cont1
                - cont2

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if containers is None:
        containers = []
    # map containers to container's Ids.
    containers = [__salt__['dockerng.inspect_container'](c)['Id'] for c in containers]
    networks = __salt__['dockerng.networks'](names=[name])
    if networks:
        network = networks[0]  # we expect network's name to be unique
        if all(c in network['Containers'] for c in containers):
            ret['result'] = True
            ret['comment'] = 'Network \'{0}\' already exists.'.format(name)
            return ret
        result = True
        for container in containers:
            if container not in network['Containers']:
                try:
                    ret['changes']['connected'] = __salt__['dockerng.connect_container_to_network'](
                        container, name)
                except Exception as exc:
                    ret['comment'] = ('Failed to connect container \'{0}\' to network \'{1}\' {2}'.format(
                        container, name, exc))
                    result = False
            ret['result'] = result

    else:
        try:
            ret['changes']['created'] = __salt__['dockerng.create_network'](
                name, driver=driver)
        except Exception as exc:
            ret['comment'] = ('Failed to create network \'{0}\': {1}'
                              .format(name, exc))
        else:
            result = True
            for container in containers:
                try:
                    ret['changes']['connected'] = __salt__['dockerng.connect_container_to_network'](
                        container, name)
                except Exception as exc:
                    ret['comment'] = ('Failed to connect container \'{0}\' to network \'{1}\' {2}'.format(
                        container, name, exc))
                    result = False
            ret['result'] = result
    return ret


def network_absent(name, driver=None):
    '''
    Ensure that a network is absent.

    name
        Name of the network

    Usage Examples:

    .. code-block:: yaml

        network_foo:
          dockerng.network_absent

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    networks = __salt__['dockerng.networks'](names=[name])
    if not networks:
        ret['result'] = True
        ret['comment'] = 'Network \'{0}\' already absent'.format(name)
        return ret

    for container in networks[0]['Containers']:
        try:
            ret['changes']['disconnected'] = __salt__['dockerng.disconnect_container_from_network'](container, name)
        except Exception as exc:
            ret['comment'] = ('Failed to disconnect container \'{0}\' to network \'{1}\' {2}'.format(
                container, name, exc))
    try:
        ret['changes']['removed'] = __salt__['dockerng.remove_network'](name)
        ret['result'] = True
    except Exception as exc:
        ret['comment'] = ('Failed to remove network \'{0}\': {1}'
                          .format(name, exc))
    return ret


def volume_present(name, driver=None, driver_opts=None, force=False):
    '''
    Ensure that a volume is present.

    .. versionadded:: 2015.8.4

    .. versionchanged:: 2015.8.6
        This function no longer deletes and re-creates a volume if the
        existing volume's driver does not match the ``driver``
        parameter (unless the ``force`` parameter is set to ``True``).

    name
        Name of the volume

    driver
        Type of driver for that volume.  If ``None`` and the volume
        does not yet exist, the volume will be created using Docker's
        default driver.  If ``None`` and the volume does exist, this
        function does nothing, even if the existing volume's driver is
        not the Docker default driver.  (To ensure that an existing
        volume's driver matches the Docker default, you must
        explicitly name Docker's default driver here.)

    driver_opts
        Options for the volume driver

    force : False
        If the volume already exists but the existing volume's driver
        does not match the driver specified by the ``driver``
        parameter, this parameter controls whether the function errors
        out (if ``False``) or deletes and re-creates the volume (if
        ``True``).

        .. versionadded:: 2015.8.6

    Usage Examples:

    .. code-block:: yaml

        volume_foo:
          dockerng.volume_present


    .. code-block:: yaml

        volume_bar:
          dockerng.volume_present
            - name: bar
            - driver: local
            - driver_opts:
                foo: bar

    .. code-block:: yaml

        volume_bar:
          dockerng.volume_present
            - name: bar
            - driver: local
            - driver_opts:
                - foo: bar
                - option: value

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if salt.utils.is_dictlist(driver_opts):
        driver_opts = salt.utils.repack_dictlist(driver_opts)
    volume = _find_volume(name)
    if not volume:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('The volume \'{0}\' will be created'.format(name))
            return ret
        try:
            ret['changes']['created'] = __salt__['dockerng.create_volume'](
                name, driver=driver, driver_opts=driver_opts)
        except Exception as exc:
            ret['comment'] = ('Failed to create volume \'{0}\': {1}'
                              .format(name, exc))
            return ret
        else:
            result = True
            ret['result'] = result
            return ret
    # volume exists, check if driver is the same.
    if driver is not None and volume['Driver'] != driver:
        if not force:
            ret['comment'] = "Driver for existing volume '{0}' ('{1}')" \
                             " does not match specified driver ('{2}')" \
                             " and force is False".format(
                                 name, volume['Driver'], driver)
            ret['result'] = None if __opts__['test'] else False
            return ret
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = "The volume '{0}' will be replaced with a" \
                             " new one using the driver '{1}'".format(
                                 name, volume)
            return ret
        try:
            ret['changes']['removed'] = __salt__['dockerng.remove_volume'](name)
        except Exception as exc:
            ret['comment'] = ('Failed to remove volume \'{0}\': {1}'
                              .format(name, exc))
            return ret
        else:
            try:
                ret['changes']['created'] = __salt__['dockerng.create_volume'](
                    name, driver=driver, driver_opts=driver_opts)
            except Exception as exc:
                ret['comment'] = ('Failed to create volume \'{0}\': {1}'
                                .format(name, exc))
                return ret
            else:
                result = True
                ret['result'] = result
                return ret

    ret['result'] = None if __opts__['test'] else True
    ret['comment'] = 'Volume \'{0}\' already exists.'.format(name)
    return ret


def volume_absent(name, driver=None):
    '''
    Ensure that a volume is absent.

    .. versionadded:: 2015.8.4,

    name
        Name of the volume

    Usage Examples:

    .. code-block:: yaml

        volume_foo:
          dockerng.volume_absent

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    volume = _find_volume(name)
    if not volume:
        ret['result'] = True
        ret['comment'] = 'Volume \'{0}\' already absent'.format(name)
        return ret

    try:
        ret['changes']['removed'] = __salt__['dockerng.remove_volume'](name)
        ret['result'] = True
    except Exception as exc:
        ret['comment'] = ('Failed to remove volume \'{0}\': {1}'
                          .format(name, exc))
    return ret


def mod_watch(name, sfun=None, **kwargs):
    if sfun == 'running':
        watch_kwargs = copy.deepcopy(kwargs)
        if watch_kwargs.get('watch_action', 'force') == 'force':
            watch_kwargs['force'] = True
        else:
            watch_kwargs['send_signal'] = True
            watch_kwargs['force'] = False
        return running(name, **watch_kwargs)

    if sfun == 'stopped':
        return stopped(name, **salt.utils.clean_kwargs(**kwargs))

    if sfun == 'image_present':
        # Force image to be updated
        kwargs['force'] = True
        return image_present(name, **kwargs)

    return {'name': name,
            'changes': {},
            'result': False,
            'comment': ('watch requisite is not'
                        ' implemented for {0}'.format(sfun))}
