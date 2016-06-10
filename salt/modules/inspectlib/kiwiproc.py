# -*- coding: utf-8 -*-
#
# Copyright 2016 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from lxml import etree
from xml.dom import minidom
import platform
import socket
from salt.modules.inspectlib.exceptions import InspectorKiwiProcessorException


class KiwiExporter(object):
    '''
    Exports system description as Kiwi configuration.
    '''
    def __init__(self, grains, format):
        self.__grains__ = grains
        self.format = format
        self._data = type('data', (), {})
        self.name = None

    def load(self, **descr):
        '''
        Load data by keys.

        :param data:
        :return:
        '''
        # self._data.configuration = {}
        # self._data.identity = {}
        # self._data.system = {}
        # self._data.software = {}
        # self._data.services = {}
        # self._data.payload = {}

        for obj, data in descr.items():
            setattr(self._data, obj, data)

    def export(self, name):
        '''
        Export to the Kiwi config.xml as text.

        :return:
        '''

        self.name = name
        root = self._create_doc()
        self._set_description(root)
        self._set_preferences(root)
        self._set_repositories(root)
        #self._set_users(root)
        self._set_packages(root)

        return '\n'.join([line for line in minidom.parseString(
            etree.tostring(root, encoding='UTF-8', pretty_print=True)).toprettyxml(indent="  ").split("\n")
                          if line.strip()])

    def _get_package_manager(self):
        '''
        Get package manager.

        :return:
        '''
        ret = None
        if self.__grains__.get('os_family') in ('Kali', 'Debian'):
            ret = 'apt-get'
        elif self.__grains__.get('os_family', '') == 'Suse':
            ret = 'zypper'
        elif self.__grains__.get('os_family', '') == 'redhat':
            ret = 'yum'

        if ret is None:
            raise InspectorKiwiProcessorException('Unsupported platform: {0}'.format(self.__grains__.get('os_family')))

        return ret

    def _set_preferences(self, node):
        '''
        Set preferences.

        :return:
        '''
        pref = etree.SubElement(node, 'preferences')
        pacman = etree.SubElement(pref, 'packagemanager')
        pacman.text = self._get_package_manager()
        p_version = etree.SubElement(pref, 'version')
        p_version.text = '0.0.1'
        p_type = etree.SubElement(pref, 'type')
        p_type.set('image', 'vmx')

        for disk_id, disk_data in self._data.system.get('disks', {}).items():
            if disk_id.startswith('/dev'):
                p_type.set('filesystem', disk_data.get('type') or 'ext3')
                break

        p_type.set('installiso', 'true')
        p_type.set('boot', "vmxboot/suse-leap42.1")
        p_type.set('format', self.format)
        p_type.set('bootloader', 'grub2')
        p_type.set('timezone', __salt__['timezone.get_zone']())
        p_type.set('hwclock', __salt__['timezone.get_hwclock']())

        return pref

    def _set_users(self, node):
        '''
        Create existing local users.

        <users group="root">
          <user password="$1$wYJUgpM5$RXMMeASDc035eX.NbYWFl0" home="/root" name="root"/>
        </users>

        :param node:
        :return:
        '''

    def _set_repositories(self, node):
        '''
        Create repositories.

        :param node:
        :return:
        '''
        priority = 99

        for repo_id, repo_data in self._data.software.get('repositories', {}).items():
            if type(repo_data) == list:
                repo_data = repo_data[0]
            if repo_data.get('enabled') or not repo_data.get('disabled'):  # RPM and Debian, respectively
                uri = repo_data.get('baseurl', repo_data.get('uri'))
                if not uri:
                    continue
                repo = etree.SubElement(node, 'repository')
                if self.__grains__.get('os_family') in ('Kali', 'Debian'):
                    repo.set('alias', repo_id)
                    repo.set('distribution', repo_data['dist'])
                else:
                    repo.set('alias', repo_data['alias'])
                    if self.__grains__.get('os_family', '') == 'Suse':
                        repo.set('type', 'yast2')  # TODO: Check for options!
                    repo.set('priority', str(priority))
                source = etree.SubElement(repo, 'source')
                source.set('path', uri)  # RPM and Debian, respectively
                priority -= 1

    def _set_packages(self, node):
        '''
        Set packages and collections.

        :param node:
        :return:
        '''
        pkgs = etree.SubElement(node, 'packages')
        for pkg_name, pkg_version in self._data.software.get('packages', {}).items():
            pkg = etree.SubElement(pkgs, 'package')
            pkg.set('name', pkg_name)

        # Add collections (SUSE)
        if self.__grains__.get('os_family', '') == 'Suse':
            for ptn_id, ptn_data in self._data.software.get('patterns', {}).items():
                if ptn_data.get('installed'):
                    ptn = etree.SubElement(pkgs, 'namedCollection')
                    ptn.set('name', ptn_id)

        return pkgs


    def _set_description(self, node):
        '''
        Create a system description.

        :return:
        '''
        hostname = socket.getfqdn() or platform.node()

        descr = etree.SubElement(node, 'description')
        author = etree.SubElement(descr, 'author')
        author.text = "salt.modules.node on {0}".format(hostname)
        contact = etree.SubElement(descr, 'contact')
        contact.text = 'root@{0}'.format(hostname)
        specs = etree.SubElement(descr, 'specification')
        specs.text = 'Rebuild of {0}, based on Salt inspection.'.format(hostname)

        return descr

    def _create_doc(self):
        '''
        Create document.

        :return:
        '''
        root = etree.Element('image')
        root.set('schemaversion', '6.3')
        root.set('name', self.name)

        return root