# -*- coding: utf-8 -*-
'''
The pkgbuild state is the front of Salt package building backend. It
automatically

.. versionadded:: 2015.8.0

.. code-block:: yaml

    salt_2015.5.2:
      pkgbuild.built:
        - runas: thatch
        - results:
          - salt-2015.5.2-2.el7.centos.noarch.rpm
          - salt-api-2015.5.2-2.el7.centos.noarch.rpm
          - salt-cloud-2015.5.2-2.el7.centos.noarch.rpm
          - salt-master-2015.5.2-2.el7.centos.noarch.rpm
          - salt-minion-2015.5.2-2.el7.centos.noarch.rpm
          - salt-ssh-2015.5.2-2.el7.centos.noarch.rpm
          - salt-syndic-2015.5.2-2.el7.centos.noarch.rpm
        - dest_dir: /tmp/pkg
        - spec: salt://pkg/salt/spec/salt.spec
        - template: jinja
        - deps:
          - salt://pkg/salt/sources/required_dependency.rpm
        - tgt: epel-7-x86_64
        - sources:
          - salt://pkg/salt/sources/logrotate.salt
          - salt://pkg/salt/sources/README.fedora
          - salt://pkg/salt/sources/salt-2015.5.2.tar.gz
          - salt://pkg/salt/sources/salt-2015.5.2-tests.patch
          - salt://pkg/salt/sources/salt-api
          - salt://pkg/salt/sources/salt-api.service
          - salt://pkg/salt/sources/salt-master
          - salt://pkg/salt/sources/salt-master.service
          - salt://pkg/salt/sources/salt-minion
          - salt://pkg/salt/sources/salt-minion.service
          - salt://pkg/salt/sources/saltpkg.sls
          - salt://pkg/salt/sources/salt-syndic
          - salt://pkg/salt/sources/salt-syndic.service
          - salt://pkg/salt/sources/SaltTesting-2015.5.8.tar.gz
    /tmp/pkg:
      pkgbuild.repo
'''
# Import python libs
from __future__ import absolute_import, print_function
import errno
import logging
import os

# Import salt libs
import salt.utils
from salt.ext import six

log = logging.getLogger(__name__)


def _get_missing_results(results, dest_dir):
    '''
    Return a list of the filenames specified in the ``results`` argument, which
    are not present in the dest_dir.
    '''
    try:
        present = set(os.listdir(dest_dir))
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            log.debug(
                'pkgbuild.built: dest_dir \'{0}\' does not exist'
                .format(dest_dir)
            )
        elif exc.errno == errno.EACCES:
            log.error(
                'pkgbuilt.built: cannot access dest_dir \'{0}\''
                .format(dest_dir)
            )
        present = set()
    return sorted(set(results).difference(present))


def built(name,
          runas,
          dest_dir,
          spec,
          sources,
          tgt,
          template=None,
          deps=None,
          env=None,
          results=None,
          force=False,
          always=None,
          saltenv='base',
          log_dir='/var/log/salt/pkgbuild'):
    '''
    Ensure that the named package is built and exists in the named directory

    name
        The name to track the build, the name value is otherwise unused

    runas
        The user to run the build process as

    dest_dir
        The directory on the minion to place the built package(s)

    spec
        The location of the spec file (used for rpms)

    sources
        The list of package sources

    tgt
        The target platform to run the build on

    template
        Run the spec file through a templating engine

        .. versionchanged:: 2015.8.2
            This argument is now optional, allowing for no templating engine to
            be used if none is desired.

    deps
        Packages required to ensure that the named package is built
        can be hosted on either the salt master server or on an HTTP
        or FTP server.  Both HTTPS and HTTP are supported as well as
        downloading directly from Amazon S3 compatible URLs with both
        pre-configured and automatic IAM credentials

    env
        A dictionary of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

                - env:
                    DEB_BUILD_OPTIONS: 'nocheck'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :doc:`here
            </topics/troubleshooting/yaml_idiosyncrasies>`.

    results
        The names of the expected rpms that will be built

    force : False
        If ``True``, packages will be built even if they already exist in the
        ``dest_dir``. This is useful when building a package for continuous or
        nightly package builds.

        .. versionadded:: 2015.8.2

    always
        If ``True``, packages will be built even if they already exist in the
        ``dest_dir``. This is useful when building a package for continuous or
        nightly package builds.

        .. deprecated:: 2015.8.2
            Use ``force`` instead.

    saltenv
        The saltenv to use for files downloaded from the salt filesever

    log_dir : /var/log/salt/rpmbuild
        Root directory for log files created from the build. Logs will be
        organized by package name, version, OS release, and CPU architecture
        under this directory.

        .. versionadded:: 2015.8.2
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}

    if always is not None:
        salt.utils.warn_until(
            'Carbon',
            'The \'always\' argument to the pkgbuild.built state has been '
            'deprecated, please use \'force\' instead.'
        )
        force = always

    if not results:
        ret['comment'] = '\'results\' argument is required'
        ret['result'] = False
        return ret

    if isinstance(results, six.string_types):
        results = results.split(',')

    needed = _get_missing_results(results, dest_dir)
    if not force and not needed:
        ret['comment'] = 'All needed packages exist'
        return ret

    if __opts__['test']:
        ret['result'] = None
        if force:
            ret['comment'] = 'Packages will be force-built'
        else:
            ret['comment'] = 'The following packages need to be built: '
            ret['comment'] += ', '.join(needed)
        return ret

    # Need the check for None here, if env is not provided then it falls back
    # to None and it is assumed that the environment is not being overridden.
    if env is not None and not isinstance(env, dict):
        ret['comment'] = ('Invalidly-formatted \'env\' parameter. See '
                          'documentation.')
        ret['result'] = False
        return ret

    ret['changes'] = __salt__['pkgbuild.build'](
        runas,
        tgt,
        dest_dir,
        spec,
        sources,
        deps,
        env,
        template,
        saltenv,
        log_dir)

    needed = _get_missing_results(results, dest_dir)
    if needed:
        ret['comment'] = 'The following packages were not built: '
        ret['comment'] += ', '.join(needed)
        ret['result'] = False
    else:
        ret['comment'] = 'All needed packages were built'
    return ret


def repo(name, keyid=None, env=None):
    '''
    Make a package repository, the name is directoty to turn into a repo.
    This state is best used with onchanges linked to your package building
    states

    name
        The directory to find packages that will be in the repository

    keyid
        Optional Key ID to use in signing repository

    env
        A dictionary of environment variables to be utlilized in creating the repository.
        Example:

        .. code-block:: yaml

                - env:
                    OPTIONS: 'ask-passphrase'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :doc:`here
            </topics/troubleshooting/yaml_idiosyncrasies>`.

            Use of OPTIONS on some platforms, for example: ask-passphrase, will
            require gpg-agent or similar to cache passphrases.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if __opts__['test'] is True:
        ret['result'] = None
        ret['comment'] = 'Package repo at {0} will be rebuilt'.format(name)
        return ret

    # Need the check for None here, if env is not provided then it falls back
    # to None and it is assumed that the environment is not being overridden.
    if env is not None and not isinstance(env, dict):
        ret['comment'] = ('Invalidly-formatted \'env\' parameter. See '
                          'documentation.')
        return ret

    __salt__['pkgbuild.make_repo'](name, keyid, env)
    ret['changes'] = {'refresh': True}
    return ret
