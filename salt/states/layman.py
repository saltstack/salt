'''
Mangement of Gentoo Overlays using layman
=========================================

A state module to manage Gentoo package overlays via layman

.. code-block:: yaml

    sunrise:
        layman.added
'''

def added(name):
    '''
    Verify that the overlay has been added.

    name
        The name of the overlay to add
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Overlay already added
    if name in __salt__['layman.list_local']():
        ret['comment'] = 'Overlay {0} already added'.format(name)
    else:
        # Attempt to add the overlay
        changes = __salt__['layman.add'](name)

        # The overlay failed to add
        if len(changes) < 1:
            ret['comment'] = 'Overlay {0} failed to add'.format(name)
            ret['result'] = False
        # Sucess
        else:
            ret['changes']['added'] = changes
            ret['comment'] = 'Overlay {0} added.'.format(name)

    return ret

def deleted(name):
    '''
    Verify that the overlay has been removed.

    name
        The name of the overlay to delete
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Overlay already added
    if name not in __salt__['layman.list_local']():
        ret['comment'] = 'Overlay {0} already deleted'.format(name)
    else:
        # Attempt to delete the overlay
        changes = __salt__['layman.delete'](name)

        # The overlay failed to delete
        if len(changes) < 1:
            ret['comment'] = 'Overlay {0} failed to delete'.format(name)
            ret['result'] = False
        # Sucess
        else:
            ret['changes']['deleted'] = changes
            ret['comment'] = 'Overlay {0} deleted.'.format(name)

    return ret
