=========================================
Mod Aggregate State Runtime Modifications
=========================================

.. versionadded:: 2014.7.0

The mod_aggregate system was added in the 2014.7.0 release of Salt and allows for
runtime modification of the executing state data. Simply put, it allows for the
data used by Salt's state system to be changed on the fly at runtime, kind of
like a configuration management JIT compiler or a runtime import system. All in
all, it makes Salt much more dynamic.

How it Works
============

The best example is the ``pkg`` state. One of the major requests in Salt has long
been adding the ability to install all packages defined at the same time. The
mod_aggregate system makes this a reality. While executing Salt's state system,
when a ``pkg`` state is reached the ``mod_aggregate`` function in the state module
is called. For ``pkg`` this function scans all of the other states that are slated
to run, and picks up the references to ``name`` and ``pkgs``, then adds them to
``pkgs`` in the first state. The result is a single call to yum, apt-get,
pacman, etc as part of the first package install.

How to Use it
=============

.. note::

    Since this option changes the basic behavior of the state runtime, after
    it is enabled states should be executed using `test=True` to ensure that
    the desired behavior is preserved.

In config files
---------------

The first way to enable aggregation is with a configuration option in either
the master or minion configuration files. Salt will invoke ``mod_aggregate``
the first time it encounters a state module that has aggregate support.

If this option is set in the master config it will apply to all state runs on
all minions, if set in the minion config it will only apply to said minion.

Enable for all states:

.. code-block:: yaml

    state_aggregate: True

Enable for only specific state modules:

.. code-block:: yaml

    state_aggregate:
      - pkg

In states
---------

The second way to enable aggregation is with the state-level ``aggregate``
keyword. In this configuration, Salt will invoke the ``mod_aggregate`` function
the first time it encounters this keyword. Any additional occurrences of the
keyword will be ignored as the aggregation has already taken place.

The following example will trigger ``mod_aggregate`` when the ``lamp_stack``
state is processed resulting in a single call to the underlying package
manager.

.. code-block:: yaml

    lamp_stack:
      pkg.installed:
        - pkgs:
          - php
          - mysql-client
        - aggregate: True

    memcached:
      pkg.installed:
        - name: memcached

Adding mod_aggregate to a State Module
======================================

Adding a mod_aggregate routine to an existing state module only requires adding
an additional function to the state module called mod_aggregate.

The mod_aggregate function just needs to accept three parameters and return the
low data to use. Since mod_aggregate is working on the state runtime level it
does need to manipulate `low data`.

The three parameters are `low`, `chunks`, and `running`. The `low` option is the
low data for the state execution which is about to be called. The `chunks` is
the list of all of the low data dictionaries which are being executed by the
runtime and the `running` dictionary is the return data from all of the state
executions which have already be executed.

This example, simplified from the pkg state, shows how to create mod_aggregate functions:

.. code-block:: python

    def mod_aggregate(low, chunks, running):
        '''
        The mod_aggregate function which looks up all packages in the available
        low chunks and merges them into a single pkgs ref in the present low data
        '''
        pkgs = []
        # What functions should we aggregate?
        agg_enabled = [
                'installed',
                'latest',
                'removed',
                'purged',
                ]
        # The `low` data is just a dict with the state, function (fun) and
        # arguments passed in from the sls
        if low.get('fun') not in agg_enabled:
            return low
        # Now look into what other things are set to execute
        for chunk in chunks:
            # The state runtime uses "tags" to track completed jobs, it may
            # look familiar with the _|-
            tag = salt.utils.gen_state_tag(chunk)
            if tag in running:
                # Already ran the pkg state, skip aggregation
                continue
            if chunk.get('state') == 'pkg':
                if '__agg__' in chunk:
                    continue
                # Check for the same function
                if chunk.get('fun') != low.get('fun'):
                    continue
                # Pull out the pkg names!
                if 'pkgs' in chunk:
                    pkgs.extend(chunk['pkgs'])
                    chunk['__agg__'] = True
                elif 'name' in chunk:
                    pkgs.append(chunk['name'])
                    chunk['__agg__'] = True
        if pkgs:
            if 'pkgs' in low:
                low['pkgs'].extend(pkgs)
            else:
                low['pkgs'] = pkgs
        # The low has been modified and needs to be returned to the state
        # runtime for execution
        return low
