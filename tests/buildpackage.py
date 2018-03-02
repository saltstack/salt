# -*- coding: utf-8 -*-
# Maintainer: Erik Johnson (https://github.com/terminalmage)
#
# WARNING: This script will recursively remove the build and artifact
# directories.
#
# This script is designed for speed, therefore it does not use mock and does not
# run tests. It *will* install the build deps on the machine running the script.
#

# pylint: disable=file-perms,resource-leakage

from __future__ import absolute_import, print_function
import errno
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
from optparse import OptionParser, OptionGroup

logging.QUIET = 0
logging.GARBAGE = 1
logging.TRACE = 5

logging.addLevelName(logging.QUIET, 'QUIET')
logging.addLevelName(logging.TRACE, 'TRACE')
logging.addLevelName(logging.GARBAGE, 'GARBAGE')

LOG_LEVELS = {
    'all': logging.NOTSET,
    'debug': logging.DEBUG,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
    'garbage': logging.GARBAGE,
    'info': logging.INFO,
    'quiet': logging.QUIET,
    'trace': logging.TRACE,
    'warning': logging.WARNING,
}

log = logging.getLogger(__name__)

# FUNCTIONS


def _abort(msgs):
    '''
    Unrecoverable error, pull the plug
    '''
    if not isinstance(msgs, list):
        msgs = [msgs]
    for msg in msgs:
        log.error(msg)
        sys.stderr.write(msg + '\n\n')
    sys.stderr.write('Build failed. See log file for further details.\n')
    sys.exit(1)


# HELPER FUNCTIONS

def _init():
    '''
    Parse CLI options.
    '''
    parser = OptionParser()
    parser.add_option('--platform',
                      dest='platform',
                      help='Platform (\'os\' grain)')
    parser.add_option('--log-level',
                      dest='log_level',
                      default='warning',
                      help='Control verbosity of logging. Default: %default')

    # All arguments dealing with file paths (except for platform-specific ones
    # like those for SPEC files) should be placed in this group so that
    # relative paths are properly expanded.
    path_group = OptionGroup(parser, 'File/Directory Options')
    path_group.add_option('--source-dir',
                          default='/testing',
                          help='Source directory. Must be a git checkout. '
                               '(default: %default)')
    path_group.add_option('--build-dir',
                          default='/tmp/salt-buildpackage',
                          help='Build root, will be removed if it exists '
                               'prior to running script. (default: %default)')
    path_group.add_option('--artifact-dir',
                          default='/tmp/salt-packages',
                          help='Location where build artifacts should be '
                               'placed for Jenkins to retrieve them '
                               '(default: %default)')
    parser.add_option_group(path_group)

    # This group should also consist of nothing but file paths, which will be
    # normalized below.
    rpm_group = OptionGroup(parser, 'RPM-specific File/Directory Options')
    rpm_group.add_option('--spec',
                         dest='spec_file',
                         default='/tmp/salt.spec',
                         help='Spec file to use as a template to build RPM. '
                              '(default: %default)')
    parser.add_option_group(rpm_group)

    opts = parser.parse_args()[0]

    # Expand any relative paths
    for group in (path_group, rpm_group):
        for path_opt in [opt.dest for opt in group.option_list]:
            path = getattr(opts, path_opt)
            if not os.path.isabs(path):
                # Expand ~ or ~user
                path = os.path.expanduser(path)
                if not os.path.isabs(path):
                    # Still not absolute, resolve '..'
                    path = os.path.realpath(path)
                # Update attribute with absolute path
                setattr(opts, path_opt, path)

    # Sanity checks
    problems = []
    if not opts.platform:
        problems.append('Platform (\'os\' grain) required')
    if not os.path.isdir(opts.source_dir):
        problems.append('Source directory {0} not found'
                        .format(opts.source_dir))
    try:
        shutil.rmtree(opts.build_dir)
    except OSError as exc:
        if exc.errno not in (errno.ENOENT, errno.ENOTDIR):
            problems.append('Unable to remove pre-existing destination '
                            'directory {0}: {1}'.format(opts.build_dir, exc))
    finally:
        try:
            os.makedirs(opts.build_dir)
        except OSError as exc:
            problems.append('Unable to create destination directory {0}: {1}'
                            .format(opts.build_dir, exc))
    try:
        shutil.rmtree(opts.artifact_dir)
    except OSError as exc:
        if exc.errno not in (errno.ENOENT, errno.ENOTDIR):
            problems.append('Unable to remove pre-existing artifact directory '
                            '{0}: {1}'.format(opts.artifact_dir, exc))
    finally:
        try:
            os.makedirs(opts.artifact_dir)
        except OSError as exc:
            problems.append('Unable to create artifact directory {0}: {1}'
                            .format(opts.artifact_dir, exc))

    # Create log file in the artifact dir so it is sent back to master if the
    # job fails
    opts.log_file = os.path.join(opts.artifact_dir, 'salt-buildpackage.log')

    if problems:
        _abort(problems)

    return opts


def _move(src, dst):
    '''
    Wrapper around shutil.move()
    '''
    try:
        os.remove(os.path.join(dst, os.path.basename(src)))
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            _abort(exc)

    try:
        shutil.move(src, dst)
    except shutil.Error as exc:
        _abort(exc)


def _run_command(args):
    log.info('Running command: {0}'.format(args))
    proc = subprocess.Popen(args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if stdout:
        log.debug('Command output: \n{0}'.format(stdout))
    if stderr:
        log.error(stderr)
    log.info('Return code: {0}'.format(proc.returncode))
    return stdout, stderr, proc.returncode


def _make_sdist(opts, python_bin='python'):
    os.chdir(opts.source_dir)
    stdout, stderr, rcode = _run_command([python_bin, 'setup.py', 'sdist'])
    if rcode == 0:
        # Find the sdist with the most recently-modified metadata
        sdist_path = max(
            glob.iglob(os.path.join(opts.source_dir, 'dist', 'salt-*.tar.gz')),
            key=os.path.getctime
        )
        log.info('sdist is located at {0}'.format(sdist_path))
        return sdist_path
    else:
        _abort('Failed to create sdist')


# BUILDER FUNCTIONS


def build_centos(opts):
    '''
    Build an RPM
    '''
    log.info('Building CentOS RPM')
    log.info('Detecting major release')
    try:
        with open('/etc/redhat-release', 'r') as fp_:
            redhat_release = fp_.read().strip()
            major_release = int(redhat_release.split()[2].split('.')[0])
    except (ValueError, IndexError):
        _abort('Unable to determine major release from /etc/redhat-release '
               'contents: \'{0}\''.format(redhat_release))
    except IOError as exc:
        _abort('{0}'.format(exc))

    log.info('major_release: {0}'.format(major_release))

    define_opts = [
        '--define',
        '_topdir {0}'.format(os.path.join(opts.build_dir))
    ]
    build_reqs = ['rpm-build']
    if major_release == 5:
        python_bin = 'python26'
        define_opts.extend(['--define', 'dist .el5'])
        if os.path.exists('/etc/yum.repos.d/saltstack.repo'):
            build_reqs.extend(['--enablerepo=saltstack'])
        build_reqs.extend(['python26-devel'])
    elif major_release == 6:
        build_reqs.extend(['python-devel'])
    elif major_release == 7:
        build_reqs.extend(['python-devel', 'systemd-units'])
    else:
        _abort('Unsupported major release: {0}'.format(major_release))

    # Install build deps
    _run_command(['yum', '-y', 'install'] + build_reqs)

    # Make the sdist
    try:
        sdist = _make_sdist(opts, python_bin=python_bin)
    except NameError:
        sdist = _make_sdist(opts)

    # Example tarball names:
    #   - Git checkout: salt-2014.7.0rc1-1584-g666602e.tar.gz
    #   - Tagged release: salt-2014.7.0.tar.gz
    tarball_re = re.compile(r'^salt-([^-]+)(?:-(\d+)-(g[0-9a-f]+))?\.tar\.gz$')
    try:
        base, offset, oid = tarball_re.match(os.path.basename(sdist)).groups()
    except AttributeError:
        _abort('Unable to extract version info from sdist filename \'{0}\''
               .format(sdist))

    if offset is None:
        salt_pkgver = salt_srcver = base
    else:
        salt_pkgver = '.'.join((base, offset, oid))
        salt_srcver = '-'.join((base, offset, oid))

    log.info('salt_pkgver: {0}'.format(salt_pkgver))
    log.info('salt_srcver: {0}'.format(salt_srcver))

    # Setup build environment
    for build_dir in 'BUILD BUILDROOT RPMS SOURCES SPECS SRPMS'.split():
        path = os.path.join(opts.build_dir, build_dir)
        try:
            os.makedirs(path)
        except OSError:
            pass
        if not os.path.isdir(path):
            _abort('Unable to make directory: {0}'.format(path))

    # Get sources into place
    build_sources_path = os.path.join(opts.build_dir, 'SOURCES')
    rpm_sources_path = os.path.join(opts.source_dir, 'pkg', 'rpm')
    _move(sdist, build_sources_path)
    for src in ('salt-master', 'salt-syndic', 'salt-minion', 'salt-api',
                'salt-master.service', 'salt-syndic.service',
                'salt-minion.service', 'salt-api.service',
                'README.fedora', 'logrotate.salt', 'salt.bash'):
        shutil.copy(os.path.join(rpm_sources_path, src), build_sources_path)

    # Prepare SPEC file
    spec_path = os.path.join(opts.build_dir, 'SPECS', 'salt.spec')
    with open(opts.spec_file, 'r') as spec:
        spec_lines = spec.read().splitlines()
    with open(spec_path, 'w') as fp_:
        for line in spec_lines:
            if line.startswith('%global srcver '):
                line = '%global srcver {0}'.format(salt_srcver)
            elif line.startswith('Version: '):
                line = 'Version: {0}'.format(salt_pkgver)
            fp_.write(line + '\n')

    # Do the thing
    cmd = ['rpmbuild', '-ba']
    cmd.extend(define_opts)
    cmd.append(spec_path)
    stdout, stderr, rcode = _run_command(cmd)

    if rcode != 0:
        _abort('Build failed.')

    packages = glob.glob(
        os.path.join(
            opts.build_dir,
            'RPMS',
            'noarch',
            'salt-*{0}*.noarch.rpm'.format(salt_pkgver)
        )
    )
    packages.extend(
        glob.glob(
            os.path.join(
                opts.build_dir,
                'SRPMS',
                'salt-{0}*.src.rpm'.format(salt_pkgver)
            )
        )
    )
    return packages


# MAIN

if __name__ == '__main__':
    opts = _init()

    print('Starting {0} build. Progress will be logged to {1}.'
          .format(opts.platform, opts.log_file))

    # Setup logging
    log_format = '%(asctime)s.%(msecs)03d %(levelname)s: %(message)s'
    log_datefmt = '%H:%M:%S'
    log_level = LOG_LEVELS[opts.log_level] \
        if opts.log_level in LOG_LEVELS \
        else LOG_LEVELS['warning']
    logging.basicConfig(filename=opts.log_file,
                        format=log_format,
                        datefmt=log_datefmt,
                        level=LOG_LEVELS[opts.log_level])
    if opts.log_level not in LOG_LEVELS:
        log.error('Invalid log level \'{0}\', falling back to \'warning\''
                  .format(opts.log_level))

    # Build for the specified platform
    if not opts.platform:
        _abort('Platform required')
    elif opts.platform.lower() == 'centos':
        artifacts = build_centos(opts)
    else:
        _abort('Unsupported platform \'{0}\''.format(opts.platform))

    msg = ('Build complete. Artifacts will be stored in {0}'
           .format(opts.artifact_dir))
    log.info(msg)
    print(msg)  # pylint: disable=C0325
    for artifact in artifacts:
        shutil.copy(artifact, opts.artifact_dir)
        log.info('Copied {0} to artifact directory'.format(artifact))
    log.info('Done!')
