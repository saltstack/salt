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
import json
import pprint


if __name__ == '__main__':
    sys.stderr.write('Do not execute this file directly. Use nox instead, it will know how to handle this file\n')
    sys.stderr.flush()
    exit(1)

# Import 3rd-party libs
import nox
from nox.command import CommandFailed

# Global Path Definitions
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SITECUSTOMIZE_DIR = os.path.join(REPO_ROOT, 'tests', 'support', 'coverage')
IS_WINDOWS = sys.platform.lower().startswith('win')
REQUIREMENTS_OVERRIDES = {
    None: [
        'jsonschema <= 2.6.0'
    ],
    'ubuntu-14.04': [
        'tornado < 5.0'
    ]
}

# Python versions to run against
_PYTHON_VERSIONS = ('2', '2.7', '3', '3.4', '3.5', '3.6')

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


def _install_requirements(session, transport, *extra_requirements):
    # Install requirements
    distro_requirements = None

    if session.python.startswith('2'):
        pydir = 'py2'
    else:
        pydir = 'py3'

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
                session.install('setuptools-git')
            distro_requirements = _distro_requirements
    else:
        # The distro package doesn't output anything for Windows
        session.install('distro')
        output = session.run('distro', '-j', silent=True)
        distro = json.loads(output.strip())
        session.log('Distro information:\n%s', pprint.pformat(distro))
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
        session.install('-r', requirements_file)

    if extra_requirements:
        session.install(*extra_requirements)


def _run_with_coverage(session, *test_cmd):
    session.install('coverage==4.5.3')
    session.run('coverage', 'erase')
    python_path_env_var = os.environ.get('PYTHONPATH') or None
    if python_path_env_var is None:
        python_path_env_var = SITECUSTOMIZE_DIR
    else:
        python_path_env_var = '{}:{}'.format(SITECUSTOMIZE_DIR, python_path_env_var)
    session.run(
        *test_cmd,
        env={
            'PYTHONPATH': python_path_env_var,
            'COVERAGE_PROCESS_START': os.path.join(REPO_ROOT, '.coveragerc')
        }
    )
    session.run('coverage', 'combine')
    session.run('coverage', 'xml', '-o', os.path.join(REPO_ROOT, 'artifacts', 'coverage', 'coverage.xml'))


def _runtests(session, coverage, transport, cmd_args):
    # Create required artifacts directories
    _create_ci_directories()
    try:
        if coverage is True:
            _run_with_coverage(session, 'coverage', 'run', '-m', 'tests.runtests', *cmd_args)
        else:
            session.run('python', os.path.join('tests', 'runtests.py'), *cmd_args)
    except CommandFailed:
        session.log('Re-running failed tests if possible')
        names_file_path = os.path.join('artifacts', 'failed-tests.txt')
        session.install('xunitparser==1.3.3')
        session.run(
            'python',
            os.path.join('tests', 'support', 'generate-names-file-from-failed-test-reports.py'),
            names_file_path
        )
        if not os.path.exists(names_file_path):
            session.error('No names file was generated to re-run tests')

        with open(names_file_path) as rfh:
            failed_tests_count = len(rfh.read().splitlines())
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


@nox.session(python=_PYTHON_VERSIONS, name='runtests-parametrized')
@nox.parametrize('coverage', [False, True])
@nox.parametrize('transport', ['zeromq', 'raet'])
@nox.parametrize('crypto', [None, 'm2crypto', 'pycryptodomex'])
def runtests_parametrized(session, coverage, transport, crypto):
    # Install requirements
    _install_requirements(session, transport, 'unittest-xml-reporting==2.2.1')

    if crypto:
        if crypto == 'm2crypto':
            session.run('pip', 'uninstall', '-y', 'pycrypto', 'pycryptodome', 'pycryptodomex', silent=True)
        else:
            session.run('pip', 'uninstall', '-y', 'm2crypto', silent=True)
        session.install(crypto)

    cmd_args = [
        '--tests-logfile={}'.format(
            os.path.join(REPO_ROOT, 'artifacts', 'logs', 'runtests.log')
        ),
        '--transport={}'.format(transport)
    ] + session.posargs
    _runtests(session, coverage, transport, cmd_args)


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


@nox.session(python=_PYTHON_VERSIONS, name='pytest-parametrized')
@nox.parametrize('coverage', [False, True])
@nox.parametrize('transport', ['zeromq', 'raet'])
@nox.parametrize('crypto', [None, 'm2crypto', 'pycryptodomex'])
def pytest_parametrized(session, coverage, transport, crypto):
    # Install requirements
    _install_requirements(session, transport)

    if crypto:
        if crypto == 'm2crypto':
            session.run('pip', 'uninstall', '-y', 'pycrypto', 'pycryptodome', 'pycryptodomex', silent=True)
        else:
            session.run('pip', 'uninstall', '-y', 'm2crypto', silent=True)
        session.install(crypto)

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
    _pytest(session, coverage, transport, cmd_args)


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


def _pytest(session, coverage, transport, cmd_args):
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
