# -*- coding: utf-8 -*-
'''
Managing Images in OpenStack Glance
===================================
'''
# Import python libs
import logging

log = logging.getLogger(__name__)

def image_present(name, visibility=None, protected=None):
    '''
    Checks if given image is present with properties
    set as specified.

    Supported properties:
      - visibility ('public' or 'private')
      - protected (bool)
    '''
    ret = {'name': name,
            'changes': {},
            'result': True,
            'comment': '',
            }

    images_dict = __salt__['glance.image_list'](name=name)
    log.debug('Got images_dict: {0}'.format(images_dict))
    if len(images_dict) == 1 and 'images' in images_dict:
        images_dict = images_dict['images']

    if len(images_dict) == 0:
        ret['result'] = False
        ret['comment'] = 'No image with name "{0}"'.format(name)
    elif len(images_dict) == 1:
        if len(images_dict) == 1:
            image = images_dict[images_dict.keys()[0]]
        else:
            image = images_dict[0]
        if visibility and image['visibility'] != visibility:
            ret['result'] = False
            ret['comment'] += '"visibility" is {0}, should be {1}'.format(
                image['visibility'], visibility)
        if protected is not None and image['protected'] ^ protected:
            ret['result'] = False
            ret['comment'] += '"protected" is {0}, should be {1}'.format(
                image['protected'], protected)
    else:
        raise NotImplementedError
    return ret
