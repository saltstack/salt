# -*- coding: utf-8 -*-
'''
Managing implicit state and baselines using snapshots
=====================================================

Salt can manage state against explicitly defined state, for example
if your minion state is defined by:

.. code-block:: yaml

   /etc/config_file:
     file.managed:
       - source: salt://configs/myconfig

If someone modifies this file, the next application of the highstate will
allow the admin to correct this deviation and the file will be corrected.

Now, what happens if somebody creates a file ``/etc/new_config_file`` and
deletes ``/etc/important_config_file``? Unless you have a explicit rule, this
change will go unnoticed.

The snapper state module allows you to manage state implicitly, in addition
to explicit rules, in order to define a baseline and iterate with explicit
rules as they show that they work in production.

The workflow is: once you have a workin and audited system, you would create
your baseline snapshot (eg. with ``salt tgt snapper.create_snapshot``) and
define in your state this baseline using the identifier of the snapshot
(in this case: 20):

.. code-block:: yaml

    my_baseline:
      snapper.baseline_snapshot:
        - number: 20
        - ignore:
          - /var/log
          - /var/cache


If you have this state, and you haven't done changes to the system since the
snapshot, and you add a user, the state will show you the changes (including
full diffs) to ``/etc/passwd``, ``/etc/shadow``, etc if you call it
with ``test=True`` and will undo all changes if you call it without.

This allows you to add more explicit state knowing that you are starting from a
very well defined state, and that you can audit any change that is not part
of your explicit configuration.

So after you made this your state, you decided to introduce a change in your
configuration:

.. code-block:: yaml

    my_baseline:
      snapper.baseline_snapshot:
        - number: 20
        - ignore:
          - /var/log
          - /var/cache

    hosts_entry:
      file.blockreplace:
        - name: /etc/hosts
        - content: 'First line of content'
        - append_if_not_found: True


The change in ``/etc/hosts`` will be done after any other change that deviates
from the specified snapshot are reverted. This could be for example,
modifications to the ``/etc/passwd`` file or changes in the ``/etc/hosts``
that could render your the ``hosts_entry`` rule void or dangerous.

Once you take a new snapshot and you update the baseline snapshot number to
include the change in ``/etc/hosts`` the ``hosts_entry`` rule will basically
do nothing. You are free to leave it there for documentation, to ensure that
the change is made in case the snapshot is wrong, but if you remove anything
that comes after the ``snapper.baseline_snapshot`` as it will have no effect:
 by the moment the state is evaluated, the baseline state was already applied
and include this change.

.. warning::
    Make sure you specify the baseline state before other rules, otherwise
    the baseline state will revert all changes if they are not present in
    the snapshot.

.. warning::
    Do not specify more than one baseline rule as only the last one will
    affect the result.

:codeauthor:    Duncan Mac-Vicar P. <dmacvicar@suse.de>
:codeauthor:    Pablo Suarez Hernandez <psuarezhernandez@suse.de>
:maturity:      new
:platform:      Linux

'''
import logging
import os

log = logging.getLogger(__name__)


def __virtual__():
    return True


def baseline_snapshot(name, number=None, config='root', ignore=[]):
    '''
    Enforces that no file is modified comparing against a previously
    defined snapshot identified by number.

    ignore
        List of files to ignore
    '''

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if number is None:
        ret.update({'result': False,
                    'comment': 'Snapshot number needs to be specified'})
        return ret

    status = __salt__['snapper.status'](
        config, num_pre=number, num_post=0)

    for f in ignore:
        if os.path.isfile(f):
            status.pop(f, None)
        elif os.path.isdir(f):
            [status.pop(x, None) for x in status.keys() if x.startswith(f)]

    for f in status:
        status[f]['actions'] = status[f].pop("status")

        # Only include diff for modified files
        if "modified" in status[f]['actions']:
            status[f].update(__salt__['snapper.diff'](config,
                                                      num_pre=0,
                                                      num_post=number, filename=f)[f])

    if __opts__['test'] and status:
        ret['pchanges'] = ret["changes"]
        ret['changes'] = {}
        ret['comment'] = "{0} files changes are set to be undone".format(len(status.keys()))
        ret['result'] = None
    elif __opts__['test'] and not status:
        ret['changes'] = {}
        ret['comment'] = "Nothing to be done"
        ret['result'] = True
    elif not __opts__['test'] and status:
        undo = __salt__['snapper.undo'](config, num_pre=number, num_post=0,
                                        files=status.keys())
        ret['changes']['sumary'] = undo
        ret['changes']['files'] = status
        ret['result'] = True
    else:
        ret['comment'] = "No changes were done"
        ret['result'] = True

    return ret
