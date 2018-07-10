# coding=utf-8
'''
Get default scenario of the support.
'''
from __future__ import print_function, unicode_literals, absolute_import
import yaml
import os


def get_scenario(scenario='default'):
    scenario_path = os.path.join(os.path.dirname(__file__), 'scenarios', scenario + '.yml')
    if os.path.exists(scenario_path):
        data = yaml.load(open(scenario_path))
    else:
        data = {}

    return data
