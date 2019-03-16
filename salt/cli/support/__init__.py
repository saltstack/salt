# coding=utf-8
'''
Get default scenario of the support.
'''
from __future__ import print_function, unicode_literals, absolute_import
import yaml
import os
import salt.exceptions
import jinja2
import logging

log = logging.getLogger(__name__)


def _render_profile(path, caller, runner):
    '''
    Render profile as Jinja2.
    :param path:
    :return:
    '''
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(path)), trim_blocks=False)
    return env.get_template(os.path.basename(path)).render(salt=caller, runners=runner).strip()


def get_profile(profile, caller, runner):
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
            try:
                rendered_template = _render_profile(profile_path, caller, runner)
                line = '-' * 80
                log.debug('\n%s\n%s\n%s\n', line, rendered_template, line)
                data.update(yaml.load(rendered_template))
            except Exception as ex:
                log.debug(ex, exc_info=True)
                raise salt.exceptions.SaltException('Rendering profile failed: {}'.format(ex))
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
        if profile_name.endswith('.yml'):
            profiles.append(profile_name.split('.')[0])

    return sorted(profiles)
