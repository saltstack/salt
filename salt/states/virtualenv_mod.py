# -*- coding: utf-8 -*-
'''
Setup of Python virtualenv sandboxes.
=====================================

'''

# Import python libs
import logging
import os
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    return 'virtualenv'


def managed(name,
            venv_bin='virtualenv',
            requirements=None,
            no_site_packages=None,
            system_site_packages=False,
            distribute=False,
            use_wheel=False,
            clear=False,
            python=None,
            extra_search_dir=None,
            never_download=None,
            prompt=None,
            __env__='base',
            user=None,
            runas=None,
            no_chown=False,
            cwd=None,
            index_url=None,
            extra_index_url=None,
            pre_releases=False):
    '''
    Create a virtualenv and optionally manage it with pip

    name
        Path to the virtualenv
    requirements
        Path to a pip requirements file. If the path begins with ``salt://``
        the file will be transferred from the master file server.
    cwd
        Path to the working directory where "pip install" is executed.
    use_wheel : False
        Prefer wheel archives (requires pip>=1.4)

    Also accepts any kwargs that the virtualenv module will.

    .. code-block:: yaml

        /var/www/myvirtualenv.com:
          virtualenv.managed:
            - system_site_packages: False
            - requirements: salt://REQUIREMENTS.txt
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not 'virtualenv.create' in __salt__:
        ret['result'] = False
        ret['comment'] = 'Virtualenv was not detected on this system'
        return ret

    salt.utils.warn_until(
        (0, 18),
        'Let\'s support \'runas\' until salt 0.19.0 is out, after which '
        'it will stop being supported',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    if salt.utils.is_windows():
        venv_py = os.path.join(name, 'Scripts', 'python.exe')
    else:
        venv_py = os.path.join(name, 'bin', 'python')
    venv_exists = os.path.exists(venv_py)

    # Bail out early if the specified requirements file can't be found
    if requirements and requirements.startswith('salt://'):
        cached_requirements = __salt__['cp.is_cached'](requirements, __env__)
        if not cached_requirements:
            # It's not cached, let's cache it.
            cached_requirements = __salt__['cp.cache_file'](
                requirements, __env__
            )
        # Check if the master version has changed.
        if __salt__['cp.hash_file'](requirements, __env__) != \
                __salt__['cp.hash_file'](cached_requirements, __env__):
            cached_requirements = __salt__['cp.cache_file'](
                requirements, __env__
            )
        if not cached_requirements:
            ret.update({
                'result': False,
                'comment': 'pip requirements file {0!r} not found'.format(
                    requirements
                )
            })
            return ret
        requirements = cached_requirements

    # If it already exists, grab the version for posterity
    if venv_exists and clear:
        ret['changes']['cleared_packages'] = \
            __salt__['pip.freeze'](bin_env=name)
        ret['changes']['old'] = \
            __salt__['cmd.run_stderr']('{0} -V'.format(venv_py)).strip('\n')

    # Create (or clear) the virtualenv
    if __opts__['test']:
        if venv_exists and clear:
            ret['result'] = None
            ret['comment'] = 'Virtualenv {0} is set to be cleared'.format(name)
            return ret
        if venv_exists and not clear:
            #ret['result'] = None
            ret['comment'] = 'Virtualenv {0} is already created'.format(name)
            return ret
        ret['result'] = None
        ret['comment'] = 'Virtualenv {0} is set to be created'.format(name)
        return ret

    if not venv_exists or (venv_exists and clear):
        _ret = __salt__['virtualenv.create'](
            name,
            venv_bin=venv_bin,
            no_site_packages=no_site_packages,
            system_site_packages=system_site_packages,
            distribute=distribute,
            clear=clear,
            python=python,
            extra_search_dir=extra_search_dir,
            never_download=never_download,
            prompt=prompt,
            runas=user
        )

        ret['result'] = _ret['retcode'] == 0
        ret['changes']['new'] = __salt__['cmd.run_stderr'](
            '{0} -V'.format(venv_py)).strip('\n')

        if clear:
            ret['comment'] = 'Cleared existing virtualenv'
        else:
            ret['comment'] = 'Created new virtualenv'

    elif venv_exists:
        ret['comment'] = 'virtualenv exists'

    if use_wheel:
        min_version = '1.4'
        cur_version = __salt__['pip.version'](bin_env=name)
        if not salt.utils.compare_versions(ver1=cur_version, oper='>=',
                                           ver2=min_version):
            ret['result'] = False
            ret['comment'] = ('The \'use_wheel\' option is only supported in '
                              'pip {0} and newer. The version of pip detected '
                              'was {1}.').format(min_version, cur_version)
            return ret


    # Populate the venv via a requirements file
    if requirements:
        before = set(__salt__['pip.freeze'](bin_env=name))
        _ret = __salt__['pip.install'](
            requirements=requirements,
            bin_env=name,
            use_wheel=use_wheel,
            runas=user,
            cwd=cwd,
            index_url=index_url,
            extra_index_url=extra_index_url,
            no_chown=no_chown,
            __env__=__env__,
            pre_releases=pre_releases
        )
        ret['result'] &= _ret['retcode'] == 0
        if _ret['retcode'] > 0:
            ret['comment'] = '{0}\n{1}\n{2}'.format(ret['comment'],
                                                    _ret['stdout'],
                                                    _ret['stderr'])

        after = set(__salt__['pip.freeze'](bin_env=name))

        new = list(after - before)
        old = list(before - after)

        if new or old:
            ret['changes']['packages'] = {
                'new': new if new else '',
                'old': old if old else ''}
    return ret

manage = managed  # pylint: disable=C0103
