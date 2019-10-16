# -*- coding: utf-8 -*-
'''
Management of zc.buildout

.. versionadded:: 2014.1.0

.. _`minitage's buildout maker`: https://github.com/minitage/minitage/blob/master/src/minitage/core/makers/buildout.py

This module is inspired by `minitage's buildout maker`_

.. note::

    The zc.buildout integration is still in beta; the API is subject to change

General notes
-------------

You have those following methods:

* upgrade_bootstrap
* bootstrap
* run_buildout
* buildout
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import re
import logging
import sys
import traceback
import copy

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import range
from salt.ext.six.moves.urllib.request import urlopen as _urlopen
# pylint: enable=import-error,no-name-in-module,redefined-builtin

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError


INVALID_RESPONSE = 'We did not get any expectable answer from buildout'
VALID_RESPONSE = ''
NOTSET = object()
HR = '{0}\n'.format('-' * 80)
RE_F = re.S | re.M | re.U
BASE_STATUS = {
    'status': None,
    'logs': [],
    'comment': '',
    'out': None,
    'logs_by_level': {},
    'outlog': None,
    'outlog_by_level': None,
}
_URL_VERSIONS = {
    1: 'http://downloads.buildout.org/1/bootstrap.py',
    2: 'http://downloads.buildout.org/2/bootstrap.py',
}
DEFAULT_VER = 2
_logger = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'buildout'


def __virtual__():
    '''
    Only load if buildout libs are present
    '''
    return __virtualname__


def _salt_callback(func, **kwargs):
    LOG.clear()

    def _call_callback(*a, **kw):
        # cleanup the module kwargs before calling it from the
        # decorator
        kw = copy.deepcopy(kw)
        for k in [ar for ar in kw if '__pub' in ar]:
            kw.pop(k, None)
        st = BASE_STATUS.copy()
        directory = kw.get('directory', '.')
        onlyif = kw.get('onlyif', None)
        unless = kw.get('unless', None)
        runas = kw.get('runas', None)
        env = kw.get('env', ())
        status = BASE_STATUS.copy()
        try:
            # may rise _ResultTransmission
            status = _check_onlyif_unless(onlyif,
                                          unless,
                                          directory=directory,
                                          runas=runas,
                                          env=env)
            # if onlyif/unless returns, we are done
            if status is None:
                status = BASE_STATUS.copy()
                comment, st = '', True
                out = func(*a, **kw)
                # we may have already final statuses not to be touched
                # merged_statuses flag is there to check that !
                if not isinstance(out, dict):
                    status = _valid(status, out=out)
                else:
                    if out.get('merged_statuses', False):
                        status = out
                    else:
                        status = _set_status(status,
                                             status=out.get('status', True),
                                             comment=out.get('comment', ''),
                                             out=out.get('out', out))
        except Exception:
            trace = traceback.format_exc(None)
            LOG.error(trace)
            _invalid(status)
        LOG.clear()
        # before returning, trying to compact the log output
        for k in ['comment', 'out', 'outlog']:
            if status[k] and isinstance(status[k], six.string_types):
                status[k] = '\n'.join([
                    log
                    for log in status[k].split('\n')
                    if log.strip()])
        return status
    _call_callback.__doc__ = func.__doc__
    return _call_callback


class _Logger(object):
    levels = ('info', 'warn', 'debug', 'error')

    def __init__(self):
        self._msgs = []
        self._by_level = {}

    def _log(self, level, msg):
        if not isinstance(msg, six.text_type):
            msg = msg.decode('utf-8')
        if level not in self._by_level:
            self._by_level[level] = []
        self._msgs.append((level, msg))
        self._by_level[level].append(msg)

    def debug(self, msg):
        self._log('debug', msg)

    def info(self, msg):
        self._log('info', msg)

    def error(self, msg):
        self._log('error', msg)

    def warn(self, msg):
        self._log('warn', msg)

    warning = warn

    def clear(self):
        for i in self._by_level:
            self._by_level[i] = []
        for i in range(len(self._msgs)):
            self._msgs.pop()

    def get_logs(self, level):
        return self._by_level.get(level, [])

    @property
    def messages(self):
        return self._msgs

    @property
    def by_level(self):
        return self._by_level


LOG = _Logger()


def _encode_status(status):
    if status['out'] is None:
        status['out'] = None
    else:
        status['out'] = salt.utils.stringutils.to_unicode(status['out'])
    status['outlog_by_level'] = salt.utils.stringutils.to_unicode(status['outlog_by_level'])
    if status['logs']:
        for i, data in enumerate(status['logs'][:]):
            status['logs'][i] = (data[0], salt.utils.stringutils.to_unicode(data[1]))
        for logger in 'error', 'warn', 'info', 'debug':
            logs = status['logs_by_level'].get(logger, [])[:]
            if logs:
                for i, log in enumerate(logs):
                    status['logs_by_level'][logger][i] = salt.utils.stringutils.to_unicode(log)
    return status


def _set_status(m,
                comment=INVALID_RESPONSE,
                status=False,
                out=None):
    '''
    Assign status data to a dict.
    '''
    m['out'] = out
    m['status'] = status
    m['logs'] = LOG.messages[:]
    m['logs_by_level'] = LOG.by_level.copy()
    outlog, outlog_by_level = '', ''
    m['comment'] = comment
    if out and isinstance(out, six.string_types):
        outlog += HR
        outlog += 'OUTPUT:\n'
        outlog += '{0}\n'.format(salt.utils.stringutils.to_unicode(out))
        outlog += HR
    if m['logs']:
        outlog += HR
        outlog += 'Log summary:\n'
        outlog += HR
        outlog_by_level += HR
        outlog_by_level += 'Log summary by level:\n'
        outlog_by_level += HR
        for level, msg in m['logs']:
            outlog += '\n{0}: {1}\n'.format(level.upper(),
                                            salt.utils.stringutils.to_unicode(msg))
        for logger in 'error', 'warn', 'info', 'debug':
            logs = m['logs_by_level'].get(logger, [])
            if logs:
                outlog_by_level += '\n{0}:\n'.format(logger.upper())
                for idx, log in enumerate(logs[:]):
                    logs[idx] = salt.utils.stringutils.to_unicode(log)
                outlog_by_level += '\n'.join(logs)
                outlog_by_level += '\n'
        outlog += HR
    m['outlog'] = outlog
    m['outlog_by_level'] = outlog_by_level
    return _encode_status(m)


def _invalid(m, comment=INVALID_RESPONSE, out=None):
    '''
    Return invalid status.
    '''
    return _set_status(m, status=False, comment=comment, out=out)


def _valid(m, comment=VALID_RESPONSE, out=None):
    '''
    Return valid status.
    '''
    return _set_status(m, status=True, comment=comment, out=out)


def _Popen(command,
           output=False,
           directory='.',
           runas=None,
           env=(),
           exitcode=0,
           use_vt=False,
           loglevel=None):
    '''
    Run a command.

    output
        return output if true

    directory
        directory to execute in

    runas
        user used to run buildout as

    env
        environment variables to set when running

    exitcode
        fails if cmd does not return this exit code
        (set to None to disable check)

    use_vt
        Use the new salt VT to stream output [experimental]

    '''
    ret = None
    directory = os.path.abspath(directory)
    if isinstance(command, list):
        command = ' '.join(command)
    LOG.debug('Running {0}'.format(command))  # pylint: disable=str-format-in-logging
    if not loglevel:
        loglevel = 'debug'
    ret = __salt__['cmd.run_all'](
        command, cwd=directory, output_loglevel=loglevel,
        runas=runas, env=env, use_vt=use_vt, python_shell=False)
    out = ret['stdout'] + '\n\n' + ret['stderr']
    if (exitcode is not None) and (ret['retcode'] != exitcode):
        raise _BuildoutError(out)
    ret['output'] = out
    if output:
        ret = out
    return ret


class _BuildoutError(CommandExecutionError):
    '''
    General Buildout Error.
    '''


def _has_old_distribute(python=sys.executable, runas=None, env=()):
    old_distribute = False
    try:
        cmd = [python,
               '-c',
               '\'import pkg_resources;'
               'print pkg_resources.'
               'get_distribution(\"distribute\").location\'']
        ret = _Popen(cmd, runas=runas, env=env, output=True)
        if 'distribute-0.6' in ret:
            old_distribute = True
    except Exception:
        old_distribute = False
    return old_distribute


def _has_setuptools7(python=sys.executable, runas=None, env=()):
    new_st = False
    try:
        cmd = [python,
               '-c',
               '\'import pkg_resources;'
               'print not pkg_resources.'
               'get_distribution("setuptools").version.startswith("0.6")\'']
        ret = _Popen(cmd, runas=runas, env=env, output=True)
        if 'true' in ret.lower():
            new_st = True
    except Exception:
        new_st = False
    return new_st


def _find_cfgs(path, cfgs=None):
    '''
    Find all buildout configs in a subdirectory.
    only buildout.cfg and etc/buildout.cfg are valid in::

    path
        directory where to start to search

    cfg
        a optional list to append to

            .
            ├── buildout.cfg
            ├── etc
            │   └── buildout.cfg
            ├── foo
            │   └── buildout.cfg
            └── var
                └── buildout.cfg
    '''
    ignored = ['var', 'parts']
    dirs = []
    if not cfgs:
        cfgs = []
    for i in os.listdir(path):
        fi = os.path.join(path, i)
        if fi.endswith('.cfg') and os.path.isfile(fi):
            cfgs.append(fi)
        if os.path.isdir(fi) and (i not in ignored):
            dirs.append(fi)
    for fpath in dirs:
        for p, ids, ifs in salt.utils.path.os_walk(fpath):
            for i in ifs:
                if i.endswith('.cfg'):
                    cfgs.append(os.path.join(p, i))
    return cfgs


def _get_bootstrap_content(directory='.'):
    '''
    Get the current bootstrap.py script content
    '''
    try:
        with salt.utils.files.fopen(os.path.join(
                                os.path.abspath(directory),
                                'bootstrap.py')) as fic:
            oldcontent = salt.utils.stringutils.to_unicode(
                fic.read()
            )
    except (OSError, IOError):
        oldcontent = ''
    return oldcontent


def _get_buildout_ver(directory='.'):
    '''Check for buildout versions.

    In any cases, check for a version pinning
    Also check for buildout.dumppickedversions which is buildout1 specific
    Also check for the version targeted by the local bootstrap file
    Take as default buildout2

    directory
        directory to execute in
    '''
    directory = os.path.abspath(directory)
    buildoutver = 2
    try:
        files = _find_cfgs(directory)
        for f in files:
            with salt.utils.files.fopen(f) as fic:
                buildout1re = re.compile(r'^zc\.buildout\s*=\s*1', RE_F)
                dfic = salt.utils.stringutils.to_unicode(fic.read())
                if (
                        ('buildout.dumppick' in dfic)
                        or
                        (buildout1re.search(dfic))
                ):
                    buildoutver = 1
        bcontent = _get_bootstrap_content(directory)
        if (
            '--download-base' in bcontent
            or '--setup-source' in bcontent
            or '--distribute' in bcontent
        ):
            buildoutver = 1
    except (OSError, IOError):
        pass
    return buildoutver


def _get_bootstrap_url(directory):
    '''
    Get the most appropriate download URL for the bootstrap script.

    directory
        directory to execute in

    '''
    v = _get_buildout_ver(directory)
    return _URL_VERSIONS.get(v, _URL_VERSIONS[DEFAULT_VER])


def _dot_buildout(directory):
    '''
    Get the local marker directory.

    directory
        directory to execute in
    '''
    return os.path.join(
        os.path.abspath(directory), '.buildout')


@_salt_callback
def upgrade_bootstrap(directory='.',
                      onlyif=None,
                      unless=None,
                      runas=None,
                      env=(),
                      offline=False,
                      buildout_ver=None):
    '''
    Upgrade current bootstrap.py with the last released one.

    Indeed, when we first run a buildout, a common source of problem
    is to have a locally stale bootstrap, we just try to grab a new copy

    directory
        directory to execute in

    offline
        are we executing buildout in offline mode

    buildout_ver
        forcing to use a specific buildout version (1 | 2)

    onlyif
        Only execute cmd if statement on the host return 0

    unless
        Do not execute cmd if statement on the host return 0

    CLI Example:

    .. code-block:: bash

        salt '*' buildout.upgrade_bootstrap /srv/mybuildout
    '''
    if buildout_ver:
        booturl = _URL_VERSIONS[buildout_ver]
    else:
        buildout_ver = _get_buildout_ver(directory)
        booturl = _get_bootstrap_url(directory)
    LOG.debug('Using {0}'.format(booturl))  # pylint: disable=str-format-in-logging
    # try to download an up-to-date bootstrap
    # set defaulttimeout
    # and add possible content
    directory = os.path.abspath(directory)
    b_py = os.path.join(directory, 'bootstrap.py')
    comment = ''
    try:
        oldcontent = _get_bootstrap_content(directory)
        dbuild = _dot_buildout(directory)
        data = oldcontent
        updated = False
        dled = False
        if not offline:
            try:
                if not os.path.isdir(dbuild):
                    os.makedirs(dbuild)
                # only try to download once per buildout checkout
                with salt.utils.files.fopen(os.path.join(
                        dbuild,
                        '{0}.updated_bootstrap'.format(buildout_ver))):
                    pass
            except (OSError, IOError):
                LOG.info('Bootstrap updated from repository')
                data = _urlopen(booturl).read()
                updated = True
                dled = True
        if 'socket.setdefaulttimeout' not in data:
            updated = True
            ldata = data.splitlines()
            ldata.insert(1, 'import socket;socket.setdefaulttimeout(2)')
            data = '\n'.join(ldata)
        if updated:
            comment = 'Bootstrap updated'
            with salt.utils.files.fopen(b_py, 'w') as fic:
                fic.write(salt.utils.stringutils.to_str(data))
        if dled:
            with salt.utils.files.fopen(os.path.join(dbuild,
                                               '{0}.updated_bootstrap'.format(
                                                   buildout_ver)), 'w') as afic:
                afic.write('foo')
    except (OSError, IOError):
        if oldcontent:
            with salt.utils.files.fopen(b_py, 'w') as fic:
                fic.write(salt.utils.stringutils.to_str(oldcontent))

    return {'comment': comment}


@_salt_callback
def bootstrap(directory='.',
              config='buildout.cfg',
              python=sys.executable,
              onlyif=None,
              unless=None,
              runas=None,
              env=(),
              distribute=None,
              buildout_ver=None,
              test_release=False,
              offline=False,
              new_st=None,
              use_vt=False,
              loglevel=None):
    '''
    Run the buildout bootstrap dance (python bootstrap.py).

    directory
        directory to execute in

    config
        alternative buildout configuration file to use

    runas
        User used to run buildout as

    env
        environment variables to set when running

    buildout_ver
        force a specific buildout version (1 | 2)

    test_release
        buildout accept test release

    offline
        are we executing buildout in offline mode

    distribute
        Forcing use of distribute

    new_st
        Forcing use of setuptools >= 0.7

    python
        path to a python executable to use in place of default (salt one)

    onlyif
        Only execute cmd if statement on the host return 0

    unless
        Do not execute cmd if statement on the host return 0

    use_vt
        Use the new salt VT to stream output [experimental]

    CLI Example:

    .. code-block:: bash

        salt '*' buildout.bootstrap /srv/mybuildout
    '''
    directory = os.path.abspath(directory)
    dbuild = _dot_buildout(directory)
    bootstrap_args = ''
    has_distribute = _has_old_distribute(python=python, runas=runas, env=env)
    has_new_st = _has_setuptools7(python=python, runas=runas, env=env)
    if (
        has_distribute and has_new_st
        and not distribute and new_st
    ):
        new_st = True
        distribute = False
    if (
        has_distribute and has_new_st
        and not distribute and new_st
    ):
        new_st = True
        distribute = False
    if (
        has_distribute and has_new_st
        and distribute and not new_st
    ):
        new_st = True
        distribute = False
    if (
        has_distribute and has_new_st
        and not distribute and not new_st
    ):
        new_st = True
        distribute = False

    if (
        not has_distribute and has_new_st
        and not distribute and new_st
    ):
        new_st = True
        distribute = False
    if (
        not has_distribute and has_new_st
        and not distribute and new_st
    ):
        new_st = True
        distribute = False
    if (
        not has_distribute and has_new_st
        and distribute and not new_st
    ):
        new_st = True
        distribute = False
    if (
        not has_distribute and has_new_st
        and not distribute and not new_st
    ):
        new_st = True
        distribute = False

    if (
        has_distribute and not has_new_st
        and not distribute and new_st
    ):
        new_st = True
        distribute = False
    if (
        has_distribute and not has_new_st
        and not distribute and new_st
    ):
        new_st = True
        distribute = False
    if (
        has_distribute and not has_new_st
        and distribute and not new_st
    ):
        new_st = False
        distribute = True
    if (
        has_distribute and not has_new_st
        and not distribute and not new_st
    ):
        new_st = False
        distribute = True

    if (
        not has_distribute and not has_new_st
        and not distribute and new_st
    ):
        new_st = True
        distribute = False
    if (
        not has_distribute and not has_new_st
        and not distribute and new_st
    ):
        new_st = True
        distribute = False
    if (
        not has_distribute and not has_new_st
        and distribute and not new_st
    ):
        new_st = False
        distribute = True
    if (
        not has_distribute and not has_new_st
        and not distribute and not new_st
    ):
        new_st = True
        distribute = False

    if new_st and distribute:
        distribute = False
    if new_st:
        distribute = False
        LOG.warning('Forcing to use setuptools as we have setuptools >= 0.7')
    if distribute:
        new_st = False
        if buildout_ver == 1:
            LOG.warning('Using distribute !')
            bootstrap_args += ' --distribute'
    if not os.path.isdir(dbuild):
        os.makedirs(dbuild)
    upgrade_bootstrap(directory,
                      offline=offline,
                      buildout_ver=buildout_ver)
    # be sure which buildout bootstrap we have
    b_py = os.path.join(directory, 'bootstrap.py')
    with salt.utils.files.fopen(b_py) as fic:
        content = salt.utils.stringutils.to_unicode(fic.read())
    if (
        (test_release is not False)
        and ' --accept-buildout-test-releases' in content
    ):
        bootstrap_args += ' --accept-buildout-test-releases'
    if config and '"-c"' in content:
        bootstrap_args += ' -c {0}'.format(config)
    # be sure that the bootstrap belongs to the running user
    try:
        if runas:
            uid = __salt__['user.info'](runas)['uid']
            gid = __salt__['user.info'](runas)['gid']
            os.chown('bootstrap.py', uid, gid)
    except (IOError, OSError) as exc:
        # don't block here, try to execute it if can pass
        _logger.error('BUILDOUT bootstrap permissions error:'
                      ' {0}'.format(exc),
                  exc_info=_logger.isEnabledFor(logging.DEBUG))
    cmd = '{0} bootstrap.py {1}'.format(python, bootstrap_args)
    ret = _Popen(cmd, directory=directory, runas=runas, loglevel=loglevel,
                 env=env, use_vt=use_vt)
    output = ret['output']
    return {'comment': cmd, 'out': output}


@_salt_callback
def run_buildout(directory='.',
                 config='buildout.cfg',
                 parts=None,
                 onlyif=None,
                 unless=None,
                 offline=False,
                 newest=True,
                 runas=None,
                 env=(),
                 verbose=False,
                 debug=False,
                 use_vt=False,
                 loglevel=None):
    '''
    Run a buildout in a directory.

    directory
        directory to execute in

    config
        alternative buildout configuration file to use

    offline
        are we executing buildout in offline mode

    runas
        user used to run buildout as

    env
        environment variables to set when running

    onlyif
        Only execute cmd if statement on the host return 0

    unless
        Do not execute cmd if statement on the host return 0

    newest
        run buildout in newest mode

    force
        run buildout unconditionally

    verbose
        run buildout in verbose mode (-vvvvv)

    use_vt
        Use the new salt VT to stream output [experimental]

    CLI Example:

    .. code-block:: bash

        salt '*' buildout.run_buildout /srv/mybuildout
    '''
    directory = os.path.abspath(directory)
    bcmd = os.path.join(directory, 'bin', 'buildout')
    installed_cfg = os.path.join(directory, '.installed.cfg')
    argv = []
    if verbose:
        LOG.debug('Buildout is running in verbose mode!')
        argv.append('-vvvvvvv')
    if not newest and os.path.exists(installed_cfg):
        LOG.debug('Buildout is running in non newest mode!')
        argv.append('-N')
    if newest:
        LOG.debug('Buildout is running in newest mode!')
        argv.append('-n')
    if offline:
        LOG.debug('Buildout is running in offline mode!')
        argv.append('-o')
    if debug:
        LOG.debug('Buildout is running in debug mode!')
        argv.append('-D')
    cmds, outputs = [], []
    if parts:
        for part in parts:
            LOG.info('Installing single part: {0}'.format(part))  # pylint: disable=str-format-in-logging
            cmd = '{0} -c {1} {2} install {3}'.format(
                bcmd, config, ' '.join(argv), part)
            cmds.append(cmd)
            outputs.append(
                _Popen(
                    cmd, directory=directory,
                    runas=runas,
                    env=env,
                    output=True,
                    loglevel=loglevel,
                    use_vt=use_vt)
            )
    else:
        LOG.info('Installing all buildout parts')
        cmd = '{0} -c {1} {2}'.format(
            bcmd, config, ' '.join(argv))
        cmds.append(cmd)
        outputs.append(
            _Popen(
                cmd, directory=directory, runas=runas, loglevel=loglevel,
                env=env, output=True, use_vt=use_vt)
        )

    return {'comment': '\n'.join(cmds),
            'out': '\n'.join(outputs)}


def _merge_statuses(statuses):
    status = BASE_STATUS.copy()
    status['status'] = None
    status['merged_statuses'] = True
    status['out'] = ''
    for st in statuses:
        if status['status'] is not False:
            status['status'] = st['status']
        out = st['out']
        comment = salt.utils.stringutils.to_unicode(st['comment'])
        logs = st['logs']
        logs_by_level = st['logs_by_level']
        outlog_by_level = st['outlog_by_level']
        outlog = st['outlog']
        if out:
            if not status['out']:
                status['out'] = ''
            status['out'] += '\n'
            status['out'] += HR
            out = salt.utils.stringutils.to_unicode(out)
            status['out'] += '{0}\n'.format(out)
            status['out'] += HR
        if comment:
            if not status['comment']:
                status['comment'] = ''
            status['comment'] += '\n{0}\n'.format(
                salt.utils.stringutils.to_unicode(comment))
        if outlog:
            if not status['outlog']:
                status['outlog'] = ''
            outlog = salt.utils.stringutils.to_unicode(outlog)
            status['outlog'] += '\n{0}'.format(HR)
            status['outlog'] += outlog
        if outlog_by_level:
            if not status['outlog_by_level']:
                status['outlog_by_level'] = ''
            status['outlog_by_level'] += '\n{0}'.format(HR)
            status['outlog_by_level'] += salt.utils.stringutils.to_unicode(outlog_by_level)
        status['logs'].extend([
            (a[0], salt.utils.stringutils.to_unicode(a[1])) for a in logs])
        for log in logs_by_level:
            if log not in status['logs_by_level']:
                status['logs_by_level'][log] = []
            status['logs_by_level'][log].extend(
                [salt.utils.stringutils.to_unicode(a) for a in logs_by_level[log]])
    return _encode_status(status)


@_salt_callback
def buildout(directory='.',
             config='buildout.cfg',
             parts=None,
             runas=None,
             env=(),
             buildout_ver=None,
             test_release=False,
             distribute=None,
             new_st=None,
             offline=False,
             newest=False,
             python=sys.executable,
             debug=False,
             verbose=False,
             onlyif=None,
             unless=None,
             use_vt=False,
             loglevel=None):
    '''
    Run buildout in a directory.

    directory
        directory to execute in

    config
        buildout config to use

    parts
        specific buildout parts to run

    runas
        user used to run buildout as

    env
        environment variables to set when running

    buildout_ver
        force a specific buildout version (1 | 2)

    test_release
        buildout accept test release

    new_st
        Forcing use of setuptools >= 0.7

    distribute
        use distribute over setuptools if possible

    offline
        does buildout run offline

    python
        python to use

    debug
        run buildout with -D debug flag

    onlyif
        Only execute cmd if statement on the host return 0

    unless
        Do not execute cmd if statement on the host return 0
    newest
        run buildout in newest mode

    verbose
        run buildout in verbose mode (-vvvvv)

    use_vt
        Use the new salt VT to stream output [experimental]

    CLI Example:

    .. code-block:: bash

        salt '*' buildout.buildout /srv/mybuildout
    '''
    LOG.info('Running buildout in {0} ({1})'.format(directory, config))  # pylint: disable=str-format-in-logging
    boot_ret = bootstrap(directory,
                         config=config,
                         buildout_ver=buildout_ver,
                         test_release=test_release,
                         offline=offline,
                         new_st=new_st,
                         env=env,
                         runas=runas,
                         distribute=distribute,
                         python=python,
                         use_vt=use_vt,
                         loglevel=loglevel)
    buildout_ret = run_buildout(directory=directory,
                                config=config,
                                parts=parts,
                                offline=offline,
                                newest=newest,
                                runas=runas,
                                env=env,
                                verbose=verbose,
                                debug=debug,
                                use_vt=use_vt,
                                loglevel=loglevel)
    # signal the decorator or our return
    return _merge_statuses([boot_ret, buildout_ret])


def _check_onlyif_unless(onlyif, unless, directory, runas=None, env=()):
    ret = None
    status = BASE_STATUS.copy()
    if os.path.exists(directory):
        directory = os.path.abspath(directory)
        status['status'] = False
        retcode = __salt__['cmd.retcode']
        if onlyif is not None:
            if not isinstance(onlyif, six.string_types):
                if not onlyif:
                    _valid(status, 'onlyif condition is false')
            elif isinstance(onlyif, six.string_types):
                if retcode(onlyif, cwd=directory, runas=runas, env=env) != 0:
                    _valid(status, 'onlyif condition is false')
        if unless is not None:
            if not isinstance(unless, six.string_types):
                if unless:
                    _valid(status, 'unless condition is true')
            elif isinstance(unless, six.string_types):
                if retcode(unless, cwd=directory, runas=runas, env=env, python_shell=False) == 0:
                    _valid(status, 'unless condition is true')
    if status['status']:
        ret = status
    return ret

# vim:set et sts=4 ts=4 tw=80:
