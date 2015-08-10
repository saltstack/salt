# -*- coding: utf-8 -*-
'''
Generate the salt thin tarball from the installed python files
'''

# Import python libs
from __future__ import absolute_import

import os
import sys
import json
import shutil
import tarfile
import zipfile
import tempfile
import subprocess

# Import third party libs
import jinja2
import yaml
import salt.ext.six as six
import tornado
import msgpack

# pylint: disable=import-error,no-name-in-module
try:
    import certifi
    HAS_CERTIFI = True
except ImportError:
    HAS_CERTIFI = False

try:
    import markupsafe
    HAS_MARKUPSAFE = True
except ImportError:
    # Older jinja does not need markupsafe
    HAS_MARKUPSAFE = False

try:
    import xml
    HAS_XML = True
except ImportError:
    HAS_XML = False
# pylint: enable=import-error,no-name-in-module

try:
    # Older python where the backport from pypi is installed
    from backports import ssl_match_hostname
    HAS_SSL_MATCH_HOSTNAME = True
except ImportError:
    # Other older python we use our bundled copy
    try:
        from salt.ext import ssl_match_hostname
        HAS_SSL_MATCH_HOSTNAME = True
    except ImportError:
        HAS_SSL_MATCH_HOSTNAME = False

# Import salt libs
import salt
import salt.utils
import salt.exceptions

SALTCALL = '''
import os
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        'py{0[0]}'.format(sys.version_info)
    )
)

from salt.scripts import salt_call
if __name__ == '__main__':
    salt_call()
'''


def thin_path(cachedir):
    '''
    Return the path to the thin tarball
    '''
    return os.path.join(cachedir, 'thin', 'thin.tgz')


def get_tops(extra_mods='', so_mods=''):
    tops = [
            os.path.dirname(salt.__file__),
            os.path.dirname(jinja2.__file__),
            os.path.dirname(yaml.__file__),
            os.path.dirname(tornado.__file__),
            os.path.dirname(msgpack.__file__)
            ]

    tops.append(six.__file__.replace('.pyc', '.py'))

    if HAS_CERTIFI:
        tops.append(os.path.dirname(certifi.__file__))

    if HAS_SSL_MATCH_HOSTNAME:
        tops.append(os.path.dirname(os.path.dirname(ssl_match_hostname.__file__)))

    if HAS_XML:
        # For openSUSE, which apparently doesn't include the whole stdlib
        tops.append(os.path.dirname(xml.__file__))

    for mod in [m for m in extra_mods.split(',') if m]:
        if mod not in locals() and mod not in globals():
            try:
                locals()[mod] = __import__(mod)
                moddir, modname = os.path.split(locals()[mod].__file__)
                base, ext = os.path.splitext(modname)
                if base == '__init__':
                    tops.append(moddir)
                else:
                    tops.append(os.path.join(moddir, base + '.py'))
            except ImportError:
                # Not entirely sure this is the right thing, but the only
                # options seem to be 1) fail, 2) spew errors, or 3) pass.
                # Nothing else in here spits errors, and the markupsafe code
                # doesn't bail on import failure, so I followed that lead.
                # And of course, any other failure still S/T's.
                pass
    for mod in [m for m in so_mods.split(',') if m]:
        try:
            locals()[mod] = __import__(mod)
            tops.append(locals()[mod].__file__)
        except ImportError:
            pass   # As per comment above
    if HAS_MARKUPSAFE:
        tops.append(os.path.dirname(markupsafe.__file__))

    return tops


def gen_thin(cachedir, extra_mods='', overwrite=False, so_mods='',
             python2_bin='python2', python3_bin='python3'):
    '''
    Generate the salt-thin tarball and print the location of the tarball
    Optional additional mods to include (e.g. mako) can be supplied as a comma
    delimited string.  Permits forcing an overwrite of the output file as well.

    CLI Example:

    .. code-block:: bash

        salt-run thin.generate
        salt-run thin.generate mako
        salt-run thin.generate mako,wempy 1
        salt-run thin.generate overwrite=1
    '''
    thindir = os.path.join(cachedir, 'thin')
    if not os.path.isdir(thindir):
        os.makedirs(thindir)
    thintar = os.path.join(thindir, 'thin.tgz')
    thinver = os.path.join(thindir, 'version')
    pythinver = os.path.join(thindir, '.thin-gen-py-version')
    salt_call = os.path.join(thindir, 'salt-call')
    with salt.utils.fopen(salt_call, 'w+') as fp_:
        fp_.write(SALTCALL)
    if os.path.isfile(thintar):
        if not overwrite:
            if os.path.isfile(thinver):
                with salt.utils.fopen(thinver) as fh_:
                    overwrite = fh_.read() != salt.version.__version__
                if overwrite is False and os.path.isfile(pythinver):
                    with salt.utils.fopen(pythinver) as fh_:
                        overwrite = fh_.read() != str(sys.version_info[0])
            else:
                overwrite = True

        if overwrite:
            try:
                os.remove(thintar)
            except OSError:
                pass
        else:
            return thintar
    if six.PY3:
        # Let's check for the minimum python 2 version requirement, 2.6
        py_shell_cmd = (
            python2_bin + ' -c \'from __future__ import print_function; import sys; '
            'print("{0}.{1}".format(*(sys.version_info[:2])));\''
        )
        cmd = subprocess.Popen(py_shell_cmd, stdout=subprocess.PIPE, shell=True)
        stdout, _ = cmd.communicate()
        if cmd.returncode == 0:
            py2_version = tuple(int(n) for n in stdout.decode('utf-8').strip().split('.'))
            if py2_version < (2, 6):
                # Bail!
                raise salt.exceptions.SaltSystemExit(
                    'The minimum required python version to run salt-ssh is "2.6".'
                    'The version reported by "{0}" is "{1}". Please try "salt-ssh '
                    '--python2-bin=<path-to-python-2.6-binary-or-higher>".'.format(python2_bin,
                                                                                stdout.strip())
                )
    elif sys.version_info < (2, 6):
        # Bail! Though, how did we reached this far in the first place.
        raise salt.exceptions.SaltSystemExit(
            'The minimum required python version to run salt-ssh is "2.6".'
        )

    tops_py_version_mapping = {}
    tops = get_tops(extra_mods=extra_mods, so_mods=so_mods)
    if six.PY2:
        tops_py_version_mapping['2'] = tops
    else:
        tops_py_version_mapping['3'] = tops

    # TODO: Consider putting known py2 and py3 compatible libs in it's own sharable directory.
    #       This would reduce the thin size.
    if six.PY2 and sys.version_info[0] == 2:
        # Get python 3 tops
        py_shell_cmd = (
            python3_bin + ' -c \'import sys; import json; import salt.utils.thin; '
            'print(json.dumps(salt.utils.thin.get_tops(**(json.loads(sys.argv[1]))))); exit(0);\' '
            '\'{0}\''.format(json.dumps({'extra_mods': extra_mods, 'so_mods': so_mods}))
        )
        cmd = subprocess.Popen(py_shell_cmd, stdout=subprocess.PIPE, shell=True)
        stdout, stderr = cmd.communicate()
        if cmd.returncode == 0:
            try:
                tops = json.loads(stdout)
                tops_py_version_mapping['3'] = tops
            except ValueError:
                pass
    if six.PY3 and sys.version_info[0] == 3:
        # Get python 2 tops
        py_shell_cmd = (
            python2_bin + ' -c \'from __future__ import print_function; '
            'import sys; import json; import salt.utils.thin; '
            'print(json.dumps(salt.utils.thin.get_tops(**(json.loads(sys.argv[1]))))); exit(0);\' '
            '\'{0}\''.format(json.dumps({'extra_mods': extra_mods, 'so_mods': so_mods}))
        )
        cmd = subprocess.Popen(py_shell_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout, stderr = cmd.communicate()
        if cmd.returncode == 0:
            try:
                tops = json.loads(stdout.decode('utf-8'))
                tops_py_version_mapping['2'] = tops
            except ValueError:
                pass

    tfp = tarfile.open(thintar, 'w:gz', dereference=True)
    try:  # cwd may not exist if it was removed but salt was run from it
        start_dir = os.getcwd()
    except OSError:
        start_dir = None
    tempdir = None
    for py_ver, tops in six.iteritems(tops_py_version_mapping):
        for top in tops:
            base = os.path.basename(top)
            top_dirname = os.path.dirname(top)
            if os.path.isdir(top_dirname):
                os.chdir(top_dirname)
            else:
                # This is likely a compressed python .egg
                tempdir = tempfile.mkdtemp()
                egg = zipfile.ZipFile(top_dirname)
                egg.extractall(tempdir)
                top = os.path.join(tempdir, base)
                os.chdir(tempdir)
            if not os.path.isdir(top):
                # top is a single file module
                tfp.add(base, arcname=os.path.join('py{0}'.format(py_ver), base))
                continue
            for root, dirs, files in os.walk(base, followlinks=True):
                for name in files:
                    if not name.endswith(('.pyc', '.pyo')):
                        tfp.add(os.path.join(root, name),
                                arcname=os.path.join('py{0}'.format(py_ver), root, name))
            if tempdir is not None:
                shutil.rmtree(tempdir)
                tempdir = None
    os.chdir(thindir)
    tfp.add('salt-call')
    with salt.utils.fopen(thinver, 'w+') as fp_:
        fp_.write(salt.version.__version__)
    with salt.utils.fopen(pythinver, 'w+') as fp_:
        fp_.write(str(sys.version_info[0]))
    os.chdir(os.path.dirname(thinver))
    tfp.add('version')
    tfp.add('.thin-gen-py-version')
    if start_dir:
        os.chdir(start_dir)
    tfp.close()
    return thintar


def thin_sum(cachedir, form='sha1'):
    '''
    Return the checksum of the current thin tarball
    '''
    thintar = gen_thin(cachedir)
    return salt.utils.get_hash(thintar, form)
