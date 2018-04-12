# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import time

# Import Salt libs
import salt.utils.decorators
from tests.support.paths import BASE_FILES

EXIT_CODE_SH = os.path.join(BASE_FILES, 'exit_code.sh')


def _exit_code(code):
    return '/usr/bin/env sh {0} {1}'.format(EXIT_CODE_SH, code)


def _fallbackfunc():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return False, 'fallback'


def working_function():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True


@salt.utils.decorators.depends(True)
def booldependsTrue():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True


@salt.utils.decorators.depends(False)
def booldependsFalse():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True


@salt.utils.decorators.depends('time')
def depends():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    ret = {'ret': True,
           'time': time.time()}
    return ret


@salt.utils.decorators.depends('time123')
def missing_depends():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True


@salt.utils.decorators.depends('time', fallback_function=_fallbackfunc)
def depends_will_not_fallback():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    ret = {'ret': True,
           'time': time.time()}
    return ret


@salt.utils.decorators.depends('time123', fallback_function=_fallbackfunc)
def missing_depends_will_fallback():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    ret = {'ret': True,
           'time': time.time()}
    return ret


@salt.utils.decorators.depends(_exit_code(42), retcode=42)
def command_success_retcode():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True


@salt.utils.decorators.depends(_exit_code(42), retcode=0)
def command_failure_retcode():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True


@salt.utils.decorators.depends(_exit_code(42), nonzero_retcode=True)
def command_success_nonzero_retcode_true():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True


@salt.utils.decorators.depends(_exit_code(0), nonzero_retcode=True)
def command_failure_nonzero_retcode_true():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True


@salt.utils.decorators.depends(_exit_code(0), nonzero_retcode=False)
def command_success_nonzero_retcode_false():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True


@salt.utils.decorators.depends(_exit_code(42), nonzero_retcode=False)
def command_failure_nonzero_retcode_false():
    '''
    CLI Example:

    .. code-block:: bash
    '''
    return True
