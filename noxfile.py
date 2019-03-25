# -*- coding: utf-8 -*-
'''
noxfile
~~~~~~~

Nox configuration script
'''

# Import Python libs
import os
import sys
import json

if __name__ == '__main__':
    sys.stderr.write('Do not execute this file directly. Use nox instead, it will know how to handle this file\n')
    sys.stderr.flush()
    exit(1)

# Import 3rd-party libs
import nox

# Global Path Definitions
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SITECUSTOMIZE_DIR = os.path.join(REPO_ROOT, 'tests', 'support', 'coverage')

# We can't just import salt because if this is running under a frozen nox, there
# will be no salt to import
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


def _install_requirements_overrides(session, *extra_requirements):
    session.install('distro')
    output = session.run('distro', '-j', silent=True)
    distro_data = json.loads(output.strip())

    requirements_overrides = REQUIREMENTS_OVERRIDES[None]
    requirements_overrides.extend(
        REQUIREMENTS_OVERRIDES.get(
            '{id}-{version}'.format(**distro_data),
            []
        )
    )
    if requirements_overrides:
        for requirement in requirements_overrides:
            session.install(requirement)


def _install_requirements(session, *extra_requirements):
    _install_requirements_overrides(session)
    # Install requirements
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

    if IS_WINDOWS:
        # Windows hacks :/
        nox_windows_setup = os.path.join(REPO_ROOT, 'tests', 'support', 'nox-windows-setup.py')
        session.run('python', nox_windows_setup)


def _run_with_coverage(session, *test_cmd):
    session.install('coverage')
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


@nox.session(python=_PYTHON_VERSIONS)
@nox.parametrize('coverage', [False, True])
def runtests(session, coverage):
    # Install requirements
    _install_requirements(session, 'unittest-xml-reporting')
    # Create required artifacts directories
    _create_ci_directories()

    cmd_args = [
        '-v',
        '--tests-logfile={}'.format(
            os.path.join(REPO_ROOT, 'artifacts', 'logs', 'runtests.log')
        )
    ] + session.posargs

    if coverage is True:
        _run_with_coverage(session, 'coverage', 'run', '-m', 'tests.runtests', *cmd_args)
    else:
        session.run('python', os.path.join('tests', 'runtests.py'), *cmd_args)


@nox.session(python=_PYTHON_VERSIONS)
@nox.parametrize('coverage', [False, True])
def pytest(session, coverage):
    # Install requirements
    _install_requirements(session)
    # Create required artifacts directories
    _create_ci_directories()

    cmd_args = [
        '--rootdir', REPO_ROOT,
        '--log-file={}'.format(
            os.path.join(REPO_ROOT, 'artifacts', 'logs', 'runtests.log')
        ),
        '--no-print-logs',
        '-ra',
        '-sv'
    ] + session.posargs

    if coverage is True:
        _run_with_coverage(session, 'coverage', 'run', '-m', 'py.test', *cmd_args)
    else:
        session.run('py.test', *cmd_args)
