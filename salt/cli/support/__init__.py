# coding=utf-8
'''
Get default scenario of the support.
'''
from __future__ import print_function, unicode_literals, absolute_import
import yaml
import os


def get_profile(scenario='default'):
    profile_path = os.path.join(os.path.dirname(__file__), 'profiles', scenario + '.yml')
    if os.path.exists(profile_path):
        data = yaml.load(open(profile_path))
    else:
        data = {}

    return data
