'''
Setup of Python virtualenv sandboxes.
=====================================

'''
import logging
import os

logger = logging.getLogger(__name__)


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
        cwd=None):
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

    .. code-block: yaml

        /var/www/myvirtualenv.com:
          virtualenv.manage:
            - no_site_packages: True
            - requirements: salt://REQUIREMENTS.txt
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if not 'virtualenv.create' in __salt__:
        ret['result'] = False
        ret['comment'] = 'Virtualenv was not detected on this system'
        return ret

    venv_py = os.path.join(name, 'bin', 'python')
    venv_exists = os.path.exists(venv_py)

    # Bail out early if the specified requirements file can't be found
    if requirements:
        reqs_hash = __salt__['cp.hash_file'](requirements, __env__)

        if not reqs_hash:
            ret.update({
                'result': False,
                'comment': "pip requirements file '{0}' not found".format(
                    requirements)})

            return ret

    # If it already exists, grab the version for posterity
    if venv_exists and clear:
        ret['changes']['cleared_packages'] = \
            __salt__['pip.freeze'](bin_env=name)
        ret['changes']['old'] = \
            __salt__['cmd.run_stderr']('{0} -V'.format(venv_py)).strip('\n')

    # Create (or clear) the virtualenv
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Virtualenv {0} is set to be created or cleared'
        return ret

    if not venv_exists or (venv_exists and clear):
        __salt__['virtualenv.create'](name,
                venv_bin=venv_bin,
                no_site_packages=no_site_packages,
                system_site_packages=system_site_packages,
                distribute=distribute,
                clear=clear,
                python=python,
                extra_search_dir=extra_search_dir,
                never_download=never_download,
                prompt=prompt,
                runas=runas)

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
        if requirements.startswith('salt://'):
            requirements = __salt__['cp.cache_file'](requirements, __env__)
        before = set(__salt__['pip.freeze'](bin_env=name))
        __salt__['pip.install'](
            requirements=requirements, bin_env=name, runas=runas, cwd=cwd
        )
        after = set(__salt__['pip.freeze'](bin_env=name))

        new = list(after - before)
        old = list(before - after)

        if new or old:
            ret['changes']['packages'] = {
                'new': new if new else '',
                'old': old if old else ''}
    ret['result'] = True
    return ret

manage = managed
