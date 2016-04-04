# -*- coding: utf-8 -*-
'''
Management of APT/YUM package repos
===================================

Package repositories for APT-based and YUM-based distros can be managed with
these states. Here is some example SLS:

.. code-block:: yaml

    base:
      pkgrepo.managed:
        - humanname: CentOS-$releasever - Base
        - mirrorlist: http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=os
        - comments:
            - '#http://mirror.centos.org/centos/$releasever/os/$basearch/'
        - gpgcheck: 1
        - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-6

.. code-block:: yaml

    base:
      pkgrepo.managed:
        - humanname: Logstash PPA
        - name: deb http://ppa.launchpad.net/wolfnet/logstash/ubuntu precise main
        - dist: precise
        - file: /etc/apt/sources.list.d/logstash.list
        - keyid: 28B04E4A
        - keyserver: keyserver.ubuntu.com
        - require_in:
          - pkg: logstash

      pkg.latest:
        - name: logstash
        - refresh: True

.. code-block:: yaml

    base:
      pkgrepo.managed:
        - humanname: deb-multimedia
        - name: deb http://www.deb-multimedia.org stable main
        - file: /etc/apt/sources.list.d/deb-multimedia.list
        - key_url: salt://deb-multimedia/files/marillat.pub

.. code-block:: yaml

    base:
      pkgrepo.managed:
        - humanname: Google Chrome
        - name: deb http://dl.google.com/linux/chrome/deb/ stable main
        - dist: stable
        - file: /etc/apt/sources.list.d/chrome-browser.list
        - require_in:
          - pkg: google-chrome-stable
        - gpgcheck: 1
        - key_url: https://dl-ssl.google.com/linux/linux_signing_key.pub

.. code-block:: yaml

    base:
      pkgrepo.managed:
        - ppa: wolfnet/logstash
      pkg.latest:
        - name: logstash
        - refresh: True


.. _bug: https://bugs.launchpad.net/ubuntu/+source/software-properties/+bug/1249080

.. note::

    On Ubuntu systems, the ``python-software-properties`` package should be
    installed for better support of PPA repositories. To check if this package
    is installed, run ``dpkg -l python-software-properties``.

    Also, some Ubuntu releases have a bug_ in their
    ``python-software-properties`` package, a missing dependency on pycurl, so
    ``python-pycurl`` will need to be manually installed if it is not present
    once ``python-software-properties`` is installed.

    On Ubuntu & Debian systems, the ```python-apt`` package is required to be installed.
    To check if this package is installed, run ``dpkg -l python-software-properties``.
    ``python-apt`` will need to be manually installed if it is not present.

'''
from __future__ import absolute_import

# Import salt libs
import salt.utils

from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.modules.aptpkg import _strip_uri
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS


def __virtual__():
    '''
    Only load if modifying repos is available for this package type
    '''
    return 'pkg.mod_repo' in __salt__


def managed(name, **kwargs):
    '''
    This function manages the configuration on a system that points to the
    repositories for the system's package manager.

    name
        The name of the package repo, as it would be referred to when running
        the regular package manager commands.

    For yum-based systems, take note of the following configuration values:

    humanname
        On yum-based systems, this is stored as the "name" value in the .repo
        file in /etc/yum.repos.d/. On yum-based systems, this is required.

    baseurl
        On yum-based systems, baseurl refers to a direct URL to be used for
        this yum repo.
        One of baseurl or mirrorlist is required.

    mirrorlist
        a URL which contains a collection of baseurls to choose from. On
        yum-based systems.
        One of baseurl or mirrorlist is required.

    comments
        Sometimes you want to supply additional information, but not as
        enabled configuration. Anything supplied for this list will be saved
        in the repo configuration with a comment marker (#) in front.

    Additional configuration values, such as gpgkey or gpgcheck, are used
    verbatim to update the options for the yum repo in question.


    For apt-based systems, take note of the following configuration values:

    ppa
        On Ubuntu, you can take advantage of Personal Package Archives on
        Launchpad simply by specifying the user and archive name. The keyid
        will be queried from launchpad and everything else is set
        automatically. You can override any of the below settings by simply
        setting them as you would normally. For example:

        .. code-block:: yaml

            logstash-ppa:
              pkgrepo.managed:
                - ppa: wolfnet/logstash

    ppa_auth
        For Ubuntu PPAs there can be private PPAs that require authentication
        to access. For these PPAs the username/password can be passed as an
        HTTP Basic style username/password combination.

        .. code-block:: yaml

            logstash-ppa:
              pkgrepo.managed:
                - ppa: wolfnet/logstash
                - ppa_auth: username:password

    name
        On apt-based systems this must be the complete entry as it would be
        seen in the sources.list file.  This can have a limited subset of
        components (i.e. 'main') which can be added/modified with the
        "comps" option.

        .. code-block:: yaml

            precise-repo:
              pkgrepo.managed:
                - name: deb http://us.archive.ubuntu.com/ubuntu precise main

    disabled
        Toggles whether or not the repo is used for resolving dependencies
        and/or installing packages.

    comps
        On apt-based systems, comps dictate the types of packages to be
        installed from the repository (e.g. main, nonfree, ...).  For
        purposes of this, comps should be a comma-separated list.

    file
       The filename for the .list that the repository is configured in.
       It is important to include the full-path AND make sure it is in
       a directory that APT will look in when handling packages

    dist
       This dictates the release of the distro the packages should be built
       for.  (e.g. unstable). This option is rarely needed.

    keyid
       The KeyID of the GPG key to install. This option also requires
       the ``keyserver`` option to be set.

    keyserver
       This is the name of the keyserver to retrieve gpg keys from.  The
       ``keyid`` option must also be set for this option to work.

    key_url
       URL to retrieve a GPG key from. Allows the usage of ``http://``,
       ``https://`` as well as ``salt://``.

       .. note::

           Use either ``keyid``/``keyserver`` or ``key_url``, but not both.

    consolidate
       If set to true, this will consolidate all sources definitions to
       the sources.list file, cleanup the now unused files, consolidate
       components (e.g. main) for the same URI, type, and architecture
       to a single line, and finally remove comments from the sources.list
       file.  The consolidate will run every time the state is processed. The
       option only needs to be set on one repo managed by salt to take effect.

    clean_file
       If set to true, empty file before config repo, dangerous if use
       multiple sources in one file.

       .. versionadded:: 2015.8.0

    refresh_db
       If set to false this will skip refreshing the apt package database on
       debian based systems.

    require_in
       Set this to a list of pkg.installed or pkg.latest to trigger the
       running of apt-get update prior to attempting to install these
       packages. Setting a require in the pkg will not work for this.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    repo = {}

    # pkg.mod_repo has conflicting kwargs, so move 'em around

    if 'name' in kwargs:
        if 'ppa' in kwargs:
            ret['result'] = False
            ret['comment'] = 'You may not use both the "name" argument ' \
                             'and the "ppa" argument.'
            return ret
        kwargs['repo'] = kwargs['name']

    if 'key_url' in kwargs and ('keyid' in kwargs or 'keyserver' in kwargs):
        ret['result'] = False
        ret['comment'] = 'You may not use both "keyid"/"keyserver" and ' \
                         '"key_url" argument.'
        return ret

    if 'ppa' in kwargs and __grains__['os'] in ('Ubuntu', 'Mint'):
        # overload the name/repo value for PPAs cleanly
        # this allows us to have one code-path for PPAs
        repo_name = 'ppa:{0}'.format(kwargs['ppa'])
        kwargs['repo'] = repo_name
    if 'repo' not in kwargs:
        kwargs['repo'] = name

    if 'humanname' in kwargs:
        kwargs['name'] = kwargs['humanname']
        kwargs.pop('humanname')

    if kwargs.pop('enabled', None):
        kwargs['disabled'] = False
        salt.utils.warn_until(
            'Carbon',
            'The `enabled` argument has been deprecated in favor of '
            '`disabled`.'
        )

    for kwarg in _STATE_INTERNAL_KEYWORDS:
        kwargs.pop(kwarg, None)

    try:
        repo = __salt__['pkg.get_repo'](
                kwargs['repo'],
                ppa_auth=kwargs.get('ppa_auth', None)
        )
    except CommandExecutionError as exc:
        ret['result'] = False
        ret['comment'] = \
            'Failed to configure repo {0!r}: {1}'.format(name, exc)
        return ret

    # this is because of how apt-sources works.  This pushes distro logic
    # out of the state itself and into a module that it makes more sense
    # to use.  Most package providers will simply return the data provided
    # it doesn't require any "specialized" data massaging.
    if 'pkg.expand_repo_def' in __salt__:
        sanitizedkwargs = __salt__['pkg.expand_repo_def'](kwargs)
    else:
        sanitizedkwargs = kwargs
    if __grains__['os_family'] == 'Debian':
        kwargs['repo'] = _strip_uri(kwargs['repo'])

    if repo:
        notset = False
        for kwarg in sanitizedkwargs:
            if kwarg == 'repo':
                pass
            elif kwarg not in repo:
                notset = True
            elif kwarg == 'comps':
                if sorted(sanitizedkwargs[kwarg]) != sorted(repo[kwarg]):
                    notset = True
            elif kwarg == 'line' and __grains__['os_family'] == 'Debian':
                # split the line and sort everything after the URL
                sanitizedsplit = sanitizedkwargs[kwarg].split()
                sanitizedsplit[3:] = sorted(sanitizedsplit[3:])
                reposplit = repo[kwarg].split()
                reposplit[3:] = sorted(reposplit[3:])
                if sanitizedsplit != reposplit:
                    notset = True
            else:
                if str(sanitizedkwargs[kwarg]) != str(repo[kwarg]):
                    notset = True
        if notset is False:
            ret['result'] = True
            ret['comment'] = ('Package repo {0!r} already configured'
                              .format(name))
            return ret

    if __opts__['test']:
        ret['comment'] = ('Package repo {0!r} will be configured. This may '
                          'cause pkg states to behave differently than stated '
                          'if this action is repeated without test=True, due '
                          'to the differences in the configured repositories.'
                          .format(name))
        return ret

    # empty file before configure
    if kwargs.get('clean_file', False):
        salt.utils.fopen(kwargs['file'], 'w').close()

    try:
        if __grains__['os_family'] == 'Debian':
            __salt__['pkg.mod_repo'](saltenv=__env__, **kwargs)
        else:
            __salt__['pkg.mod_repo'](**kwargs)
    except Exception as exc:
        # This is another way to pass information back from the mod_repo
        # function.
        ret['result'] = False
        ret['comment'] = \
            'Failed to configure repo {0!r}: {1}'.format(name, exc)
        return ret

    try:
        repodict = __salt__['pkg.get_repo'](
            kwargs['repo'], ppa_auth=kwargs.get('ppa_auth', None)
        )
        if repo:
            for kwarg in sanitizedkwargs:
                if repodict.get(kwarg) != repo.get(kwarg):
                    change = {'new': repodict[kwarg],
                              'old': repo.get(kwarg)}
                    ret['changes'][kwarg] = change
        else:
            ret['changes'] = {'repo': kwargs['repo']}

        ret['result'] = True
        ret['comment'] = 'Configured package repo {0!r}'.format(name)
    except Exception as exc:
        ret['result'] = False
        ret['comment'] = \
            'Failed to confirm config of repo {0!r}: {1}'.format(name, exc)

    return ret


def absent(name, **kwargs):
    '''
    This function deletes the specified repo on the system, if it exists. It
    is essentially a wrapper around pkg.del_repo.

    name
        The name of the package repo, as it would be referred to when running
        the regular package manager commands.

    **UBUNTU-SPECIFIC OPTIONS**

    ppa
        On Ubuntu, you can take advantage of Personal Package Archives on
        Launchpad simply by specifying the user and archive name.

        .. code-block:: yaml

            logstash-ppa:
              pkgrepo.absent:
                - ppa: wolfnet/logstash

    ppa_auth
        For Ubuntu PPAs there can be private PPAs that require authentication
        to access. For these PPAs the username/password can be specified.  This
        is required for matching if the name format uses the ``ppa:`` specifier
        and is private (requires username/password to access, which is encoded
        in the URI).

        .. code-block:: yaml

            logstash-ppa:
              pkgrepo.absent:
                - ppa: wolfnet/logstash
                - ppa_auth: username:password

    keyid
        If passed, then the GPG key corresponding to the passed KeyID will also
        be removed.

    keyid_ppa : False
        If set to ``True``, the GPG key's ID will be looked up from
        ppa.launchpad.net and removed, and the ``keyid`` argument will be
        ignored.

        .. note::
            This option will be disregarded unless the ``ppa`` argument is
            present.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    repo = {}
    if 'ppa' in kwargs and __grains__['os'] in ('Ubuntu', 'Mint'):
        name = kwargs.pop('ppa')
        if not name.startswith('ppa:'):
            name = 'ppa:' + name

    remove_key = any(kwargs.get(x) is not None
                     for x in ('keyid', 'keyid_ppa'))
    if remove_key and 'pkg.del_repo_key' not in __salt__:
        ret['result'] = False
        ret['comment'] = \
            'Repo key management is not implemented for this platform'
        return ret

    try:
        repo = __salt__['pkg.get_repo'](
            name, ppa_auth=kwargs.get('ppa_auth', None)
        )
    except CommandExecutionError as exc:
        ret['result'] = False
        ret['comment'] = \
            'Failed to configure repo {0!r}: {1}'.format(name, exc)
        return ret

    if not repo:
        ret['comment'] = 'Package repo {0} is absent'.format(name)
        ret['result'] = True
        return ret

    if __opts__['test']:
        ret['comment'] = ('Package repo {0!r} will be removed. This may '
                          'cause pkg states to behave differently than stated '
                          'if this action is repeated without test=True, due '
                          'to the differences in the configured repositories.'
                          .format(name))
        return ret

    try:
        __salt__['pkg.del_repo'](repo=name, **kwargs)
    except (CommandExecutionError, SaltInvocationError) as exc:
        ret['result'] = False
        ret['comment'] = exc.strerror
        return ret

    repos = __salt__['pkg.list_repos']()
    if name not in repos:
        ret['changes']['repo'] = name
        ret['comment'] = 'Removed repo {0}'.format(name)

        if not remove_key:
            ret['result'] = True
        else:
            try:
                removed_keyid = __salt__['pkg.del_repo_key'](name, **kwargs)
            except (CommandExecutionError, SaltInvocationError) as exc:
                ret['result'] = False
                ret['comment'] += ', but failed to remove key: {0}'.format(exc)
            else:
                ret['result'] = True
                ret['changes']['keyid'] = removed_keyid
                ret['comment'] += ', and keyid {0}'.format(removed_keyid)
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to remove repo {0}'.format(name)

    return ret
