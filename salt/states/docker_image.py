# -*- coding: utf-8 -*-
'''
Management of Docker images

.. versionadded:: Nitrogen

:depends: docker_ Python module

.. note::
    Older releases of the Python bindings for Docker were called docker-py_ in
    PyPI. All releases of docker_, and releases of docker-py_ >= 1.6.0 are
    supported. These python bindings can easily be installed using
    :py:func:`pip.install <salt.modules.pip.install>`:

    .. code-block:: bash

        salt myminion pip.install docker

.. _docker: https://pypi.python.org/pypi/docker
.. _docker-py: https://pypi.python.org/pypi/docker-py

These states were moved from the :mod:`docker <salt.states.docker>` state
module (formerly called **dockerng**) in the Nitrogen release.

.. note::
    To pull from a Docker registry, authentication must be configured. See
    :ref:`here <docker-authentication>` for more information on how to
    configure access to docker registries in :ref:`Pillar <pillar>` data.
'''
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils.docker

# Enable proper logging
log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Define the module's virtual name
__virtualname__ = 'docker_image'


def __virtual__():
    '''
    Only load if the docker execution module is available
    '''
    if 'docker.version' in __salt__:
        return __virtualname__
    return (False, __salt__.missing_fun_string('docker.version'))


def present(name,
            build=None,
            load=None,
            force=False,
            insecure_registry=False,
            client_timeout=salt.utils.docker.CLIENT_TIMEOUT,
            dockerfile=None,
            sls=None,
            base='opensuse/python',
            saltenv='base',
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
          docker_image.present

    build
        Path to directory on the Minion containing a Dockerfile

        .. code-block:: yaml

            myuser/myimage:mytag:
              docker_image.present:
                - build: /home/myuser/docker/myimage


            myuser/myimage:mytag:
              docker_image.present:
                - build: /home/myuser/docker/myimage
                - dockerfile: Dockerfile.alternative

            .. versionadded:: 2016.11.0

        The image will be built using :py:func:`docker.build
        <salt.modules.docker.build>` and the specified image name and tag
        will be applied to it.

    load
        Loads a tar archive created with :py:func:`docker.load
        <salt.modules.docker.load>` (or the ``docker load`` Docker CLI
        command), and assigns it the specified repo and tag.

        .. code-block:: yaml

            myuser/myimage:mytag:
              docker_image.present:
                - load: salt://path/to/image.tar

    force : False
        Set this parameter to ``True`` to force Salt to pull/build/load the
        image even if it is already present.

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        the state, but for receiving a response from the API.

    dockerfile
        Allows for an alternative Dockerfile to be specified.  Path to alternative
        Dockefile is relative to the build path for the Docker container.

        .. versionadded:: 2016.11.0

    sls
        Allow for building images with ``dockerng.sls_build`` by specify the
        SLS files to build with. This can be a list or comma-seperated string.

        .. code-block:: yaml

            myuser/myimage:mytag:
              dockerng.image_present:
                - sls:
                    - webapp1
                    - webapp2
                - base: centos
                - saltenv: base

        .. versionadded: Nitrogen

    base
        Base image with which to start ``dockerng.sls_build``

        .. versionadded: Nitrogen

    saltenv
        environment from which to pull sls files for ``dockerng.sls_build``.

        .. versionadded: Nitrogen
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if build is not None and load is not None:
        ret['comment'] = 'Only one of \'build\' or \'load\' is permitted.'
        return ret

    # Ensure that we have repo:tag notation
    image = ':'.join(salt.utils.docker.get_repo_tag(name))
    all_tags = __salt__['docker.list_tags']()

    if image in all_tags:
        if not force:
            ret['result'] = True
            ret['comment'] = 'Image \'{0}\' already present'.format(name)
            return ret
        else:
            try:
                image_info = __salt__['docker.inspect_image'](name)
            except Exception as exc:
                ret['comment'] = \
                    'Unable to get info for image \'{0}\': {1}'.format(name, exc)
                return ret
    else:
        image_info = None

    if build or sls:
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
            image_update = __salt__['docker.build'](path=build,
                                                      image=image,
                                                      dockerfile=dockerfile)
        except Exception as exc:
            ret['comment'] = (
                'Encountered error building {0} as {1}: {2}'
                .format(build, image, exc)
            )
            return ret
        if image_info is None or image_update['Id'] != image_info['Id'][:12]:
            ret['changes'] = image_update

    elif sls:
        if isinstance(sls, list):
            sls = ','.join(sls)
        try:
            image_update = __salt__['dockerng.sls_build'](name=image,
                                                          base=base,
                                                          mods=sls,
                                                          saltenv=saltenv)
        except Exception as exc:
            ret['comment'] = (
                'Encountered error using sls {0} for building {1}: {2}'
                .format(sls, image, exc)
            )
            return ret
        if image_info is None or image_update['Id'] != image_info['Id'][:12]:
            ret['changes'] = image_update

    elif load:
        try:
            image_update = __salt__['docker.load'](path=load, image=image)
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
            image_update = __salt__['docker.pull'](
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

    ret['result'] = image in __salt__['docker.list_tags']()

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


def absent(name=None, images=None, force=False):
    '''
    Ensure that an image is absent from the Minion. Image names can be
    specified either using ``repo:tag`` notation, or just the repo name (in
    which case a tag of ``latest`` is assumed).

    images
        Run this state on more than one image at a time. The following two
        examples accomplish the same thing:

        .. code-block:: yaml

            remove_images:
              docker_image.absent:
                - names:
                  - busybox
                  - centos:6
                  - nginx

        .. code-block:: yaml

            remove_images:
              docker_image.absent:
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
            has a pillar variable named ``docker.running.force`` which is
            set to ``True``, it will turn on this option. This pillar variable
            can even be set at runtime. For example:

            .. code-block:: bash

                salt myminion state.sls docker_stuff pillar="{docker.force: True}"

            If this pillar variable is present and set to ``False``, then it
            will turn off this option.

            For more granular control, setting a pillar variable named
            ``docker.force.image_name`` will affect only the named image.
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
                targets.append(':'.join(salt.utils.docker.get_repo_tag(target)))
            except TypeError:
                # Don't stomp on images with unicode characters in Python 2,
                # only force image to be a str if it wasn't already (which is
                # very unlikely).
                targets.append(':'.join(salt.utils.docker.get_repo_tag(str(target))))
    elif name:
        try:
            targets = [':'.join(salt.utils.docker.get_repo_tag(name))]
        except TypeError:
            targets = [':'.join(salt.utils.docker.get_repo_tag(str(name)))]

    pre_tags = __salt__['docker.list_tags']()
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

    result = __salt__['docker.rmi'](*to_delete, force=force)
    post_tags = __salt__['docker.list_tags']()
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


def mod_watch(name, sfun=None, **kwargs):
    if sfun == 'present':
        # Force image to be updated
        kwargs['force'] = True
        return present(name, **kwargs)

    return {'name': name,
            'changes': {},
            'result': False,
            'comment': ('watch requisite is not'
                        ' implemented for {0}'.format(sfun))}
