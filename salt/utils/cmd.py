# -*- coding: utf-8 -*-

import salt.modules.cmdmod as cmd

def run_quiet(cmd,
               cwd=None,
               stdin=None,
               runas=None,
               shell=DEFAULT_SHELL,
               python_shell=True,
               env=None,
               template=None,
               umask=None,
               timeout=None,
               reset_system_locale=True,
               saltenv='base'):
    '''
    Helper for running commands quietly for minion startup
    '''
    return cmd.run(cmd,
                runas=runas,
                cwd=cwd,
                stdin=stdin,
                stderr=subprocess.STDOUT,
                output_loglevel='quiet',
                shell=shell,
                python_shell=python_shell,
                env=env,
                template=template,
                umask=umask,
                timeout=timeout,
                reset_system_locale=reset_system_locale,
                saltenv=saltenv)['stdout']


def run_all_quiet(cmd,
                   cwd=None,
                   stdin=None,
                   runas=None,
                   shell=DEFAULT_SHELL,
                   python_shell=True,
                   env=None,
                   template=None,
                   umask=None,
                   timeout=None,
                   reset_system_locale=True,
                   saltenv='base'):
    '''
    Helper for running commands quietly for minion startup.
    Returns a dict of return data
    '''
    return cmd.run(cmd,
                runas=runas,
                cwd=cwd,
                stdin=stdin,
                shell=shell,
                python_shell=python_shell,
                env=env,
                output_loglevel='quiet',
                template=template,
                umask=umask,
                timeout=timeout,
                reset_system_locale=reset_system_locale,
                saltenv=saltenv)

def retcode_quiet(cmd,
                   cwd=None,
                   stdin=None,
                   runas=None,
                   shell=DEFAULT_SHELL,
                   python_shell=True,
                   env=None,
                   clean_env=False,
                   template=None,
                   umask=None,
                   output_loglevel='quiet',
                   quiet=True,
                   timeout=None,
                   reset_system_locale=True,
                   ignore_retcode=False,
                   saltenv='base',
                   use_vt=False,
                   **kwargs):
    '''
    Helper for running commands quietly for minion startup.
    Returns same as retcode
    '''
    return retcode(cmd,
                   cwd=cwd,
                   stdin=stdin,
                   runas=runas,
                   shell=shell,
                   python_shell=python_shell,
                   env=env,
                   clean_env=clean_env,
                   template=template,
                   umask=umask,
                   output_loglevel=output_loglevel,
                   timeout=timeout,
                   reset_system_locale=reset_system_locale,
                   ignore_retcode=ignore_retcode,
                   saltenv=saltenv,
                   use_vt=use_vt,
                   **kwargs)
