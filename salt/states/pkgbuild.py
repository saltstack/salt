# -*- coding: utf-8 -*-
'''
The pkgbuild state is the front of Salt package building backend. It
automatically builds DEB and RPM packages from specified sources

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
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

    results
        The names of the expected rpms that will be built

    force : False
        If ``True``, packages will be built even if they already exist in the
        ``dest_dir``. This is useful when building a package for continuous or
        nightly package builds.

        .. versionadded:: 2015.8.2

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

    func = 'pkgbuild.build'
    if __grains__.get('os_family', False) not in ('RedHat', 'Suse'):
        for res in results:
            if res.endswith('.rpm'):
                func = 'rpmbuild.build'
                break

    ret['changes'] = __salt__[func](
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


def repo(name,
         keyid=None,
         env=None,
         use_passphrase=False,
         gnupghome='/etc/salt/gpgkeys',
         runas='builder',
         timeout=15.0):
    '''
    Make a package repository and optionally sign it and packages present

    The name is directory to turn into a repo. This state is best used
    with onchanges linked to your package building states.

    name
        The directory to find packages that will be in the repository

    keyid
        .. versionchanged:: 2016.3.0

        Optional Key ID to use in signing packages and repository.
        Utilizes Public and Private keys associated with keyid which have
        been loaded into the minion's Pillar data.

        For example, contents from a Pillar data file with named Public
        and Private keys as follows:

        .. code-block:: yaml

            gpg_pkg_priv_key: |
              -----BEGIN PGP PRIVATE KEY BLOCK-----
              Version: GnuPG v1

              lQO+BFciIfQBCADAPCtzx7I5Rl32escCMZsPzaEKWe7bIX1em4KCKkBoX47IG54b
              w82PCE8Y1jF/9Uk2m3RKVWp3YcLlc7Ap3gj6VO4ysvVz28UbnhPxsIkOlf2cq8qc
              .
              .
              Ebe+8JCQTwqSXPRTzXmy/b5WXDeM79CkLWvuGpXFor76D+ECMRPv/rawukEcNptn
              R5OmgHqvydEnO4pWbn8JzQO9YX/Us0SMHBVzLC8eIi5ZIopzalvX
              =JvW8
              -----END PGP PRIVATE KEY BLOCK-----

            gpg_pkg_priv_keyname: gpg_pkg_key.pem

            gpg_pkg_pub_key: |
              -----BEGIN PGP PUBLIC KEY BLOCK-----
              Version: GnuPG v1

              mQENBFciIfQBCADAPCtzx7I5Rl32escCMZsPzaEKWe7bIX1em4KCKkBoX47IG54b
              w82PCE8Y1jF/9Uk2m3RKVWp3YcLlc7Ap3gj6VO4ysvVz28UbnhPxsIkOlf2cq8qc
              .
              .
              bYP7t5iwJmQzRMyFInYRt77wkJBPCpJc9FPNebL9vlZcN4zv0KQta+4alcWivvoP
              4QIxE+/+trC6QRw2m2dHk6aAeq/J0Sc7ilZufwnNA71hf9SzRIwcFXMsLx4iLlki
              inNqW9c=
              =s1CX
              -----END PGP PUBLIC KEY BLOCK-----

            gpg_pkg_pub_keyname: gpg_pkg_key.pub

    env
        .. versionchanged:: 2016.3.0

        A dictionary of environment variables to be utilized in creating the
        repository. Example:

        .. code-block:: yaml

            - env:
                OPTIONS: 'ask-passphrase'

        .. warning::

            The above illustrates a common ``PyYAML`` pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other)
            ``PyYAML`` idiosyncrasies can be found :ref:`here
            <yaml-idiosyncrasies>`.

            Use of ``OPTIONS`` on some platforms, for example:
            ``ask-passphrase``, will require ``gpg-agent`` or similar to cache
            passphrases.

        .. note::

            This parameter is not used for making ``yum`` repositories.

    use_passphrase : False
        .. versionadded:: 2016.3.0

        Use a passphrase with the signing key presented in ``keyid``.
        Passphrase is received from Pillar data which could be passed on the
        command line with ``pillar`` parameter. For example:

        .. code-block:: bash

            pillar='{ "gpg_passphrase" : "my_passphrase" }'

    gnupghome : /etc/salt/gpgkeys
        .. versionadded:: 2016.3.0

        Location where GPG related files are stored, used with 'keyid'

    runas : builder
        .. versionadded:: 2016.3.0

        User to create the repository as, and optionally sign packages.

        .. note::

            Ensure the user has correct permissions to any files and
            directories which are to be utilized.

    timeout : 15.0
        .. versionadded:: 2016.3.4

        Timeout in seconds to wait for the prompt for inputting the passphrase.

    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}

    if __opts__['test'] is True:
        ret['result'] = None
        ret['comment'] = 'Package repo metadata at {0} will be refreshed'.format(name)
        return ret

    # Need the check for None here, if env is not provided then it falls back
    # to None and it is assumed that the environment is not being overridden.
    if env is not None and not isinstance(env, dict):
        ret['comment'] = ('Invalidly-formatted \'env\' parameter. See '
                          'documentation.')
        return ret

    func = 'pkgbuild.make_repo'
    if __grains__.get('os_family', False) not in ('RedHat', 'Suse'):
        for file in os.listdir(name):
            if file.endswith('.rpm'):
                func = 'rpmbuild.make_repo'
                break

    res = __salt__[func](name, keyid, env, use_passphrase, gnupghome, runas, timeout)

    if res['retcode'] > 0:
        ret['result'] = False
    else:
        ret['changes'] = {'refresh': True}

    if res['stdout'] and res['stderr']:
        ret['comment'] = "{0}\n{1}".format(res['stdout'], res['stderr'])
    elif res['stdout']:
        ret['comment'] = res['stdout']
    elif res['stderr']:
        ret['comment'] = res['stderr']

    return ret
