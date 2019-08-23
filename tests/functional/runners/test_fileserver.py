# -*- coding: utf-8 -*-
'''
Tests for the fileserver runner
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import contextlib

# Import 3rd-party libs
import pytest

log = logging.getLogger(__name__)


def test_dir_list(runners):
    '''
    fileserver.dir_list
    '''
    ret = runners.fileserver.dir_list()
    assert isinstance(ret, list)
    assert '_modules' in ret

    # Backend submitted as a string
    ret = runners.fileserver.dir_list(backend='roots')
    assert isinstance(ret, list)
    assert '_modules' in ret

    # Backend submitted as a list
    ret = runners.fileserver.dir_list(backend=['roots'])
    assert isinstance(ret, list)
    assert '_modules' in ret


def test_empty_dir_list(runners):
    '''
    fileserver.empty_dir_list
    '''
    ret = runners.fileserver.empty_dir_list()
    assert isinstance(ret, list)
    assert ret == []

    # Backend submitted as a string
    ret = runners.fileserver.empty_dir_list(backend='roots')
    assert isinstance(ret, list)
    assert ret == []

    # Backend submitted as a list
    ret = runners.fileserver.empty_dir_list(backend=['roots'])
    assert isinstance(ret, list)
    assert ret == []


def test_envs(runners):
    '''
    fileserver.envs
    '''
    ret = runners.fileserver.envs()
    assert isinstance(ret, list)
    assert ret == ['base', 'prod']

    # Backend submitted as a string
    ret = runners.fileserver.envs(backend='roots')
    assert isinstance(ret, list)
    assert ret == ['base', 'prod']

    # Backend submitted as a list
    ret = runners.fileserver.envs(backend=['roots'])
    assert isinstance(ret, list)
    assert ret == ['base', 'prod']


def test_clear_file_list_cache(runners):
    '''
    fileserver.clear_file_list_cache

    If this test fails, then something may have changed in the test suite
    and we may have more than just "roots" configured in the fileserver
    backends. This assert will need to be updated accordingly.
    '''
    saltenvs = sorted(runners.fileserver.envs())

    @contextlib.contextmanager
    def gen_cache():
        '''
        Create file_list cache so we have something to clear
        '''
        for saltenv in saltenvs:
            runners.fileserver.file_list(saltenv=saltenv)
        yield

    # Test with no arguments
    with gen_cache():
        ret = runners.fileserver.clear_file_list_cache()
        assert sorted(ret['roots']) == saltenvs

    # Test with backend passed as string
    with gen_cache():
        ret = runners.fileserver.clear_file_list_cache(backend='roots')
        assert sorted(ret['roots']) == saltenvs

    # Test with backend passed as list
    with gen_cache():
        ret = runners.fileserver.clear_file_list_cache(backend=['roots'])
        assert sorted(ret['roots']) == saltenvs

    # Test with backend passed as string, but with a nonsense backend
    with gen_cache():
        ret = runners.fileserver.clear_file_list_cache(backend='notarealbackend')
        assert ret == {}

    # Test with saltenv passed as string
    with gen_cache():
        ret = runners.fileserver.clear_file_list_cache(saltenv='base')
        assert ret['roots'] == ['base']

    # Test with saltenv passed as list
    with gen_cache():
        ret = runners.fileserver.clear_file_list_cache(saltenv=['base'])
        assert ret['roots'] == ['base']

    # Test with saltenv passed as string, but with a nonsense saltenv
    with gen_cache():
        ret = runners.fileserver.clear_file_list_cache(saltenv='notarealsaltenv')
        assert ret == {}

    # Test with both backend and saltenv passed
    with gen_cache():
        ret = runners.fileserver.clear_file_list_cache(backend='roots', saltenv=['base'])
        assert ret['roots'] == ['base']


def test_file_list(runners):
    '''
    fileserver.file_list
    '''
    ret = runners.fileserver.file_list()
    assert isinstance(ret, list)
    assert 'grail/scene33' in ret

    # Backend submitted as a string
    ret = runners.fileserver.file_list(backend='roots')
    assert isinstance(ret, list)
    assert 'grail/scene33' in ret

    # Backend submitted as a list
    ret = runners.fileserver.file_list(backend=['roots'])
    assert isinstance(ret, list)
    assert 'grail/scene33' in ret


# Git doesn't handle symlinks in Windows. See the thread below:
# http://stackoverflow.com/questions/5917249/git-symlinks-in-windows
@pytest.mark.skipif('grains["os"] == "Windows"',
                    reason='Git for Windows does not preserve symbolic links when cloning')
def test_symlink_list(runners):
    '''
    fileserver.symlink_list
    '''
    ret = runners.fileserver.symlink_list()
    assert isinstance(ret, dict)
    assert 'dest_sym' in ret

    # Backend submitted as a string
    ret = runners.fileserver.symlink_list(backend='roots')
    assert isinstance(ret, dict)
    assert 'dest_sym' in ret

    # Backend submitted as a list
    ret = runners.fileserver.symlink_list(backend=['roots'])
    assert isinstance(ret, dict)
    assert 'dest_sym' in ret


def test_update(runners):
    '''
    fileserver.update
    '''
    assert runners.fileserver.update() is True

    # Backend submitted as a string
    assert runners.fileserver.update(backend='roots') is True

    # Backend submitted as a list
    assert runners.fileserver.update(backend=['roots']) is True
