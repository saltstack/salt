# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.states.pip_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin, SaltReturnAssertsMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.states.pip_state as pip_state
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
try:
    import pip
    HAS_PIP = True
except ImportError:
    HAS_PIP = False


log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PIP,
        'The \'pip\' library is not importable(installed system-wide)')
class PipStateTest(TestCase, SaltReturnAssertsMixin, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {
            pip_state: {
                '__env__': 'base',
                '__opts__': {'test': False},
                '__salt__': {'cmd.which_bin': lambda _: 'pip'}
            }
        }

    def test_install_requirements_parsing(self):
        log.debug("Real pip version is %s", pip.__version__)
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={'pep8': '1.3.3'})
        pip_version = pip.__version__
        mock_pip_version = MagicMock(return_value=pip_version)
        with patch.dict(pip_state.__salt__, {'pip.version': mock_pip_version}):
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list}):
                with patch.dict(pip_state.__opts__, {'test': True}):
                    log.debug(
                        'pip_state._from_line globals: %s',
                        [name for name in pip_state._from_line.__globals__]
                    )
                    ret = pip_state.installed('pep8=1.3.2')
                    self.assertSaltFalseReturn({'test': ret})
                    self.assertInSaltComment(
                        'Invalid version specification in package pep8=1.3.2. '
                        '\'=\' is not supported, use \'==\' instead.',
                        {'test': ret})

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'pep8': '1.3.3'})
            pip_install = MagicMock(return_value={'retcode': 0})
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list,
                                                 'pip.install': pip_install}):
                with patch.dict(pip_state.__opts__, {'test': True}):
                    ret = pip_state.installed('pep8>=1.3.2')
                    self.assertSaltTrueReturn({'test': ret})
                    self.assertInSaltComment(
                        'Python package pep8>=1.3.2 was already installed',
                        {'test': ret}
                    )

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'pep8': '1.3.3'})
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list}):
                with patch.dict(pip_state.__opts__, {'test': True}):
                    ret = pip_state.installed('pep8<1.3.2')
                    self.assertSaltNoneReturn({'test': ret})
                    self.assertInSaltComment(
                        'Python package pep8<1.3.2 is set to be installed',
                        {'test': ret}
                    )

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'pep8': '1.3.2'})
            pip_install = MagicMock(return_value={'retcode': 0})
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list,
                                                 'pip.install': pip_install}):
                with patch.dict(pip_state.__opts__, {'test': True}):
                    ret = pip_state.installed('pep8>1.3.1,<1.3.3')
                    self.assertSaltTrueReturn({'test': ret})
                    self.assertInSaltComment(
                        'Python package pep8>1.3.1,<1.3.3 was already installed',
                        {'test': ret}
                    )

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'pep8': '1.3.1'})
            pip_install = MagicMock(return_value={'retcode': 0})
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list,
                                                 'pip.install': pip_install}):
                with patch.dict(pip_state.__opts__, {'test': True}):
                    ret = pip_state.installed('pep8>1.3.1,<1.3.3')
                    self.assertSaltNoneReturn({'test': ret})
                    self.assertInSaltComment(
                        'Python package pep8>1.3.1,<1.3.3 is set to be installed',
                        {'test': ret}
                    )

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'pep8': '1.3.1'})
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list}):
                with patch.dict(pip_state.__opts__, {'test': True}):
                    ret = pip_state.installed(
                        'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting>=0.5.1'
                    )
                    self.assertSaltNoneReturn({'test': ret})
                    self.assertInSaltComment(
                        'Python package git+https://github.com/saltstack/'
                        'salt-testing.git#egg=SaltTesting>=0.5.1 is set to be '
                        'installed',
                        {'test': ret}
                    )

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'pep8': '1.3.1'})
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list}):
                with patch.dict(pip_state.__opts__, {'test': True}):
                    ret = pip_state.installed(
                        'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
                    )
                    self.assertSaltNoneReturn({'test': ret})
                    self.assertInSaltComment(
                        'Python package git+https://github.com/saltstack/'
                        'salt-testing.git#egg=SaltTesting is set to be '
                        'installed',
                        {'test': ret}
                    )

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'pep8': '1.3.1'})
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list}):
                with patch.dict(pip_state.__opts__, {'test': True}):
                    ret = pip_state.installed(
                        'https://pypi.python.org/packages/source/S/SaltTesting/'
                        'SaltTesting-0.5.0.tar.gz'
                        '#md5=e6760af92b7165f8be53b5763e40bc24'
                    )
                    self.assertSaltNoneReturn({'test': ret})
                    self.assertInSaltComment(
                        'Python package https://pypi.python.org/packages/source/'
                        'S/SaltTesting/SaltTesting-0.5.0.tar.gz'
                        '#md5=e6760af92b7165f8be53b5763e40bc24 is set to be '
                        'installed',
                        {'test': ret}
                    )

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'SaltTesting': '0.5.0'})
            pip_install = MagicMock(return_value={
                'retcode': 0,
                'stderr': '',
                'stdout': 'Downloading/unpacking https://pypi.python.org/packages'
                          '/source/S/SaltTesting/SaltTesting-0.5.0.tar.gz\n  '
                          'Downloading SaltTesting-0.5.0.tar.gz\n  Running '
                          'setup.py egg_info for package from '
                          'https://pypi.python.org/packages/source/S/SaltTesting/'
                          'SaltTesting-0.5.0.tar.gz\n    \nCleaning up...'
            })
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list,
                                                 'pip.install': pip_install}):
                ret = pip_state.installed(
                    'https://pypi.python.org/packages/source/S/SaltTesting/'
                    'SaltTesting-0.5.0.tar.gz'
                    '#md5=e6760af92b7165f8be53b5763e40bc24'
                )
                self.assertSaltTrueReturn({'test': ret})
                self.assertInSaltComment('All packages were successfully installed',
                    {'test': ret}
                )
                self.assertInSaltReturn(
                    'Installed',
                    {'test': ret},
                    ('changes', 'https://pypi.python.org/packages/source/S/'
                                'SaltTesting/SaltTesting-0.5.0.tar.gz'
                                '#md5=e6760af92b7165f8be53b5763e40bc24==???')
                )

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'SaltTesting': '0.5.0'})
            pip_install = MagicMock(return_value={
                'retcode': 0,
                'stderr': '',
                'stdout': 'Cloned!'
            })
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list,
                                                 'pip.install': pip_install}):
                with patch.dict(pip_state.__opts__, {'test': False}):
                    ret = pip_state.installed(
                        'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
                    )
                    self.assertSaltTrueReturn({'test': ret})
                    self.assertInSaltComment(
                        'packages are already installed',
                        {'test': ret}
                    )

            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'pep8': '1.3.1'})
            pip_install = MagicMock(return_value={'retcode': 0})
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list,
                                                 'pip.install': pip_install}):
                with patch.dict(pip_state.__opts__, {'test': False}):
                    ret = pip_state.installed(
                        'arbitrary ID that should be ignored due to requirements specified',
                        requirements='/tmp/non-existing-requirements.txt'
                    )
                    self.assertSaltTrueReturn({'test': ret})

            # Test VCS installations using git+git://
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            pip_list = MagicMock(return_value={'SaltTesting': '0.5.0'})
            pip_install = MagicMock(return_value={
                'retcode': 0,
                'stderr': '',
                'stdout': 'Cloned!'
            })
            with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                                 'pip.list': pip_list,
                                                 'pip.install': pip_install}):
                with patch.dict(pip_state.__opts__, {'test': False}):
                    ret = pip_state.installed(
                        'git+git://github.com/saltstack/salt-testing.git#egg=SaltTesting'
                    )
                    self.assertSaltTrueReturn({'test': ret})
                    self.assertInSaltComment(
                        'packages are already installed',
                        {'test': ret}
                    )

    def test_install_in_editable_mode(self):
        '''
        Check that `name` parameter containing bad characters is not parsed by
        pip when package is being installed in editable mode.
        For more information, see issue #21890.
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={})
        pip_install = MagicMock(return_value={
            'retcode': 0,
            'stderr': '',
            'stdout': 'Cloned!'
        })
        pip_version = MagicMock(return_value='10.0.1')
        with patch.dict(pip_state.__salt__, {'cmd.run_all': mock,
                                             'pip.list': pip_list,
                                             'pip.install': pip_install,
                                             'pip.version': pip_version}):
            ret = pip_state.installed('state@name',
                                      cwd='/path/to/project',
                                      editable=['.'])
            self.assertSaltTrueReturn({'test': ret})
            self.assertInSaltComment(
                'successfully installed',
                {'test': ret}
            )

    def test_mod_aggregate(self):
        '''
        Test to mod_aggregate function
        '''

        low = OrderedDict([('state', 'pip'),
                           ('name', 'ipython'),
                           ('__sls__', 'test.test_pip'),
                           ('__env__', 'base'),
                           ('__id__', 'ipython'),
                           ('order', 10000),
                           ('fun', 'installed')])
        chunks = [OrderedDict([('state', 'pip'),
                               ('name', 'ipython'),
                               ('__sls__', 'test.test_pip'),
                               ('__env__', 'base'),
                               ('__id__', 'ipython'),
                               ('order', 10000),
                               ('fun', 'installed')]),
                  OrderedDict([('state', 'pip'),
                               ('name', 'pylint'),
                               ('__sls__', 'test.test_pip'),
                               ('__env__', 'base'),
                               ('__id__', 'pylint'),
                               ('order', 10001),
                               ('fun', 'installed')])]
        running = {}
        expected_low = OrderedDict([('state', 'pip'),
                                    ('name', 'ipython'),
                                    ('__sls__', 'test.test_pip'),
                                    ('__env__', 'base'),
                                    ('__id__', 'ipython'),
                                    ('order', 10000),
                                    ('fun', 'installed'),
                                    ('pkgs', ['ipython', 'pylint'])])

        mock_tag = MagicMock(side_effect=['pip_|-ipython_|-ipython_|-installed',
                                          'pip_|-pylint_|-pylint_|-installed'])
        with patch.dict(pip_state.__utils__, {'state.gen_tag': mock_tag}):
            self.assertDictEqual(pip_state.mod_aggregate(low, chunks, running),
                                 expected_low)
