import sys
import os
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from saltunittest import TestCase, TestLoader, TextTestRunner, skipIf
try:
    from mock import MagicMock, patch
    has_mock = True
except ImportError:
    has_mock = False

if has_mock:
    import salt.modules.rvm as rvm
    rvm.__salt__ = {
        'cmd.has_exec': MagicMock(return_value=True)}


@skipIf(has_mock is False, "mock python module is unavailable")
class TestRvmModule(TestCase):

    def test__rvm(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(rvm.__salt__, {'cmd.run_all': mock}):
            rvm._rvm("install", "1.9.3")
            mock.assert_called_once_with(
                "/usr/local/rvm/bin/rvm install 1.9.3", runas=None
            )

    def test__rvm_do(self):
        mock = MagicMock(return_value=None)
        with patch.object(rvm, '_rvm', new=mock):
            rvm._rvm_do("1.9.3", "gemset list")
            mock.assert_called_once_with("1.9.3 do gemset list", runas=None)

    def test_install(self):
        mock = MagicMock(return_value=0)
        with patch.dict(rvm.__salt__, {'cmd.retcode': mock}):
            rvm.install()

    def test_list(self):
        list_output = '''
rvm rubies

   jruby-1.6.5.1 [ amd64 ]
   ree-1.8.7-2011.03 [ x86_64 ]
   ree-1.8.7-2011.12 [ x86_64 ]
=* ree-1.8.7-2012.02 [ x86_64 ]
   ruby-1.9.2-p180 [ x86_64 ]
   ruby-1.9.3-p125 [ x86_64 ]
   ruby-head [ x86_64 ]

# => - current
# =* - current && default
#  * - default

'''
        with patch.object(rvm, '_rvm') as mock_method:
            mock_method.return_value = list_output
            self.assertEqual(
                [['jruby', '1.6.5.1', False],
                 ['ree', '1.8.7-2011.03', False],
                 ['ree', '1.8.7-2011.12', False],
                 ['ree', '1.8.7-2012.02', True],
                 ['ruby', '1.9.2-p180', False],
                 ['ruby', '1.9.3-p125', False],
                 ['ruby', 'head', False]],
                rvm.list())

    def test_gemset_list(self):
        output = '''
gemsets for ree-1.8.7-2012.02 (found in /usr/local/rvm/gems/ree-1.8.7-2012.02)
   global
   bar
   foo

'''
        with patch.object(rvm, '_rvm_do') as mock_method:
            mock_method.return_value = output
            self.assertEqual(
                ['global', 'bar', 'foo'],
                rvm.gemset_list())

    def test_gemset_list_all(self):
        output = '''

gemsets for ruby-1.9.3-p125 (found in /usr/local/rvm/gems/ruby-1.9.3-p125)
   9bar
   9foo
   global


gemsets for ruby-head (found in /usr/local/rvm/gems/ruby-head)
   global
   headbar
   headfoo


gemsets for jruby-1.6.5.1 (found in /usr/local/rvm/gems/jruby-1.6.5.1)
   global
   jbar
   jfoo


gemsets for ruby-1.9.2-p180 (found in /usr/local/rvm/gems/ruby-1.9.2-p180)
   global


'''
        with patch.object(rvm, '_rvm_do') as mock_method:
            mock_method.return_value = output
            self.assertEqual(
                {'jruby-1.6.5.1': ['global', 'jbar', 'jfoo'],
                 'ruby-1.9.2-p180': ['global'],
                 'ruby-1.9.3-p125': ['9bar', '9foo', 'global'],
                 'ruby-head': ['global', 'headbar', 'headfoo']},
                rvm.gemset_list_all())

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(TestRvmModule)
    TextTestRunner(verbosity=1).run(tests)
