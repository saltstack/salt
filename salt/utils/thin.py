# -*- coding: utf-8 -*-
'''
Generate the salt thin tarball from the installed python files
'''

# Import python libs
from __future__ import absolute_import

import os
import shutil
import tarfile
import zipfile
import tempfile

# Import third party libs
import jinja2
import yaml
import salt.ext.six as six

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

SALTCALL = '''
from salt.scripts import salt_call
if __name__ == '__main__':
    salt_call()
'''


def thin_path(cachedir):
    '''
    Return the path to the thin tarball
    '''
    return os.path.join(cachedir, 'thin', 'thin.tgz')


def gen_thin(cachedir, extra_mods='', overwrite=False, so_mods=''):
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
    salt_call = os.path.join(thindir, 'salt-call')
    with salt.utils.fopen(salt_call, 'w+') as fp_:
        fp_.write(SALTCALL)
    if os.path.isfile(thintar):
        if not overwrite:
            if os.path.isfile(thinver):
                with salt.utils.fopen(thinver) as fh_:
                    overwrite = fh_.read() != salt.version.__version__
            else:
                overwrite = True

        if overwrite:
            try:
                os.remove(thintar)
            except OSError:
                pass
        else:
            return thintar

    tops = [
            os.path.dirname(salt.__file__),
            os.path.dirname(jinja2.__file__),
            os.path.dirname(yaml.__file__),
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
    tfp = tarfile.open(thintar, 'w:gz', dereference=True)
    try:  # cwd may not exist if it was removed but salt was run from it
        start_dir = os.getcwd()
    except OSError:
        start_dir = None
    tempdir = None
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
            tfp.add(base)
            continue
        for root, dirs, files in os.walk(base, followlinks=True):
            for name in files:
                if not name.endswith(('.pyc', '.pyo')):
                    tfp.add(os.path.join(root, name))
        if tempdir is not None:
            shutil.rmtree(tempdir)
            tempdir = None
    os.chdir(thindir)
    tfp.add('salt-call')
    with salt.utils.fopen(thinver, 'w+') as fp_:
        fp_.write(salt.version.__version__)
    os.chdir(os.path.dirname(thinver))
    tfp.add('version')
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
