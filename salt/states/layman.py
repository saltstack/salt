# -*- coding: utf-8 -*-
'''
Management of Gentoo Overlays using layman
==========================================

A state module to manage Gentoo package overlays via layman

.. code-block:: yaml

    sunrise:
        layman.present
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    '''
    Only load if the layman module is available in __salt__
    '''
    return 'layman' if 'layman.add' in __salt__ else False


def present(name):
    '''
    Verify that the overlay is present

    name
        The name of the overlay to add
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Overlay already present
    if name in __salt__['layman.list_local']():
        ret['comment'] = 'Overlay {0} already present'.format(name)
    elif __opts__['test']:
        ret['comment'] = 'Overlay {0} is set to be added'.format(name)
        ret['result'] = None
        return ret
    else:
        # Does the overlay exist?
        if name not in __salt__['layman.list_all']():
            ret['comment'] = 'Overlay {0} not found'.format(name)
            ret['result'] = False
        else:
            # Attempt to add the overlay
            changes = __salt__['layman.add'](name)

            # The overlay failed to add
            if len(changes) < 1:
                ret['comment'] = 'Overlay {0} failed to add'.format(name)
                ret['result'] = False
            # Success
            else:
                ret['changes']['added'] = changes
                ret['comment'] = 'Overlay {0} added.'.format(name)

    return ret


def absent(name):
    '''
    Verify that the overlay is absent

    name
        The name of the overlay to delete
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Overlay is already absent
    if name not in __salt__['layman.list_local']():
        ret['comment'] = 'Overlay {0} already absent'.format(name)
    elif __opts__['test']:
        ret['comment'] = 'Overlay {0} is set to be deleted'.format(name)
        ret['result'] = None
        return ret
    else:
        # Attempt to delete the overlay
        changes = __salt__['layman.delete'](name)

        # The overlay failed to delete
        if len(changes) < 1:
            ret['comment'] = 'Overlay {0} failed to delete'.format(name)
            ret['result'] = False
        # Success
        else:
            ret['changes']['deleted'] = changes
            ret['comment'] = 'Overlay {0} deleted.'.format(name)

    return ret
