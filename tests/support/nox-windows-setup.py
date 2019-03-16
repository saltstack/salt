# -*- coding: utf-8 -*-
'''
    tests.support.nox-windows-setup
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This script is meant to run under the nox virtualenv to take care of required
    windows procedures
'''
# pylint: disable=resource-leakage

from __future__ import absolute_import, print_function, unicode_literals
import os
import re
import sys
import site
import shutil

try:
    import site
    SITE_PACKAGES = site.getsitepackages()
    PYTHON_EXECUTABLE_DIRECTORY = os.path.dirname(sys.executable)
    PYTHON_SCRIPTS_DIR = os.path.join(PYTHON_EXECUTABLE_DIRECTORY, 'Scripts')
except AttributeError:
    # The site module does not have the getsitepackages function when running within a virtualenv
    # But the site-packages directory WILL be on sys.path
    SITE_PACKAGES = None
    for entry in sys.path:
        if 'site-packages' in entry:
            SITE_PACKAGES = entry
            break
    # Under a virtualenv, the python "binary" is under Scripts already.
    # Well, not the binary, but the Python DLLs
    PYTHON_EXECUTABLE_DIRECTORY = PYTHON_SCRIPTS_DIR = os.path.dirname(sys.executable)

# Requests is a Salt dependency, it's safe to import, but...
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

IS_64_BITS = sys.maxsize > 2**32
SALT_REPO_URL = 'https://repo.saltstack.com/windows/dependencies/{}'.format(IS_64_BITS and 64 or 32)
DLLS = ("libeay32.dll", "ssleay32.dll", "OpenSSL_License.txt", "msvcr120.dll", "libsodium.dll")

for dll in DLLS:
    outfile = os.path.join(PYTHON_EXECUTABLE_DIRECTORY, dll)
    if os.path.exists(outfile):
        continue
    src_url = '{}/{}'.format(SALT_REPO_URL, dll)
    if HAS_REQUESTS:
        print('Downloading {} to {}'.format(src_url, outfile))
        request = requests.get(src_url, allow_redirects=True)
        with open(outfile, 'wb') as wfh:
            wfh.write(request.content)
    else:
        print('ATTENTION: The python requests package is not installed, can\'t download {}'.format(src_url))

PYWIN32_SYSTEM32_DIR = os.path.join(SITE_PACKAGES, 'pywin32_system32')
if os.path.exists(PYWIN32_SYSTEM32_DIR):
    for fname in os.listdir(PYWIN32_SYSTEM32_DIR):
        if not fname.endswith('.dll'):
            continue
        spath = os.path.join(PYWIN32_SYSTEM32_DIR, fname)
        dpath = spath.replace('pywin32_system32', 'win32')
        print('Moving {} to {}'.format(spath, dpath))
        shutil.move(spath, dpath)

    print('Deleting {}'.format(PYWIN32_SYSTEM32_DIR))
    shutil.rmtree(PYWIN32_SYSTEM32_DIR, ignore_errors=True)


if os.path.exists(PYTHON_SCRIPTS_DIR):
    print('Searching for pywin32 scripts to delete')
    for fname in os.listdir(PYTHON_SCRIPTS_DIR):
        if not fname.startswith('pywin32_'):
            continue
        fpath = os.path.join(PYTHON_SCRIPTS_DIR, fname)
        print('Deleting {}'.format(fpath))
        os.unlink(fpath)


PYTHONWIN_DIR = os.path.join(SITE_PACKAGES, 'pythonwin')
if os.path.exists(PYTHONWIN_DIR):
    print('Deleting {}'.format(PYTHONWIN_DIR))
    shutil.rmtree(PYTHONWIN_DIR, ignore_errors=True)

PYCRPTO_NT_FILE = os.path.join(SITE_PACKAGES, 'Crypto', 'Random', 'OSRNG', 'nt.py')
if os.path.exists(PYCRPTO_NT_FILE):
    with open(PYCRPTO_NT_FILE, 'r') as rfh:
        contents = rfh.read()
        new_contents = re.sub(
            r'^import winrandom$',
            'from Crypto.Random.OSRNG import winrandom',
            contents,
            count=1,
            flags=re.MULTILINE
        )
        if contents != new_contents:
            print('Patching {}'.format(PYCRPTO_NT_FILE))
            with open(PYCRPTO_NT_FILE, 'w') as wfh:
                wfh.write(new_contents)
