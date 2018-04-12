# -*- coding: utf-8 -*-
'''
Functions to interact with the pillar compiler on the master
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.pillar
import salt.utils.minions


def show_top(minion=None, saltenv='base'):
    '''
    Returns the compiled top data for pillar for a specific minion.  If no
    minion is specified, we use the first minion we find.

    CLI Example:

    .. code-block:: bash

        salt-run pillar.show_top
    '''
    id_, grains, _ = salt.utils.minions.get_minion_data(minion, __opts__)
    pillar = salt.pillar.Pillar(
        __opts__,
        grains,
        id_,
        saltenv)

    top, errors = pillar.get_top()

    if errors:
        __jid_event__.fire_event({'data': errors, 'outputter': 'nested'}, 'progress')
        return errors

    return top


def show_pillar(minion='*', **kwargs):
    '''
    Returns the compiled pillar either of a specific minion
    or just the global available pillars. This function assumes
    that no minion has the id ``*``.
    Function also accepts pillarenv as attribute in order to limit to a specific pillar branch of git

    CLI Example:

    shows minion specific pillar:

    .. code-block:: bash

        salt-run pillar.show_pillar 'www.example.com'

    shows global pillar:

    .. code-block:: bash

        salt-run pillar.show_pillar

    shows global pillar for 'dev' pillar environment:
    (note that not specifying pillarenv will merge all pillar environments
    using the master config option pillar_source_merging_strategy.)

    .. code-block:: bash

        salt-run pillar.show_pillar 'pillarenv=dev'

    shows global pillar for 'dev' pillar environment and specific pillarenv = dev:

    .. code-block:: bash

        salt-run pillar.show_pillar 'saltenv=dev' 'pillarenv=dev'

    API Example:

    .. code-block:: python

        import salt.config
        import salt.runner
        opts = salt.config.master_config('/etc/salt/master')
        runner = salt.runner.RunnerClient(opts)
        pillar = runner.cmd('pillar.show_pillar', [])
        print(pillar)
    '''
    pillarenv = None
    saltenv = 'base'
    id_, grains, _ = salt.utils.minions.get_minion_data(minion, __opts__)
    if grains is None:
        grains = {'fqdn': minion}

    for key in kwargs:
        if key == 'saltenv':
            saltenv = kwargs[key]
        elif key == 'pillarenv':
            # pillarenv overridden on CLI
            pillarenv = kwargs[key]
        else:
            grains[key] = kwargs[key]

    pillar = salt.pillar.Pillar(
        __opts__,
        grains,
        id_,
        saltenv,
        pillarenv=pillarenv)

    compiled_pillar = pillar.compile_pillar()
    return compiled_pillar
