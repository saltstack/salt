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
try:
    # Python 2
    from StringIO import StringIO
except ImportError:
    # Python 3
    import io
    StringIO = io.StringIO


if __name__ == '__main__':
    sys.stderr.write('Do not execute this file directly. Use nox instead, it will know how to handle this file\n')
    sys.stderr.flush()
    exit(1)

# Import 3rd-party libs
import nox
from nox.command import CommandFailed


# ----- Helper Classes ---------------------------------------------------------------------------------------------->
class StdStream(StringIO):
    def __init__(self, std):
        StringIO.__init__(self)
        self._std = std

    def write(self, data):
        StringIO.write(self, data)
        self._std.write(data)


class CaptureSTDs(object):

    def __init__(self):
        self._stdout = StdStream(sys.stdout)
        self._stderr = StdStream(sys.stderr)
        self._sys_stdout = sys.stdout
        self._sys_stderr = sys.stderr

    def __enter__(self):
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        return self

    def __exit__(self, *args):
        sys.stdout = self._sys_stdout
        sys.stderr = self._sys_stderr

    @property
    def stdout(self):
        self._stdout.seek(0)
        return self._stdout.read()

    @property
    def stderr(self):
        self._stdout.seek(0)
        return self._stdout.read()
# <---- Helper Classes -----------------------------------------------------------------------------------------------


# Global Path Definitions
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SITECUSTOMIZE_DIR = os.path.join(REPO_ROOT, 'tests', 'support', 'coverage')
IS_WINDOWS = sys.platform.lower().startswith('win')

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


def _get_pydir(session):
    return 'py{}'.format(
        session.run(
            'python', '-c'
            'from __future__ import print_function; import sys; sys.stdout.write("{}.{}".format(*sys.version_info))',
            silent=True
        )
    )


def _install_requirements(session, transport, *extra_requirements):
    # Install requirements
    distro_requirements = None

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


def _lint(session, rcfile, flags, paths):
    _install_requirements(session, 'zeromq')
    _install_requirements(session, 'raet')
    session.install('-r', 'requirements/static/{}/lint.txt'.format(_get_pydir(session)))
    session.run('pylint', '--version')
    pylint_report_path = os.environ.get('PYLINT_REPORT')

    cmd_args = [
        'pylint',
        '--rcfile={}'.format(rcfile)
    ] + list(flags) + list(paths)

    try:
        with CaptureSTDs() as capstds:
            session.run(*cmd_args)
    except CommandFailed:
        if pylint_report_path:
            # Write report
            with open(pylint_report_path, 'w') as wfh:
                wfh.write(capstds.stdout)
            session.log('Report file written to %r', pylint_report_path)
        raise


@nox.session(python=_PYTHON_VERSIONS)
def lint(session):
    '''
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
    '''
    session.notify('lint-salt-{}'.format(session.python))
    session.notify('lint-tests-{}'.format(session.python))


@nox.session(python=_PYTHON_VERSIONS, name='lint-salt')
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


@nox.session(python=_PYTHON_VERSIONS, name='lint-tests')
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


@nox.session(python='2.7')
def docs(session):
    '''
    Build Salt's Documentation
    '''
    session.install('-r', 'requirements/static/py2.7/docs.txt')
    os.chdir('doc/')
    session.run('make', 'clean', external=True)
    session.run('make', 'html', external=True)
    session.run('tar', '-czvf', 'doc-archive.tar.gz', '_build/html')
    os.chdir('..')
