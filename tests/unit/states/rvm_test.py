# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
import salt.modules.rvm
import salt.states.rvm as rvm

rvm.__salt__ = {}
rvm.__opts__ = {'test': False}

salt.modules.rvm.__salt__ = {
    'cmd.has_exec': MagicMock(return_value=True),
    'config.option': MagicMock(return_value=None)
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestRvmState(TestCase):

    def test__check_rvm(self):
        mock = MagicMock(return_value=True)
        with patch.dict(
            rvm.__salt__,
            {'rvm.is_installed': MagicMock(return_value=False),
             'rvm.install': mock}):
            rvm._check_rvm({'changes': {}})
            # rvm.install is not run anymore while checking rvm.is_installed
            self.assertEqual(mock.call_count, 0)

    def test__check_and_install_ruby(self):
        mock_check_rvm = MagicMock(
            return_value={'changes': {}, 'result': True})
        mock_check_ruby = MagicMock(
            return_value={'changes': {}, 'result': False})
        mock_install_ruby = MagicMock(return_value='')
        with patch.object(rvm, '_check_rvm', new=mock_check_rvm):
            with patch.object(rvm, '_check_ruby', new=mock_check_ruby):
                with patch.dict(rvm.__salt__,
                                {'rvm.install_ruby': mock_install_ruby}):
                    rvm._check_and_install_ruby({'changes': {}}, '1.9.3')
        mock_install_ruby.assert_called_once_with('1.9.3', runas=None)

    def test__check_ruby(self):
        mock = MagicMock(return_value=[['ruby', '1.9.3-p125', False],
                                       ['jruby', '1.6.5.1', True]])
        with patch.dict(rvm.__salt__, {'rvm.list': mock}):
            for ruby, result in {'1.9.3': True,
                                 'ruby-1.9.3': True,
                                 'ruby-1.9.3-p125': True,
                                 '1.9.3-p125': True,
                                 '1.9.3-p126': False,
                                 'rbx': False,
                                 'jruby': True,
                                 'jruby-1.6.5.1': True,
                                 'jruby-1.6': False,
                                 'jruby-1.9.3': False,
                                 'jruby-1.9.3-p125': False}.items():
                ret = rvm._check_ruby({'changes': {}, 'result': False}, ruby)
                self.assertEqual(result, ret['result'])

    def test_gemset_present(self):
        with patch.object(rvm, '_check_rvm') as mock_method:
            mock_method.return_value = {'result': True, 'changes': {}}
            gems = ['global', 'foo', 'bar']
            gemset_list = MagicMock(return_value=gems)
            gemset_create = MagicMock(return_value=True)
            check_ruby = MagicMock(
                return_value={'result': False, 'changes': {}})
            with patch.object(rvm, '_check_ruby', new=check_ruby):
                with patch.dict(rvm.__salt__,
                                {'rvm.gemset_list': gemset_list,
                                 'rvm.gemset_create': gemset_create}):
                    ret = rvm.gemset_present('foo')
                    self.assertEqual(True, ret['result'])

                    ret = rvm.gemset_present('quux')
                    self.assertEqual(True, ret['result'])
                    gemset_create.assert_called_once_with(
                        'default', 'quux', runas=None)

    def test_installed(self):
        mock = MagicMock()
        with patch.object(rvm, '_check_rvm') as mock_method:
            mock_method.return_value = {'result': True}
            with patch.object(rvm, '_check_and_install_ruby', new=mock):
                rvm.installed('1.9.3', default=True)
        mock.assert_called_once_with(
            {'result': True}, '1.9.3', True, user=None)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestRvmState, needs_daemon=False)
