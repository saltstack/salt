# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Libs
import salt.modules.win_lgpo as win_lgpo

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)


class WinLgpoTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {win_lgpo: {
            '__context__': {}
        }}

    def test__set_netsh_value_firewall(self):
        context = {
            'lgpo.netsh_data': {
                'Private': {
                    'Inbound': 'Block'}}}
        expected = {
            'lgpo.netsh_data': {
                'Private': {
                    'Inbound': 'Allow'}}}
        with patch('salt.utils.win_lgpo_netsh.set_firewall_settings',
                   MagicMock(return_value=True)),\
                patch.dict(win_lgpo.__context__, context):
            result = win_lgpo._set_netsh_value(profile='Private',
                                               section='firewallpolicy',
                                               option='Inbound',
                                               value='Allow')
            self.assertTrue(result)
            self.assertEqual(win_lgpo.__context__, expected)

    def test__set_netsh_value_settings(self):
        context = {
            'lgpo.netsh_data': {
                'private': {
                    'localfirewallrules': 'disable'}}}
        expected = {
            'lgpo.netsh_data': {
                'private': {
                    'localfirewallrules': 'enable'}}}
        with patch('salt.utils.win_lgpo_netsh.set_settings',
                   MagicMock(return_value=True)), \
                patch.dict(win_lgpo.__context__, context):
            result = win_lgpo._set_netsh_value(profile='private',
                                               section='settings',
                                               option='localfirewallrules',
                                               value='enable')
            self.assertTrue(result)
            self.assertEqual(win_lgpo.__context__, expected)

    def test__set_netsh_value_state(self):
        context = {
            'lgpo.netsh_data': {
                'private': {
                    'State': 'notconfigured'}}}
        expected = {
            'lgpo.netsh_data': {
                'private': {
                    'State': 'on'}}}
        with patch('salt.utils.win_lgpo_netsh.set_state',
                   MagicMock(return_value=True)), \
                patch.dict(win_lgpo.__context__, context):
            result = win_lgpo._set_netsh_value(profile='private',
                                               section='state',
                                               option='unused',
                                               value='on')
            self.assertTrue(result)
            self.assertEqual(win_lgpo.__context__, expected)

    def test__set_netsh_value_logging(self):
        context = {
            'lgpo.netsh_data': {
                'private': {
                    'allowedconnections': 'notconfigured'}}}
        expected = {
            'lgpo.netsh_data': {
                'private': {
                    'allowedconnections': 'enable'}}}
        with patch('salt.utils.win_lgpo_netsh.set_logging_settings',
                   MagicMock(return_value=True)), \
                patch.dict(win_lgpo.__context__, context):
            result = win_lgpo._set_netsh_value(profile='private',
                                               section='logging',
                                               option='allowedconnections',
                                               value='enable')
            self.assertTrue(result)
            self.assertEqual(win_lgpo.__context__, expected)
