'''
Setup of Python virtualenv sandboxes.
=====================================

'''

# Import python libs
import logging
import os
import salt.utils

log = logging.getLogger(__name__)


def managed(name,
            venv_bin='virtualenv',
            requirements='',
            no_site_packages=False,
            system_site_packages=False,
            distribute=False,
            clear=False,
            python='',
            extra_search_dir='',
            never_download=False,
            prompt='',
            __env__='base',
            runas=None,
            no_chown=False,
            cwd=None,
            index_url=None,
            extra_index_url=None):
    '''
    Create a virtualenv and optionally manage it with pip

    name
        Path to the virtualenv
    requirements
        Path to a pip requirements file. If the path begins with ``salt://``
        the file will be transfered from the master file server.
    cwd
        Path to the working directory where "pip install" is executed.

    Also accepts any kwargs that the virtualenv module will.

    .. code-block:: yaml

        /var/www/myvirtualenv.com:
          virtualenv.managed:
            - no_site_packages: True
            - requirements: salt://REQUIREMENTS.txt
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not 'virtualenv.create' in __salt__:
        ret['result'] = False
        ret['comment'] = 'Virtualenv was not detected on this system'
        return ret

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
                'comment': "pip requirements file '{0}' not found".format(
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
            runas=runas
        )

        ret['result'] = _ret['retcode'] == 0
        ret['changes']['new'] = __salt__['cmd.run_stderr'](
            '{0} -V'.format(venv_py)).strip('\n')

        if clear:
            ret['comment'] = "Cleared existing virtualenv"
        else:
            ret['comment'] = "Created new virtualenv"

    elif venv_exists:
        ret['comment'] = "virtualenv exists"

    # Populate the venv via a requirements file
    if requirements:
        before = set(__salt__['pip.freeze'](bin_env=name))
        _ret = __salt__['pip.install'](
            requirements=requirements, bin_env=name, runas=runas, cwd=cwd,
            index_url=index_url,
            extra_index_url=extra_index_url,
            no_chown=no_chown,
            __env__=__env__
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
