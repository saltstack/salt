# -*- coding: utf-8 -*-
'''
Network Config
==============

Manage the configuration on a network device given a specific static config or template.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`
- :mod:`Network-related basic features execution module <salt.modules.napalm_network>`

.. versionadded: 2016.11.1
'''


from __future__ import absolute_import

import logging
log = logging.getLogger(__name__)

# third party libs
try:
    # will try to import NAPALM
    # https://github.com/napalm-automation/napalm
    # pylint: disable=W0611
    from napalm_base import get_network_driver
    # pylint: enable=W0611
    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False

# ----------------------------------------------------------------------------------------------------------------------
# state properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'netconfig'

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():

    '''
    NAPALM library must be installed for this module to work.
    Also, the key proxymodule must be set in the __opts___ dictionary.
    '''

    if HAS_NAPALM and 'proxy' in __opts__:
        return __virtualname__
    else:
        return (False, 'The network config state (netconfig) cannot be loaded: \
                NAPALM or proxy could not be loaded.')

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _default_ret(name):

    ret = {
        'name': name,
        'changes': {},
        'already_configured': False,
        'loaded_config': '',
        'result': False,
        'comment': ''
    }
    return ret


def _update_config(template_name,
                   template_source=None,
                   template_path=None,
                   template_hash=None,
                   template_hash_name=None,
                   template_user='root',
                   template_group='root',
                   template_mode='755',
                   saltenv=None,
                   template_engine='jinja',
                   skip_verify=True,
                   defaults=None,
                   test=False,
                   commit=True,
                   debug=False,
                   replace=False,
                   **template_vars):

    return __salt__['net.load_template'](template_name,
                                         template_source=template_source,
                                         template_path=template_path,
                                         template_hash=template_hash,
                                         template_hash_name=template_hash_name,
                                         template_user=template_user,
                                         template_group=template_group,
                                         template_mode=template_mode,
                                         saltenv=saltenv,
                                         template_engine=template_engine,
                                         skip_verify=skip_verify,
                                         defaults=defaults,
                                         test=test,
                                         commit=commit,
                                         debug=debug,
                                         replace=replace,
                                         **template_vars)

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def managed(name,
            template_name,
            template_source=None,
            template_path=None,
            template_hash=None,
            template_hash_name=None,
            template_user='root',
            template_group='root',
            template_mode='755',
            saltenv=None,
            template_engine='jinja',
            skip_verify=True,
            defaults=None,
            test=False,
            commit=True,
            debug=False,
            replace=False,
            **template_vars):

    '''
    Manages the configuration on network devices.

    By default this function will commit the changes. If there are no changes, it does not commit and
    the flag ``already_configured`` will be set as ``True`` to point this out.
    To avoid committing the configuration, set the argument ``test`` to ``True`` (or via the CLI argument ``test=True``)
    and will discard (dry run).
    To keep the chnages but not commit, set ``commit`` to ``False``. However, this is not recommeded to be used withinn
    the state as it can lead to preserving the configuration DB locked and a unused candidate buffer.
    To replace the config, set ``replace`` to ``True``.

    template_name
        Identifies the template name. If specifies the complete path, will render the template via

    template_source: None
        Inline config template to be rendered and loaded on the device.

    template_path: None
        Specifies the absolute path to a the template directory.

    template_hash: None
        Hash of the template file. Format: ``{hash_type: 'md5', 'hsum': <md5sum>}``

    template_hash_name: None
        When ``template_hash`` refers to a remote file, this specifies the filename to look for in that file.

    template_group: root
        Owner of file.

    template_user: root
        Group owner of file.

    template_user: 755
        Permissions of file

    saltenv: base
        Specifies the template environment. This will influence the relative imports inside the templates.
        .. versionadded:: 2016.11.1
    template_engine: jinja
        The following templates engines are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

    skip_verify: True
        If ``True``, hash verification of remote file sources (``http://``, ``https://``, ``ftp://``) will be skipped,
        and the ``source_hash`` argument will be ignored.

    test: False
        Dry run? If set to ``True``, will apply the config, discard and return the changes. Default: ``False``
        and will commit the changes on the device.

    commit: True
        Commit? (default: ``True``) Sometimes it is not needed to commit the config immediately
        after loading the changes. E.g.: a state loads a couple of parts (add / remove / update)
        and would not be optimal to commit after each operation.
        Also, from the CLI when the user needs to apply the similar changes before committing,
        can specify ``commit=False`` and will not discard the config.

    debug: False
        Debug mode. Will insert a new key under the output dictionary, as ``loaded_config`` contaning the raw
        result after the template was rendered.

    replace: False
        Load and replace the configuration.

    defaults: None
        Default variables/context passed to the template.

    **template_vars
        Dictionary with the arguments/context to be used when the template is rendered.

    SLS Example (e.g.: under salt://router/config.sls) :

    .. code-block:: yaml

        whole_config_example:
            netconfig.managed:
                - template_name: salt://path/to/complete_config.jinja
                - debug: True
                - replace: True
        bgp_config_example:
            netconfig.managed:
                - template_name: /absolute/path/to/bgp_neighbors.mako
                - template_engine: mako
        prefix_lists_example:
            netconfig.managed:
                - template_name: prefix_lists.jinja
                - template_path: /absolute/path/to/
                - debug: True
        ntp_peers_example:
            netconfig.managed:
                - template_name: http://bit.ly/2gKOj20
                - skip_verify: False
                - debug: True
                - template_vars:
                    peers:
                        - 192.168.0.1
                        - 192.168.0.1
        ntp_peers_example_using_pillar:
            netconfig.managed:
                - template_name: http://bit.ly/2gKOj20
                - debug: True
                - template_vars:
                    peers: {{ pillar.get('ntp.peers', []) }}

    Usage examples:

    .. code-block:: bash

        $ sudo salt 'juniper.device' state.sls router.config test=True

        $ sudo salt -N all-routers state.sls router.config debug=True

    ``router.config`` depends on the location of the SLS file (see above). Running this command, will be executed all
    five steps from above. These examples above are not meant to be used in a production environment, their sole purpose
    is to provide usage examples.

    :return: a dictionary having the following keys:

    * result (bool): if the config was applied successfully. It is ``False`` only in case of failure. In case \
    there are no changes to be applied and successfully performs all operations it is still ``True`` and so will be \
    the ``already_configured`` flag (example below)
    * comment (str): a message for the user
    * already_configured (bool): flag to check if there were no changes applied
    * loaded_config (str): the configuration loaded on the device, after rendering the template. Requires ``debug`` \
    to be set as ``True``
    * diff (str): returns the config changes applied

    Output example:

    .. code-block:: bash

        $ sudo salt 'juniper.device' state.sls router.config test=True
        juniper.device:
        ----------
                  ID: ntp_peers_example_using_pillar
            Function: netconfig.managed
              Result: None
             Comment: Testing mode: Configuration discarded.
             Started: 12:01:40.744535
            Duration: 8755.788 ms
             Changes:
                      ----------
                      diff:
                          [edit system ntp]
                               peer 192.168.0.1 { ... }
                          +    peer 172.17.17.1;
                          +    peer 172.17.17.3;

        Summary for juniper.device
        ------------
        Succeeded: 1 (unchanged=1, changed=1)
        Failed:    0
        ------------
        Total states run:     1
        Total run time:   8.756 s

    Raw output example (useful when the output is reused in other states/execution modules):

    .. code-block:: python

        $ sudo salt --out=pprint 'juniper.device' state.sls router.config test=True
        {
            'juniper.device': {
                'netconfig_|-ntp_peers_example_using_pillar_|-ntp_peers_example_using_pillar_|-managed': {
                    '__id__': 'ntp_peers_example_using_pillar',
                    '__run_num__': 0,
                    'already_configured': False,
                    'changes': {
                    'diff':
                        '[edit system ntp]     peer 192.168.0.1 { ... }+    peer 172.17.17.1;+    peer 172.17.17.3;'
                    },
                    'comment': 'Testing mode: Configuration discarded.',
                    'duration': 7400.759,
                    'loaded_config': 'system {\n  ntp {\n  peer 172.17.17.1;\n  peer 172.17.17.3;\n}\n}\n',
                    'name': 'ntp_peers_example_using_pillar',
                    'result': None,
                    'start_time': '12:09:09.811445'
                }
            }
        }
    '''

    ret = _default_ret(name)

    # the user can override the flags the equivalent CLI args
    # which have higher precedence
    test = __opts__.get('test', test)
    debug = __opts__.get('debug', debug)
    commit = __opts__.get('commit', commit)
    replace = __opts__.get('replace', replace)  # this might be a bit risky
    skip_verify = __opts__.get('skip_verify', skip_verify)

    config_update_ret = _update_config(template_name,
                                       template_source=template_source,
                                       template_path=template_path,
                                       template_hash=template_hash,
                                       template_hash_name=template_hash_name,
                                       template_user=template_user,
                                       template_group=template_group,
                                       template_mode=template_mode,
                                       saltenv=saltenv,
                                       template_engine=template_engine,
                                       skip_verify=skip_verify,
                                       defaults=defaults,
                                       test=test,
                                       commit=commit,
                                       debug=debug,
                                       replace=replace,
                                       **template_vars)

    _apply_res = config_update_ret.get('result', False)
    result = (_apply_res if not _apply_res else None) if test else _apply_res
    _comment = config_update_ret.get('comment', '')
    comment = _comment if not test else 'Testing mode: {tail}'.format(tail=_comment)

    if result is True and not comment:
        comment = 'Configuration changed!'

    ret.update({
        'changes': {
            'diff': config_update_ret.get('diff', '')
        },
        'already_configured': config_update_ret.get('already_configured', False),
        'result': result,
        'comment': comment,
        'loaded_config': config_update_ret.get('loaded_config', ''),
    })

    return ret
