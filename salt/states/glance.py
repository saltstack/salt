# -*- coding: utf-8 -*-
'''
Managing Images in OpenStack Glance
===================================
'''
# Import python libs
import logging, time

log = logging.getLogger(__name__)

def _find_image(name):
    '''
    Tries to find image with given name, returns
        - image, 'Found image <name>'
        - None, 'No such image found'
        - False, 'Found more than one image with given name'
    '''
    images_dict = __salt__['glance.image_list'](name=name)
    log.debug('Got images_dict: {0}'.format(images_dict))

    if len(images_dict) == 1 and 'images' in images_dict:
        images_dict = images_dict['images']

    if len(images_dict) == 0:
        return None, 'No image with name "{0}"'.format(name)
    elif len(images_dict) == 1:
        return images_dict.values()[0], 'Found image {0}'.format(name)
    elif len(images_dict) > 1:
        return False, 'Found more than one image with given name'
    else:
        raise NotImplementedError


def image_present(name, visibility='public', protected=None,
        checksum=None, location=None, wait_for=None, timeout=30):
    '''
    Checks if given image is present with properties
    set as specified.

    An image should got through the stages 'queued', 'saving'
    before becoming 'active'. The attribute 'checksum' can
    only be checked once the image is active.
    If you don't specify 'wait_for' but 'checksum' the function
    will wait for the image to become active before comparing
    checksums. If you don't specify checksum either the function
    will return when the image reached 'saving'.
    The default timeout for both is 30 seconds.

    Supported properties:
      - visibility ('public' or 'private')
      - protected (bool)
      - checksum (string, md5sum)
      - location (URL, to copy from)
    '''
    ret = {'name': name,
            'changes': {},
            'result': True,
            'comment': '',
            }
    acceptable = ['queued', 'saving', 'active']
    if wait_for is None and checksum is None:
        wait_for = 'saving'
    elif wait_for is None and checksum is not None:
        wait_for = 'active'

    # Just pop states until we reach the
    # first acceptable one:
    while len(acceptable) > 0:
        if acceptable[0] == wait_for:
            break
        else:
            acceptable.pop(0)

    image, msg = _find_image(name)
    log.debug(msg)
    # No image yet and we know where to get one
    if image is None and location is not None:
        image = __salt__['glance.image_create'](name=name,
            protected=protected, visibility=visibility,
            location=location)
        if image.keys()[0] == name:
            image = image.values()[0]
        log.debug('Created new image:\n{0}'.format(image))
        ret['changes'] = {
            name:
                {
                    'new':
                        {
                        'id': image['id']
                        },
                    'old': None
                }
            }
        timer = timeout
        if image.keys()[0] == name:
            image = image.values()[0]
        # Kinda busy-loopy but I don't think the Glance
        # API has events we can listen for
        while timer > 0:
            if image.has_key('status') and \
                    image['status'] in acceptable:
                log.debug('Image {0} has reached status {1}'.format(
                    image['name'], image['status']))
                break
            else:
                timer -= 5
                time.sleep(5)
                image, msg = _find_image(name)
                if not image:
                    ret['result'] = False
                    ret['comment'] += 'Created image {0} '.format(
                        name) + ' vanished:\n' + msg
                    return ret
                elif image.keys()[0] == name:
                    image = image.values()[0]
        if timer <= 0 and image['status'] not in acceptable:
            ret['result'] = False
            ret['comment'] += 'Image didn\'t reach an acceptable '+\
                    'state ({0}) before timeout:\n'.format(acceptable)+\
                    '\tLast status was "{0}".\n'.format(image['status'])

        # Wrapped dict workaround (see Salt issue #24568)
        if name in image:
            image = image[name]
            # ret[comment] +=

    # There's no image but where would I get one??
    elif location is None:
        ret['result'] = False
        ret['comment'] = 'No location to copy image from specified,\n' +\
                         'not creating a new image.'
        return ret

    # If we've created a new image also return its last status:
    if ret['changes'].has_key(name):
        ret['changes'][name]['new']['status'] = image['status']

    if visibility:
        if image['visibility'] != visibility:
            ret['result'] = False
            ret['comment'] += '"visibility" is {0}, should be {1}.\n'.format(
                image['visibility'], visibility)
        else:
            ret['comment'] += '"visibility" is correct ({0}).\n'.format(
                visibility)
    if protected is not None:
        if not isinstance(protected, bool) or image['protected'] ^ protected:
            ret['result'] = False
            ret['comment'] += '"protected" is {0}, should be {1}.\n'.format(
                image['protected'], protected)
        else:
            ret['comment'] += '"protected" is correct ({0}).\n'.format(
                protected)
    if image.has_key('status') and checksum:
        if image['status'] == 'active':
            if not image.has_key('checksum'):
                ret['result'] = False
                ret['comment'] += 'No checksum available for this image:\n' +\
                        '\tImage has status "{0}".'.format(image['status'])
            elif image['checksum'] != checksum:
                ret['result'] = False
                ret['comment'] += '"checksum" is {0}, should be {1}.\n'.format(
                    image['checksum'], checksum)
            else:
                ret['comment'] += '"checksum" is correct ({0}).\n'.format(
                    checksum)
        elif image['status'] in ['saving', 'queued']:
            ret['comment'] += 'Checksum won\'t be verified as image ' +\
                'hasn\'t reached\n\t "status=active" yet.\n'
    log.debug('glance.image_present will return: {0}'.format(ret))
    return ret
