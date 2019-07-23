# -*- coding: utf-8 -*-
'''
noxfile
~~~~~~~

Nox configuration script
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import sys
import glob
import json
import pprint
import shutil
import tempfile

if __name__ == '__main__':
    sys.stderr.write('Do not execute this file directly. Use nox instead, it will know how to handle this file\n')
    sys.stderr.flush()
    exit(1)

# Import 3rd-party libs
import nox
from nox.command import CommandFailed

IS_PY3 = sys.version_info > (2,)

# Be verbose when runing under a CI context
PIP_INSTALL_SILENT = (os.environ.get('JENKINS_URL') or os.environ.get('CI') or os.environ.get('DRONE')) is None


# Global Path Definitions
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SITECUSTOMIZE_DIR = os.path.join(REPO_ROOT, 'tests', 'support', 'coverage')
IS_WINDOWS = sys.platform.lower().startswith('win')

# Python versions to run against
_PYTHON_VERSIONS = ('2', '2.7', '3', '3.4', '3.5', '3.6', '3.7')

# Nox options
#  Reuse existing virtualenvs
nox.options.reuse_existing_virtualenvs = True
#  Don't fail on missing interpreters
nox.options.error_on_missing_interpreters = False


def _create_ci_directories():
    for dirname in ('logs', 'coverage', 'xml-unittests-output'):
        path = os.path.join(REPO_ROOT, 'artifacts', dirname)
        if not os.path.exists(path):
            os.makedirs(path)


def _get_session_python_version_info(session):
    try:
        version_info = session._runner._real_python_version_info
    except AttributeError:
        old_install_only_value = session._runner.global_config.install_only
        try:
            # Force install only to be false for the following chunk of code
            # For additional information as to why see:
            #   https://github.com/theacodes/nox/pull/181
            session._runner.global_config.install_only = False
            session_py_version = session.run(
                'python', '-c'
                'import sys; sys.stdout.write("{}.{}.{}".format(*sys.version_info))',
                silent=True,
                log=False,
            )
            version_info = tuple(int(part) for part in session_py_version.split('.') if part.isdigit())
            session._runner._real_python_version_info = version_info
        finally:
            session._runner.global_config.install_only = old_install_only_value
    return version_info


def _get_session_python_site_packages_dir(session):
    try:
        site_packages_dir = session._runner._site_packages_dir
    except AttributeError:
        old_install_only_value = session._runner.global_config.install_only
        try:
            # Force install only to be false for the following chunk of code
            # For additional information as to why see:
            #   https://github.com/theacodes/nox/pull/181
            session._runner.global_config.install_only = False
            site_packages_dir = session.run(
                'python', '-c'
                'import sys; from distutils.sysconfig import get_python_lib; sys.stdout.write(get_python_lib())',
                silent=True,
                log=False,
            )
            session._runner._site_packages_dir = site_packages_dir
        finally:
            session._runner.global_config.install_only = old_install_only_value
    return site_packages_dir


def _get_pydir(session):
    version_info = _get_session_python_version_info(session)
    if version_info < (2, 7):
        session.error('Only Python >= 2.7 is supported')
    return 'py{}.{}'.format(*version_info)


def _get_distro_info(session):
    try:
        distro = session._runner._distro
    except AttributeError:
        # The distro package doesn't output anything for Windows
        old_install_only_value = session._runner.global_config.install_only
        try:
            # Force install only to be false for the following chunk of code
            # For additional information as to why see:
            #   https://github.com/theacodes/nox/pull/181
            session._runner.global_config.install_only = False
            session.install('--progress-bar=off', 'distro', silent=PIP_INSTALL_SILENT)
            output = session.run('distro', '-j', silent=True)
            distro = json.loads(output.strip())
            session.log('Distro information:\n%s', pprint.pformat(distro))
            session._runner._distro = distro
        finally:
            session._runner.global_config.install_only = old_install_only_value
    return distro


def _install_system_packages(session):
    '''
    Because some python packages are provided by the distribution and cannot
    be pip installed, and because we don't want the whole system python packages
    on our virtualenvs, we copy the required system python packages into
    the virtualenv
    '''
    system_python_packages = {
        '__debian_based_distros__': [
            '/usr/lib/python{py_version}/dist-packages/*apt*'
        ]
    }
    for key in ('ubuntu-14.04', 'ubuntu-16.04', 'ubuntu-18.04', 'debian-8', 'debian-9'):
        system_python_packages[key] = system_python_packages['__debian_based_distros__']

    distro = _get_distro_info(session)
    distro_keys = [
        '{id}'.format(**distro),
        '{id}-{version}'.format(**distro),
        '{id}-{version_parts[major]}'.format(**distro)
    ]
    version_info = _get_session_python_version_info(session)
    py_version_keys = [
        '{}'.format(*version_info),
        '{}.{}'.format(*version_info)
    ]
    session_site_packages_dir = _get_session_python_site_packages_dir(session)
    for distro_key in distro_keys:
        if distro_key not in system_python_packages:
            continue
        patterns = system_python_packages[distro_key]
        for pattern in patterns:
            for py_version in py_version_keys:
                matches = set(glob.glob(pattern.format(py_version=py_version)))
                if not matches:
                    continue
                for match in matches:
                    src = os.path.realpath(match)
                    dst = os.path.join(session_site_packages_dir, os.path.basename(match))
                    if os.path.exists(dst):
                        session.log('Not overwritting already existing %s with %s', dst, src)
                        continue
                    session.log('Copying %s into %s', src, dst)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copyfile(src, dst)


def _install_requirements(session, transport, *extra_requirements):
    # Install requirements
    distro_requirements = None

    if transport == 'tcp':
        # The TCP requirements are the exact same requirements as the ZeroMQ ones
        transport = 'zeromq'

    pydir = _get_pydir(session)

    if IS_WINDOWS:
        _distro_requirements = os.path.join(REPO_ROOT,
                                            'requirements',
                                            'static',
                                            pydir,
                                            '{}-windows.txt'.format(transport))
        if os.path.exists(_distro_requirements):
            if transport == 'raet':
                # Because we still install ioflo, which requires setuptools-git, which fails with a
                # weird SSL certificate issue(weird because the requirements file requirements install
                # fine), let's previously have setuptools-git installed
                session.install('--progress-bar=off', 'setuptools-git', silent=PIP_INSTALL_SILENT)
            distro_requirements = _distro_requirements
    else:
        _install_system_packages(session)
        distro = _get_distro_info(session)
        distro_keys = [
            '{id}'.format(**distro),
            '{id}-{version}'.format(**distro),
            '{id}-{version_parts[major]}'.format(**distro)
        ]
        for distro_key in distro_keys:
            _distro_requirements = os.path.join(REPO_ROOT,
                                                'requirements',
                                                'static',
                                                pydir,
                                                '{}-{}.txt'.format(transport, distro_key))
            if os.path.exists(_distro_requirements):
                distro_requirements = _distro_requirements
                break

    if distro_requirements is not None:
        _requirements_files = [distro_requirements]
        requirements_files = []
    else:
        _requirements_files = [
            os.path.join(REPO_ROOT, 'requirements', 'pytest.txt')
        ]
        if sys.platform.startswith('linux'):
            requirements_files = [
                os.path.join(REPO_ROOT, 'requirements', 'tests.txt')
            ]
        elif sys.platform.startswith('win'):
            requirements_files = [
                os.path.join(REPO_ROOT, 'pkg', 'windows', 'req.txt'),
            ]
        elif sys.platform.startswith('darwin'):
            requirements_files = [
                os.path.join(REPO_ROOT, 'pkg', 'osx', 'req.txt'),
                os.path.join(REPO_ROOT, 'pkg', 'osx', 'req_ext.txt'),
            ]

    while True:
        if not requirements_files:
            break
        requirements_file = requirements_files.pop(0)

        if requirements_file not in _requirements_files:
            _requirements_files.append(requirements_file)

        session.log('Processing {}'.format(requirements_file))
        with open(requirements_file) as rfh:  # pylint: disable=resource-leakage
            for line in rfh:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('-r'):
                    reqfile = os.path.join(os.path.dirname(requirements_file), line.strip().split()[-1])
                    if reqfile in _requirements_files:
                        continue
                    _requirements_files.append(reqfile)
                    continue

    for requirements_file in _requirements_files:
        session.install('--progress-bar=off', '-r', requirements_file, silent=PIP_INSTALL_SILENT)

    if extra_requirements:
        session.install('--progress-bar=off', *extra_requirements, silent=PIP_INSTALL_SILENT)


def _run_with_coverage(session, *test_cmd):
    session.install('--progress-bar=off', 'coverage==4.5.3', silent=PIP_INSTALL_SILENT)
    session.run('coverage', 'erase')
    python_path_env_var = os.environ.get('PYTHONPATH') or None
    if python_path_env_var is None:
        python_path_env_var = SITECUSTOMIZE_DIR
    else:
        python_path_entries = python_path_env_var.split(os.pathsep)
        if SITECUSTOMIZE_DIR in python_path_entries:
            python_path_entries.remove(SITECUSTOMIZE_DIR)
        python_path_entries.insert(0, SITECUSTOMIZE_DIR)
        python_path_env_var = os.pathsep.join(python_path_entries)
    try:
        session.run(
            *test_cmd,
            env={
                # The updated python path so that sitecustomize is importable
                'PYTHONPATH': python_path_env_var,
                # The full path to the .coverage data file. Makes sure we always write
                # them to the same directory
                'COVERAGE_FILE': os.path.abspath(os.path.join(REPO_ROOT, '.coverage')),
                # Instruct sub processes to also run under coverage
                'COVERAGE_PROCESS_START': os.path.join(REPO_ROOT, '.coveragerc')
            }
        )
    finally:
        # Always combine and generate the XML coverage report
        session.run('coverage', 'combine')
        session.run('coverage', 'xml', '-o', os.path.join(REPO_ROOT, 'artifacts', 'coverage', 'coverage.xml'))


def _runtests(session, coverage, cmd_args):
    # Create required artifacts directories
    _create_ci_directories()
    try:
        if coverage is True:
            _run_with_coverage(session, 'coverage', 'run', os.path.join('tests', 'runtests.py'), *cmd_args)
        else:
            session.run('python', os.path.join('tests', 'runtests.py'), *cmd_args)
    except CommandFailed:
        # Disabling re-running failed tests for the time being
        raise

        # pylint: disable=unreachable
        names_file_path = os.path.join('artifacts', 'failed-tests.txt')
        session.log('Re-running failed tests if possible')
        session.install('--progress-bar=off', 'xunitparser==1.3.3', silent=PIP_INSTALL_SILENT)
        session.run(
            'python',
            os.path.join('tests', 'support', 'generate-names-file-from-failed-test-reports.py'),
            names_file_path
        )
        if not os.path.exists(names_file_path):
            session.log(
                'Failed tests file(%s) was not found. Not rerunning failed tests.',
                names_file_path
            )
            # raise the original exception
            raise
        with open(names_file_path) as rfh:
            contents = rfh.read().strip()
            if not contents:
                session.log(
                    'The failed tests file(%s) is empty. Not rerunning failed tests.',
                    names_file_path
                )
                # raise the original exception
                raise
            failed_tests_count = len(contents.splitlines())
            if failed_tests_count > 500:
                # 500 test failures?! Something else must have gone wrong, don't even bother
                session.error(
                    'Total failed tests({}) > 500. No point on re-running the failed tests'.format(
                        failed_tests_count
                    )
                )

        for idx, flag in enumerate(cmd_args[:]):
            if '--names-file=' in flag:
                cmd_args.pop(idx)
                break
            elif flag == '--names-file':
                cmd_args.pop(idx)  # pop --names-file
                cmd_args.pop(idx)  # pop the actual names file
                break
        cmd_args.append('--names-file={}'.format(names_file_path))
        if coverage is True:
            _run_with_coverage(session, 'coverage', 'run', '-m', 'tests.runtests', *cmd_args)
        else:
            session.run('python', os.path.join('tests', 'runtests.py'), *cmd_args)
        # pylint: enable=unreachable


@nox.session(python=_PYTHON_VERSIONS, name='runtests-parametrized')
@nox.parametrize('coverage', [False, True])
@nox.parametrize('transport', ['zeromq', 'raet', 'tcp'])
@nox.parametrize('crypto', [None, 'm2crypto', 'pycryptodomex'])
def runtests_parametrized(session, coverage, transport, crypto):
    # Install requirements
    _install_requirements(session, transport, 'unittest-xml-reporting==2.2.1')

    if crypto:
        if crypto == 'm2crypto':
            session.run('pip', 'uninstall', '-y', 'pycrypto', 'pycryptodome', 'pycryptodomex', silent=True)
        else:
            session.run('pip', 'uninstall', '-y', 'm2crypto', silent=True)
        session.install('--progress-bar=off', crypto, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        '--tests-logfile={}'.format(
            os.path.join(REPO_ROOT, 'artifacts', 'logs', 'runtests.log')
        ),
        '--transport={}'.format(transport)
    ] + session.posargs
    _runtests(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS)
@nox.parametrize('coverage', [False, True])
def runtests(session, coverage):
    '''
    runtests.py session with zeromq transport and default crypto
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=None, transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-tcp')
@nox.parametrize('coverage', [False, True])
def runtests_tcp(session, coverage):
    '''
    runtests.py session with TCP transport and default crypto
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=None, transport=\'tcp\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-zeromq')
@nox.parametrize('coverage', [False, True])
def runtests_zeromq(session, coverage):
    '''
    runtests.py session with zeromq transport and default crypto
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=None, transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-raet')
@nox.parametrize('coverage', [False, True])
def runtests_raet(session, coverage):
    '''
    runtests.py session with raet transport and default crypto
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=None, transport=\'raet\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-m2crypto')
@nox.parametrize('coverage', [False, True])
def runtests_m2crypto(session, coverage):
    '''
    runtests.py session with zeromq transport and m2crypto
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=\'m2crypto\', transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-tcp-m2crypto')
@nox.parametrize('coverage', [False, True])
def runtests_tcp_m2crypto(session, coverage):
    '''
    runtests.py session with TCP transport and m2crypto
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=\'m2crypto\', transport=\'tcp\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-zeromq-m2crypto')
@nox.parametrize('coverage', [False, True])
def runtests_zeromq_m2crypto(session, coverage):
    '''
    runtests.py session with zeromq transport and m2crypto
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=\'m2crypto\', transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-raet-m2crypto')
@nox.parametrize('coverage', [False, True])
def runtests_raet_m2crypto(session, coverage):
    '''
    runtests.py session with raet transport and m2crypto
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=\'m2crypto\', transport=\'raet\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-pycryptodomex')
@nox.parametrize('coverage', [False, True])
def runtests_pycryptodomex(session, coverage):
    '''
    runtests.py session with zeromq transport and pycryptodomex
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=\'pycryptodomex\', transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-tcp-pycryptodomex')
@nox.parametrize('coverage', [False, True])
def runtests_tcp_pycryptodomex(session, coverage):
    '''
    runtests.py session with TCP transport and pycryptodomex
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=\'pycryptodomex\', transport=\'tcp\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-zeromq-pycryptodomex')
@nox.parametrize('coverage', [False, True])
def runtests_zeromq_pycryptodomex(session, coverage):
    '''
    runtests.py session with zeromq transport and pycryptodomex
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=\'pycryptodomex\', transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-raet-pycryptodomex')
@nox.parametrize('coverage', [False, True])
def runtests_raet_pycryptodomex(session, coverage):
    '''
    runtests.py session with raet transport and pycryptodomex
    '''
    session.notify(
        'runtests-parametrized-{}(coverage={}, crypto=\'pycryptodomex\', transport=\'raet\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='runtests-cloud')
@nox.parametrize('coverage', [False, True])
def runtests_cloud(session, coverage):
    # Install requirements
    _install_requirements(session, 'zeromq', 'unittest-xml-reporting==2.2.1')

    pydir = _get_pydir(session)
    cloud_requirements = os.path.join(REPO_ROOT, 'requirements', 'static', pydir, 'cloud.txt')

    session.install('--progress-bar=off', '-r', cloud_requirements, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        '--tests-logfile={}'.format(
            os.path.join(REPO_ROOT, 'artifacts', 'logs', 'runtests.log')
        ),
        '--cloud-provider-tests'
    ] + session.posargs
    _runtests(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name='runtests-tornado')
@nox.parametrize('coverage', [False, True])
def runtests_tornado(session, coverage):
    # Install requirements
    _install_requirements(session, 'zeromq', 'unittest-xml-reporting==2.2.1')
    session.install('--progress-bar=off', 'tornado==5.0.2', silent=PIP_INSTALL_SILENT)
    session.install('--progress-bar=off', 'pyzmq==17.0.0', silent=PIP_INSTALL_SILENT)

    cmd_args = [
        '--tests-logfile={}'.format(
            os.path.join(REPO_ROOT, 'artifacts', 'logs', 'runtests.log')
        ),
    ] + session.posargs
    _runtests(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name='pytest-parametrized')
@nox.parametrize('coverage', [False, True])
@nox.parametrize('transport', ['zeromq', 'raet', 'tcp'])
@nox.parametrize('crypto', [None, 'm2crypto', 'pycryptodomex'])
def pytest_parametrized(session, coverage, transport, crypto):
    # Install requirements
    _install_requirements(session, transport)

    if crypto:
        if crypto == 'm2crypto':
            session.run('pip', 'uninstall', '-y', 'pycrypto', 'pycryptodome', 'pycryptodomex', silent=True)
        else:
            session.run('pip', 'uninstall', '-y', 'm2crypto', silent=True)
        session.install('--progress-bar=off', crypto, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        '--rootdir', REPO_ROOT,
        '--log-file={}'.format(
            os.path.join(REPO_ROOT, 'artifacts', 'logs', 'runtests.log')
        ),
        '--no-print-logs',
        '-ra',
        '-s',
        '--transport={}'.format(transport)
    ] + session.posargs
    _pytest(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS)
@nox.parametrize('coverage', [False, True])
def pytest(session, coverage):
    '''
    pytest session with zeromq transport and default crypto
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=None, transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-tcp')
@nox.parametrize('coverage', [False, True])
def pytest_tcp(session, coverage):
    '''
    pytest session with TCP transport and default crypto
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=None, transport=\'tcp\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-zeromq')
@nox.parametrize('coverage', [False, True])
def pytest_zeromq(session, coverage):
    '''
    pytest session with zeromq transport and default crypto
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=None, transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-raet')
@nox.parametrize('coverage', [False, True])
def pytest_raet(session, coverage):
    '''
    pytest session with raet transport and default crypto
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=None, transport=\'raet\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-m2crypto')
@nox.parametrize('coverage', [False, True])
def pytest_m2crypto(session, coverage):
    '''
    pytest session with zeromq transport and m2crypto
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=\'m2crypto\', transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-tcp-m2crypto')
@nox.parametrize('coverage', [False, True])
def pytest_tcp_m2crypto(session, coverage):
    '''
    pytest session with TCP transport and m2crypto
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=\'m2crypto\', transport=\'tcp\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-zeromq-m2crypto')
@nox.parametrize('coverage', [False, True])
def pytest_zeromq_m2crypto(session, coverage):
    '''
    pytest session with zeromq transport and m2crypto
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=\'m2crypto\', transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-raet-m2crypto')
@nox.parametrize('coverage', [False, True])
def pytest_raet_m2crypto(session, coverage):
    '''
    pytest session with raet transport and m2crypto
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=\'m2crypto\', transport=\'raet\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-pycryptodomex')
@nox.parametrize('coverage', [False, True])
def pytest_pycryptodomex(session, coverage):
    '''
    pytest session with zeromq transport and pycryptodomex
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=\'pycryptodomex\', transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-tcp-pycryptodomex')
@nox.parametrize('coverage', [False, True])
def pytest_tcp_pycryptodomex(session, coverage):
    '''
    pytest session with TCP transport and pycryptodomex
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=\'pycryptodomex\', transport=\'tcp\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-zeromq-pycryptodomex')
@nox.parametrize('coverage', [False, True])
def pytest_zeromq_pycryptodomex(session, coverage):
    '''
    pytest session with zeromq transport and pycryptodomex
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=\'pycryptodomex\', transport=\'zeromq\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-raet-pycryptodomex')
@nox.parametrize('coverage', [False, True])
def pytest_raet_pycryptodomex(session, coverage):
    '''
    pytest session with raet transport and pycryptodomex
    '''
    session.notify(
        'pytest-parametrized-{}(coverage={}, crypto=\'pycryptodomex\', transport=\'raet\')'.format(
            session.python,
            coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name='pytest-cloud')
@nox.parametrize('coverage', [False, True])
def pytest_cloud(session, coverage):
    # Install requirements
    _install_requirements(session, 'zeromq')
    pydir = _get_pydir(session)
    cloud_requirements = os.path.join(REPO_ROOT, 'requirements', 'static', pydir, 'cloud.txt')

    session.install('--progress-bar=off', '-r', cloud_requirements, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        '--rootdir', REPO_ROOT,
        '--log-file={}'.format(
            os.path.join(REPO_ROOT, 'artifacts', 'logs', 'runtests.log')
        ),
        '--no-print-logs',
        '-ra',
        '-s',
        os.path.join(REPO_ROOT, 'tests', 'integration', 'cloud', 'providers')
    ] + session.posargs
    _pytest(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name='pytest-tornado')
@nox.parametrize('coverage', [False, True])
def pytest_tornado(session, coverage):
    # Install requirements
    _install_requirements(session, 'zeromq')
    session.install('--progress-bar=off', 'tornado==5.0.2', silent=PIP_INSTALL_SILENT)
    session.install('--progress-bar=off', 'pyzmq==17.0.0', silent=PIP_INSTALL_SILENT)

    cmd_args = [
        '--rootdir', REPO_ROOT,
        '--log-file={}'.format(
            os.path.join(REPO_ROOT, 'artifacts', 'logs', 'runtests.log')
        ),
        '--no-print-logs',
        '-ra',
        '-s',
    ] + session.posargs
    _pytest(session, coverage, cmd_args)


def _pytest(session, coverage, cmd_args):
    # Create required artifacts directories
    _create_ci_directories()

    try:
        if coverage is True:
            _run_with_coverage(session, 'coverage', 'run', '-m', 'py.test', *cmd_args)
        else:
            session.run('py.test', *cmd_args)
    except CommandFailed:
        # Re-run failed tests
        session.log('Re-running failed tests')
        cmd_args.append('--lf')
        if coverage is True:
            _run_with_coverage(session, 'coverage', 'run', '-m', 'py.test', *cmd_args)
        else:
            session.run('py.test', *cmd_args)


def _lint(session, rcfile, flags, paths):
    _install_requirements(session, 'zeromq')
    _install_requirements(session, 'raet')
    session.install('--progress-bar=off', '-r', 'requirements/static/{}/lint.txt'.format(_get_pydir(session)), silent=PIP_INSTALL_SILENT)
    session.run('pylint', '--version')
    pylint_report_path = os.environ.get('PYLINT_REPORT')

    cmd_args = [
        'pylint',
        '--rcfile={}'.format(rcfile)
    ] + list(flags) + list(paths)

    stdout = tempfile.TemporaryFile(mode='w+b')
    lint_failed = False
    try:
        session.run(*cmd_args, stdout=stdout)
    except CommandFailed:
        lint_failed = True
        raise
    finally:
        stdout.seek(0)
        contents = stdout.read()
        if contents:
            if IS_PY3:
                contents = contents.decode('utf-8')
            else:
                contents = contents.encode('utf-8')
            sys.stdout.write(contents)
            sys.stdout.flush()
            if pylint_report_path:
                # Write report
                with open(pylint_report_path, 'w') as wfh:
                    wfh.write(contents)
                session.log('Report file written to %r', pylint_report_path)
        stdout.close()


@nox.session(python='2.7')
def lint(session):
    '''
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
    '''
    session.notify('lint-salt-{}'.format(session.python))
    session.notify('lint-tests-{}'.format(session.python))


@nox.session(python='2.7', name='lint-salt')
def lint_salt(session):
    '''
    Run PyLint against Salt. Set PYLINT_REPORT to a path to capture output.
    '''
    flags = [
        '--disable=I,W1307,C0411,C0413,W8410,str-format-in-logging'
    ]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ['setup.py', 'salt/']
    _lint(session, '.testing.pylintrc', flags, paths)


@nox.session(python='2.7', name='lint-tests')
def lint_tests(session):
    '''
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
    '''
    flags = [
        '--disable=I,W0232,E1002,W1307,C0411,C0413,W8410,str-format-in-logging'
    ]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ['tests/']
    _lint(session, '.testing.pylintrc', flags, paths)


@nox.session(python='3')
def docs(session):
    '''
    Build Salt's Documentation
    '''
    pydir = _get_pydir(session)
    if pydir == 'py3.4':
        session.error('Sphinx only runs on Python >= 3.5')
    session.install(
        '--progress-bar=off',
        '-r', 'requirements/static/{}/docs.txt'.format(pydir),
        silent=PIP_INSTALL_SILENT)
    os.chdir('doc/')
    session.run('make', 'clean', external=True)
    session.run('make', 'html', 'SPHINXOPTS=-W', external=True)
    session.run('tar', '-czvf', 'doc-archive.tar.gz', '_build/html')
    os.chdir('..')
