# coding=utf-8
'''
Get default scenario of the support.
'''
from __future__ import print_function, unicode_literals, absolute_import
import yaml
import os
import salt.exceptions


def get_profile(profile):
    '''
    Get profile.

    :param profile:
    :return:
    '''
    profiles = profile.split(',')
    data = {}
    for profile in profiles:
        if os.path.basename(profile) == profile:
            profile = profile.split('.')[0]  # Trim extension if someone added it
            profile_path = os.path.join(os.path.dirname(__file__), 'profiles', profile + '.yml')
        else:
            profile_path = profile
        if os.path.exists(profile_path):
            data.update(yaml.load(open(profile_path)))
        else:
            raise salt.exceptions.SaltException('Profile "{}" is not found.'.format(profile))

    return data


def get_profiles(config):
    '''
    Get available profiles.

    :return:
    '''
    profiles = []
    for profile_name in os.listdir(os.path.join(os.path.dirname(__file__), 'profiles')):
        profiles.append(profile_name.split('.')[0])

    return sorted(profiles)
