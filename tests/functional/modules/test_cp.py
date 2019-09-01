# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import hashlib
import logging

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS

# Import 3rd party libs
import pytest
import salt.ext.six as six

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

log = logging.getLogger(__name__)


SSL3_SUPPORT = sys.version_info >= (2, 7, 9)


def test_get_file(modules):
    '''
    cp.get_file
    '''
    with pytest.helpers.temp_file('scene33') as path:
        ret = modules.cp.get_file('salt://grail/scene33', path)
        assert ret == path
        assert os.path.isfile(path)
        with salt.utils.files.fopen(path, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert 'KNIGHT:  They\'re nervous, sire.' in data
        assert 'bacon' not in data


def test_get_file_to_dir(modules):
    '''
    cp.get_file
    '''
    with pytest.helpers.temp_directory() as tgt:
        path = os.path.join(tgt, 'scene33')
        ret = modules.cp.get_file('salt://grail/scene33', tgt)
        assert ret == path
        assert os.path.isfile(path)
        with salt.utils.files.fopen(path, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert 'KNIGHT:  They\'re nervous, sire.' in data
        assert 'bacon' not in data


def test_get_file_templated_paths(modules):
    '''
    cp.get_file
    '''
    with pytest.helpers.temp_file('cheese') as path:
        ret = modules.cp.get_file('salt://{{grains.test_grain}}',
                                  path.replace('cheese', '{{grains.test_grain}}'),
                                  template='jinja')
        assert ret == path
        assert os.path.isfile(path)
        with salt.utils.files.fopen(path, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert 'Gromit' in data
        assert 'bacon' not in data


def test_get_file_gzipped(modules):
    '''
    cp.get_file
    '''
    src = os.path.join(RUNTIME_VARS.FILES, 'file', 'base', 'file.big')
    with salt.utils.files.fopen(src, 'rb') as fp_:
        hash_str = hashlib.md5(fp_.read()).hexdigest()

    with pytest.helpers.temp_file('scene33') as path:
        ret = modules.cp.get_file('salt://file.big', path, gzip=5)
        assert ret == path
        with salt.utils.files.fopen(path, 'rb') as scene:
            data = scene.read()
        assert hashlib.md5(data).hexdigest() == hash_str
        data = salt.utils.stringutils.to_unicode(data)
        assert 'KNIGHT:  They\'re nervous, sire.' in data
        assert 'bacon' not in data


def test_get_file_makedirs(modules):
    '''
    cp.get_file
    '''
    with pytest.helpers.temp_directory('make') as path:
        tgt = os.path.join(path, 'dirs', 'scene33')
        ret = modules.cp.get_file('salt://grail/scene33', tgt, makedirs=True)
        assert ret == tgt
        assert os.path.isfile(tgt)
        with salt.utils.files.fopen(tgt, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert 'KNIGHT:  They\'re nervous, sire.' in data
        assert 'bacon' not in data


def test_get_template(modules):
    '''
    cp.get_template
    '''
    with pytest.helpers.temp_file('scene33') as path:
        ret = modules.cp.get_template('salt://grail/scene33', path, spam='bacon')
        assert ret == path
        assert os.path.isfile(path)
        with salt.utils.files.fopen(path, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert 'bacon' in data
        assert 'spam' not in data


def test_get_dir(modules):
    '''
    cp.get_dir
    '''
    with pytest.helpers.temp_directory('many') as path:
        ret = modules.cp.get_dir('salt://grail', path)
        assert ret != []
        assert 'grail' in os.listdir(path)
        assert '36' in os.listdir(os.path.join(path, 'grail'))
        assert 'empty' in os.listdir(os.path.join(path, 'grail'))
        assert 'scene' in os.listdir(os.path.join(path, 'grail', '36'))


def test_get_dir_templated_paths(modules):
    '''
    cp.get_dir
    '''
    with pytest.helpers.temp_directory('many') as path:
        ret = modules.cp.get_dir('salt://{{grains.script}}',
                                 path.replace('many', '{{grains.alot}}'),
                                 template='jinja')
        assert ret != []
        assert 'grail' in os.listdir(path)
        assert '36' in os.listdir(os.path.join(path, 'grail'))
        assert 'empty' in os.listdir(os.path.join(path, 'grail'))
        assert 'scene' in os.listdir(os.path.join(path, 'grail', '36'))


# cp.get_url tests


def test_get_url(modules):
    '''
    cp.get_url with salt:// source given
    '''
    with pytest.helpers.temp_file('scene33') as path:
        ret = modules.cp.get_url('salt://grail/scene33', path)
        assert ret == path
        assert os.path.isfile(path)
        with salt.utils.files.fopen(path, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert 'KNIGHT:  They\'re nervous, sire.' in data
        assert 'bacon' not in data


def test_get_url_makedirs(modules):
    '''
    cp.get_url
    '''
    with pytest.helpers.temp_directory('make') as path:
        tgt = os.path.join(path, 'dirs', 'scene33')
        ret = modules.cp.get_url('salt://grail/scene33', tgt, makedirs=True)
        assert ret == tgt
        assert os.path.isfile(tgt)
        with salt.utils.files.fopen(tgt, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert 'KNIGHT:  They\'re nervous, sire.' in data
        assert 'bacon' not in data


def test_get_url_dest_empty(modules):
    '''
    cp.get_url with salt:// source given and destination omitted.
    '''
    ret = modules.cp.get_url('salt://grail/scene33')
    try:
        assert os.path.isfile(ret)
        with salt.utils.files.fopen(ret, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert 'KNIGHT:  They\'re nervous, sire.' in data
        assert 'bacon' not in data
    finally:
        os.unlink(ret)


def test_get_url_no_dest(modules):
    '''
    cp.get_url with salt:// source given and destination set as None
    '''
    ret = modules.cp.get_url('salt://grail/scene33', None)
    assert isinstance(ret, six.text_type)
    assert 'KNIGHT:  They\'re nervous, sire.' in ret
    assert 'bacon' not in ret


def test_get_url_nonexistent_source(modules):
    '''
    cp.get_url with nonexistent salt:// source given
    '''
    ret = modules.cp.get_url('salt://grail/nonexistent_scene', None)
    assert ret is False
    ret = modules.cp.get_url('salt://grail/nonexistent_scene')
    assert ret is False


def test_get_url_to_dir(modules):
    '''
    cp.get_url with salt:// source
    '''
    with pytest.helpers.temp_directory() as tgt:
        path = os.path.join(tgt, 'scene33')
        ret = modules.cp.get_url('salt://grail/scene33', tgt)
        assert ret == path
        assert os.path.isfile(path)
        with salt.utils.files.fopen(path, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        assert 'KNIGHT:  They\'re nervous, sire.' in data
        assert 'bacon' not in data


@pytest.mark.skipif(SSL3_SUPPORT is False, reason='Requires python with SSL3 support')
@pytest.mark.requires_network
def test_get_url_https(modules):
    '''
    cp.get_url with https:// source given
    '''
    with pytest.helpers.temp_file('index.html') as path:
        ret = modules.cp.get_url('https://repo.saltstack.com/index.html', path)
        assert ret == path
        with salt.utils.files.fopen(path, 'r') as instructions:
            data = salt.utils.stringutils.to_unicode(instructions.read())
        assert 'Bootstrap' in data
        assert 'Debian' in data
        assert 'Windows' in data
        assert 'AYBABTU' not in data


@pytest.mark.skipif(SSL3_SUPPORT is False, reason='Requires python with SSL3 support')
@pytest.mark.requires_network
def test_get_url_https_empty_dest(modules):
    '''
    cp.get_url with https:// source given and destination omitted.
    '''
    path = modules.cp.get_url('https://repo.saltstack.com/index.html')
    try:
        with salt.utils.files.fopen(path, 'r') as instructions:
            data = salt.utils.stringutils.to_unicode(instructions.read())
        assert 'Bootstrap' in data
        assert 'Debian' in data
        assert 'Windows' in data
        assert 'AYBABTU' not in data
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.mark.skipif(SSL3_SUPPORT is False, reason='Requires python with SSL3 support')
@pytest.mark.requires_network
def test_get_url_https_no_dest(modules):
    '''
    cp.get_url with https:// source given and destination set as None
    '''
    data = modules.cp.get_url('https://repo.saltstack.com/index.html', None)
    assert 'Bootstrap' in data
    assert 'Debian' in data
    assert 'Windows' in data
    assert 'AYBABTU' not in data


def test_get_url_file(modules):
    '''
    cp.get_url with file:// source given
    '''
    src = os.path.join('file://', RUNTIME_VARS.FILES, 'file', 'base', 'file.big')
    path = modules.cp.get_url(src)
    with salt.utils.files.fopen(path, 'r') as scene:
        data = salt.utils.stringutils.to_unicode(scene.read())
    assert 'KNIGHT:  They\'re nervous, sire.' in data
    assert 'bacon' not in data


def test_get_url_file_no_dest(modules):
    '''
    cp.get_url with file:// source given and destination set as None
    '''
    src = os.path.join('file://', RUNTIME_VARS.FILES, 'file', 'base', 'file.big')
    ret = modules.cp.get_url(src, None)
    assert 'KNIGHT:  They\'re nervous, sire.' in ret
    assert 'bacon' not in ret


# cp.get_file_str tests


def test_get_file_str_salt(modules):
    '''
    cp.get_file_str with salt:// source given
    '''
    src = 'salt://grail/scene33'
    ret = modules.cp.get_file_str(src)
    assert 'KNIGHT:  They\'re nervous, sire.' in ret


def test_get_file_str_nonexistent_source(modules):
    '''
    cp.get_file_str with nonexistent salt:// source given
    '''
    src = 'salt://grail/nonexistent_scene'
    ret = modules.cp.get_file_str(src)
    assert ret is False


@pytest.mark.skipif(SSL3_SUPPORT is False, reason='Requires python with SSL3 support')
@pytest.mark.requires_network
def test_get_file_str_https(modules):
    '''
    cp.get_file_str with https:// source given
    '''
    src = 'https://repo.saltstack.com/index.html'
    data = modules.cp.get_file_str(src)
    assert 'Bootstrap' in data
    assert 'Debian' in data
    assert 'Windows' in data
    assert 'AYBABTU' not in data


def test_get_file_str_local(modules):
    '''
    cp.get_file_str with file:// source given
    '''
    src = os.path.join('file://', RUNTIME_VARS.FILES, 'file', 'base', 'file.big')
    ret = modules.cp.get_file_str(src)
    assert 'KNIGHT:  They\'re nervous, sire.' in ret
    assert 'bacon' not in ret


def test_list_states(modules):
    '''
    cp.list_states
    '''
    top_sls_contents = '''
    base:
      '*':
        - core
    '''
    core_sls_contents = '''
    # Goes nowhere, does nothing.
    gndn:
      test.succeed_with_changes
    '''
    with pytest.helpers.temp_state_file('top.sls', top_sls_contents):
        with pytest.helpers.temp_state_file('core.sls', core_sls_contents):
            ret = modules.cp.list_states()
            assert 'top' in ret
            assert 'core' in ret


def test_envs(modules):
    assert sorted(modules.cp.envs()) == sorted(['base', 'prod'])
