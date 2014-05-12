# -*- coding: utf-8 -*-
'''
Functions to interact with the pillar compiler on the master
'''

# Import salt libs
import salt.pillar
import salt.utils.minions
import salt.output


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
        salt.output.display_output(errors, 'nested', __opts__)
        return errors

    salt.output.display_output(top, 'nested', __opts__)
    return top


def show_pillar(minion='*', **kwargs):
    '''
    Returns the compiled pillar either of a specific minion
    or just the global available pillars. I assume that no minion
    is using the id ``*``.

    CLI Example:

    shows minion specific pillar:

    .. code-block:: bash

        salt-run pillar.show_pillar 'www.example.com'

    shows global pillar:

    .. code-block:: bash

        salt-run pillar.show_pillar

    shows global pillar for 'dev' pillar environment:

    .. code-block:: bash

        salt-run pillar.show_pillar 'saltenv=dev'

    API Example:

    .. code-block:: python

        import salt.config
        import salt.runner
        opts = salt.config.master_config('/etc/salt/master')
        runner = salt.runner.RunnerClient(opts)
        pillar = runner.cmd('pillar.show_pillar', [])
        print pillar¬
    '''

    saltenv = 'base'
    id_, grains, _ = salt.utils.minions.get_minion_data(minion, __opts__)
    if grains is None:
        grains = {'fqdn': minion}

    for key in kwargs:
        if key == 'saltenv':
            saltenv = kwargs[key]
        else:
            grains[key] = kwargs[key]

    pillar = salt.pillar.Pillar(
        __opts__,
        grains,
        id_,
        saltenv)

    compiled_pillar = pillar.compile_pillar()
    salt.output.display_output(compiled_pillar, 'nested', __opts__)
    return compiled_pillar
