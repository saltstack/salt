'''
Import python module and call given method. The data returned from method is
overlaid onto the minion's pillar data. It allows user to define pillar
dynamically in the python code.
'''

import json
import logging


logger = logging.getLogger(__name__)


def ext_pillar(minion_id, pillar, name=None):
    '''
    Import given method by name and call it with
    data = {
        'id': minion_id,
        'grains': __grains__,
        'pillar': pillar,
        'opts': __opts__
    }
    '''
    modn = '.'.join(name.split('.')[:-1])
    methn = name.split('.')[-1]

    logger.debug('External pillar call: {0}.{1}'.format(modn, methn))

    try:
        module = __import__(modn, globals(), locals(), [methn], 0)
        method = getattr(module, methn)
    except Exception:
        logger.critical('External pillar failed to import {0}'.format(name))
        return {}

    try:
        data = {
            'id': minion_id,
            'grains': __grains__,
            'pillar': pillar,
            'opts': __opts__
        }
        return method(data)
    except Exception:
        logger.critical('External pillar "call" failed to get data')
        return {}
