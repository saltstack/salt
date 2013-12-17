# -*- coding: utf-8 -*-
'''
Management of zc.buildout
=========================

This module is inspired from `minitage's buildout maker`__

.. __: https://github.com/minitage/minitage/blob/master/src/minitage/core/makers/buildout.py

.. versionadded:: Boron

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

# Define the module's virtual name
__virtualname__ = 'buildout'


def __virtual__():
    '''
    Only load if buildout libs are present
    '''
    if True:
        return __virtualname__
    return False

# Import python libs
import os
import re
import sys
import traceback
import urllib2

# Import salt libs
from salt.exceptions import CommandExecutionError
from salt._compat import string_types


INVALID_RESPONSE = 'We did not get any expectable answer from buildout'
VALID_RESPONSE = ''
NOTSET = object()
HR = u'{0}\n'.format('-' * 80)
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
    1: u'http://downloads.buildout.org/1/bootstrap.py',
    2: u'http://downloads.buildout.org/2/bootstrap.py',
}
DEFAULT_VER = 2


def _salt_callback(func):
    LOG.clear()

    def _call_callback(*a, **kw):
        st = BASE_STATUS.copy()
        directory = kw.get('directory', '.')
        onlyif = kw.get('onlyif', None)
        unless = kw.get('unless', None)
        runas = kw.get('runas', None)
        env = kw.get('env', ())
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
        return status
    _call_callback.__doc__ = func.__doc__
    return _call_callback


class _Logger(object):
    levels = ('info', 'warn', 'debug', 'error')

    def __init__(self):
        self._msgs = []
        self._by_level = {}

    def _log(self, level, msg):
        if not level in self._by_level:
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
    outlog, outlog_by_level = u'', u''
    m['comment'] = comment
    if out and isinstance(out, string_types):
        outlog += HR
        outlog += u'OUTPUT:\n'
        outlog += u'{0}\n'.format(out)
        outlog += HR
    if m['logs']:
        outlog += HR
        outlog += u'Log summary:\n'
        outlog += HR
        outlog_by_level += HR
        outlog_by_level += u'Log summary by level:\n'
        outlog_by_level += HR
        for level, msg in m['logs']:
            outlog += '\n{0}: {1}\n'.format(level.upper(), msg)
        for logger in 'error', 'warn', 'info', 'debug':
            logs = m['logs_by_level'].get(logger, [])
            if logs:
                outlog_by_level += '\n{0}:\n'.format(logger.upper())
                outlog_by_level += '\n'.join(logs)
                outlog_by_level += '\n'
        outlog += HR
    m['outlog'] = outlog
    m['outlog_by_level'] = outlog_by_level
    return m


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
           exitcode=0):
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

    '''
    ret = None
    directory = os.path.abspath(directory)
    if isinstance(command, list):
        command = ' '.join(command)
    LOG.debug(u'Running {0}'.format(command))
    ret = __salt__['cmd.run_all'](command, cwd=directory, runas=runas, env=env)
    out = ret['stdout'] + '\n\n' + ret['stderr']
    if (exitcode is not None) and (ret['retcode'] != exitcode):
        raise _BuildoutError(out)
    ret['output'] = out
    if output:
        ret = out
    return ret


class _BuildoutError(CommandExecutionError):
    '''General Buildout Error.'''


def _has_old_distribute(python=sys.executable, runas=None, env=()):
    old_distribute = False
    try:
        cmd = [python,
               '-c',
               '\'import pkg_resources;'
               'print pkg_resources.'
               'get_distribution(\"distribute\").location\'']
        #LOG.debug('Run %s' % ' '.join(cmd))
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
        #LOG.debug('Run %s' % ' '.join(cmd))
        ret = _Popen(cmd, runas=runas, env=env, output=True)
        if 'true' in ret.lower():
            new_st = True
    except Exception:
        new_st = False
    return new_st


def _find_cfgs(path, cfgs=None):
    '''
    Find all buildout configs in a sudirectory.
    only builout.cfg and etc/buildout.cfg are valid in::

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
        if os.path.isdir(fi) and (not i in ignored):
            dirs.append(fi)
    for fpath in dirs:
        for p, ids, ifs in os.walk(fpath):
            for i in ifs:
                if i.endswith('.cfg'):
                    cfgs.append(os.path.join(p, i))
    return cfgs


def _get_bootstrap_content(directory='.'):
    '''
    Get the current bootstrap.py script content
    '''
    try:
        fic = open(
            os.path.join(
                os.path.abspath(directory), 'bootstrap.py'))
        oldcontent = fic.read()
        fic.close()
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
            fic = open(f)
            buildout1re = re.compile(r'^zc\.buildout\s*=\s*1', RE_F)
            dfic = fic.read()
            if (
                    ('buildout.dumppick' in dfic)
                    or
                    (buildout1re.search(dfic))
            ):
                buildoutver = 1
            fic.close()
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
    Get the most appropriate download url for the bootstrap script.

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
    is to have an locally stale boostrap, we just try rab a new copy

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
    LOG.debug('Using %s' % booturl)
    # try to donwload an uptodate bootstrap
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
                open(os.path.join(
                    dbuild,
                    '{0}.updated_bootstrap'.format(buildout_ver)))
            except (OSError, IOError):
                LOG.info('Bootstrap updated from repository')
                data = urllib2.urlopen(booturl).read()
                updated = True
                dled = True
        if not 'socket.setdefaulttimeout' in data:
            updated = True
            ldata = data.splitlines()
            ldata.insert(1, 'import socket;socket.setdefaulttimeout(2)')
            data = '\n'.join(ldata)
        if updated:
            comment = 'Bootstrap updated'
            fic = open(b_py, 'w')
            fic.write(data)
            fic.close()
        if dled:
            afic = open(os.path.join(
                dbuild, '{0}.updated_bootstrap'.format(buildout_ver)
            ), 'w')
            afic.write('foo')
            afic.close()
    except (OSError, IOError):
        if oldcontent:
            fic = open(b_py, 'w')
            fic.write(oldcontent)
            fic.close()

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
              new_st=None):
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

    new_set
        Forcing use of setuptools >= 0.7

    python
        path to a python executable to use in place of default (salt one)

    onlyif
        Only execute cmd if statement on the host return 0

    unless
        Do not execute cmd if statement on the host return 0

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
        LOG.warning(u'Forcing to use setuptools as we have setuptools >= 0.7')
    if distribute:
        new_st = False
        if buildout_ver == 1:
            LOG.warning(u'Using distribute !')
            bootstrap_args += ' %s' % '--distribute'
    if not os.path.isdir(dbuild):
        os.makedirs(dbuild)
    upgrade_bootstrap(directory,
                      offline=offline,
                      buildout_ver=buildout_ver)
    # be sure which buildout bootstrap we have
    b_py = os.path.join(directory, 'bootstrap.py')
    fic = open(b_py)
    content = fic.read()
    fic.close()
    if (
        (False != test_release)
        and ' --accept-buildout-test-releases' in content
    ):
        bootstrap_args += ' --accept-buildout-test-releases'
    if config and '"-c"' in content:
        bootstrap_args += ' -c %s' % config
    cmd = '%s bootstrap.py %s ' % (python, bootstrap_args,)
    ret = _Popen(cmd, directory=directory, runas=runas, env=env)
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
                 python=sys.executable):
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
        run buildout unconditionnaly

    verbose
        run buildout in verbose mode (-vvvvv)

    CLI Example:

    .. code-block:: bash

        salt '*' buildout.run_buildout /srv/mybuildout
    '''
    directory = os.path.abspath(directory)
    bcmd = os.path.join(directory, 'bin', 'buildout')
    installed_cfg = os.path.join(directory, '.installed.cfg')
    argv = []
    if verbose:
        LOG.debug(u'Buildout is running in verbose mode!')
        argv.append('-vvvvvvv')
    if not newest and os.path.exists(installed_cfg):
        LOG.debug(u'Buildout is running in non newest mode!')
        argv.append('-N')
    if newest:
        LOG.debug(u'Buildout is running in newest mode!')
        argv.append('-n')
    if offline:
        LOG.debug(u'Buildout is running in offline mode!')
        argv.append('-o')
    if debug:
        LOG.debug(u'Buildout is running in debug mode!')
        argv.append('-D')
    cmds, outputs = [], []
    if parts:
        for part in parts:
            LOG.info(u'Installing single part: {0}'.format(part))
            cmd = '{0} -c {1} {2} install {3}'.format(
                bcmd, config, ' '.join(argv), part)
            cmds.append(cmd)
            outputs.append(
                _Popen(
                    cmd, directory=directory,
                    runas=runas,
                    env=env,
                    output=True)
            )
    else:
        LOG.info(u'Installing all buildout parts')
        cmd = '{0} -c {1} {2}'.format(
            bcmd, config, ' '.join(argv))
        cmds.append(cmd)
        outputs.append(
            _Popen(cmd, directory=directory, runas=runas, env=env, output=True)
        )

    return {'comment': '\n'.join(cmds),
            'out': '\n'.join(outputs)}


def _merge_statuses(statuses):
    status = BASE_STATUS.copy()
    status['status'] = None
    status['merged_statuses'] = True
    status['out'] = []
    for st in statuses:
        if status['status'] is not False:
            status['status'] = st['status']
        out = st['out']
        comment = st['comment']
        logs = st['logs']
        logs_by_level = st['logs_by_level']
        outlog_by_level = st['outlog_by_level']
        outlog = st['outlog']
        if out:
            if not status['out']:
                status['out'] = ''
            status['out'] += '\n'
            status['out'] += HR
            status['out'] += '{0}\n'.format(out)
            status['out'] += HR
        if comment:
            if not status['comment']:
                status['comment'] = ''
            status['comment'] += '\n{0}\n'.format(comment)
        if outlog:
            if not status['outlog']:
                status['outlog'] = ''
            status['outlog'] += '\n{0}'.format(HR)
            status['outlog'] += outlog
        if outlog_by_level:
            if not status['outlog_by_level']:
                status['outlog_by_level'] = ''
            status['outlog_by_level'] += '\n{0}'.format(HR)
            status['outlog_by_level'] += outlog_by_level
        status['logs'].extend(logs)
        for log in logs_by_level:
            if not log in status['logs_by_level']:
                status['logs_by_level'][log] = []
            status['logs_by_level'][log].extend(logs_by_level[log])
    return status


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
             unless=None):
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

    new_set
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


    CLI Example:

    .. code-block:: bash

        salt '*' buildout.buildout /srv/mybuildout
    '''
    LOG.info(
        'Running buildout in %s (%s)' % (directory,
                                         config))
    boot_ret = bootstrap(directory,
                         config=config,
                         buildout_ver=buildout_ver,
                         test_release=test_release,
                         offline=offline,
                         new_st=new_st,
                         env=env,
                         runas=runas,
                         distribute=distribute,
                         python=python)
    buildout_ret = run_buildout(directory=directory,
                                config=config,
                                parts=parts,
                                offline=offline,
                                newest=newest,
                                runas=runas,
                                env=env,
                                verbose=verbose,
                                debug=debug)
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
            if not isinstance(onlyif, string_types):
                if not onlyif:
                    _valid(status, 'onlyif execution failed')
            elif isinstance(onlyif, string_types):
                if retcode(onlyif, cwd=directory, runas=runas, env=env) != 0:
                    _valid(status, 'onlyif execution failed')
        if unless is not None:
            if not isinstance(unless, string_types):
                if unless:
                    _valid(status, 'unless execution succeeded')
            elif isinstance(unless, string_types):
                if retcode(unless, cwd=directory, runas=runas, env=env) == 0:
                    _valid(status, 'unless execution succeeded')
    if status['status']:
        ret = status
    return ret

# vim:set et sts=4 ts=4 tw=80:
