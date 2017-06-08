# -*- coding: utf-8 -*-
"""
Pass Renderer for Salt

[pass](https://www.passwordstore.org/)

.. versionadded:: Nitrogen

# Setup
__Note__: `<user>` needs to be replaced with the user salt-master will be
running as

1. Have private gpg loaded into `user`'s gpg keyring
   * Example salt code
        ```
        load_private_gpg_key:
          cmd.run:
            - name: gpg --import <location_of_private_gpg_key>
            - unless: gpg --list-keys '<gpg_name>'
        ```
1. Said private key's public key should have been used when encrypting pass
entries that are of interest for pillar data
1. Fetch and keep local pass git repo up-to-date
   * Example salt code
        ```
        update_pass:
          git.latest:
            - force_reset: True
            - name: <git_repo>
            - target: /<user>/.password-store
            - identity: <location_of_ssh_private_key>
            - require:
              - cmd: load_private_gpg_key
        ```
1. Install pass binary
   * Example salt code
        ```
        pass:
          pkg.installed
        ```
"""

# Import python libs
from __future__ import absolute_import
import logging
import os
from os.path import expanduser
from subprocess import Popen, PIPE

# Import salt libs
import salt.utils
from salt.exceptions import SaltRenderError

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


def _get_pass_exec():
    """
    Return the pass executable or raise an error
    """
    pass_exec = salt.utils.which('pass')
    if pass_exec:
        return pass_exec
    else:
        raise SaltRenderError('pass unavailable')


def _fetch_secret(pass_path):
    """
    Fetch secret from pass based on pass_path. If there is
    any error, return back the original pass_path value
    """
    cmd = "pass show {0}".format(pass_path.strip())
    log.debug('Fetching secret: {0}'.format(cmd))

    proc = Popen(cmd.split(' '), stdout=PIPE, stderr=PIPE)
    pass_data, pass_error = proc.communicate()

    # The version of pass used during development sent output to
    # stdout instead of stderr even though its returncode was non zero.
    if proc.returncode or not pass_data:
        log.warning('Could not fetch secret: %s %s', pass_data, pass_error)
        pass_data = pass_path
    return pass_data.strip()


def _decrypt_object(obj):
    """
    Recursively try to find a pass path (string) that can be handed off to pass
    """
    if isinstance(obj, six.string_types):
        return _fetch_secret(obj)
    elif isinstance(obj, dict):
        for pass_key, pass_path in six.iteritems(obj):
            obj[pass_key] = _decrypt_object(pass_path)
    elif isinstance(obj, list):
        for pass_key, pass_path in enumerate(obj):
            obj[pass_key] = _decrypt_object(pass_path)
    return obj


def render(pass_info, saltenv='base', sls='', argline='', **kwargs):
    """
    Fetch secret from pass based on pass_path
    """
    try:
        _get_pass_exec()
    except SaltRenderError:
        raise

    # Make sure environment variable HOME is set, since Pass looks for the
    # password-store under ~/.password-store.
    os.environ['HOME'] = expanduser('~')
    return _decrypt_object(pass_info)
