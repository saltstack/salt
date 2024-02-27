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

import os
import platform
import socket
from xml.dom import minidom

import salt.utils.files
from salt.modules.inspectlib.exceptions import InspectorKiwiProcessorException

try:
    import grp
    import pwd
except ImportError:
    pass


try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree


class KiwiExporter:
    """
    Exports system description as Kiwi configuration.
    """

    def __init__(self, grains, format):
        self.__grains__ = grains
        self.format = format
        self._data = type("data", (), {})
        self.name = None

    def load(self, **descr):
        """
        Load data by keys.

        :param data:
        :return:
        """
        for obj, data in descr.items():
            setattr(self._data, obj, data)

        return self

    def export(self, name):
        """
        Export to the Kiwi config.xml as text.

        :return:
        """

        self.name = name
        root = self._create_doc()
        self._set_description(root)
        self._set_preferences(root)
        self._set_repositories(root)
        self._set_users(root)
        self._set_packages(root)

        return "\n".join(
            [
                line
                for line in minidom.parseString(etree.tostring(root, encoding="UTF-8"))
                .toprettyxml(indent="  ")
                .split("\n")
                if line.strip()
            ]
        )

    def _get_package_manager(self):
        """
        Get package manager.

        :return:
        """
        ret = None
        if self.__grains__.get("os_family") in ("Kali", "Debian"):
            ret = "apt-get"
        elif self.__grains__.get("os_family", "") == "Suse":
            ret = "zypper"
        elif self.__grains__.get("os_family", "") == "redhat":
            ret = "yum"

        if ret is None:
            raise InspectorKiwiProcessorException(
                "Unsupported platform: {}".format(self.__grains__.get("os_family"))
            )

        return ret

    def _set_preferences(self, node):
        """
        Set preferences.

        :return:
        """
        pref = etree.SubElement(node, "preferences")
        pacman = etree.SubElement(pref, "packagemanager")
        pacman.text = self._get_package_manager()
        p_version = etree.SubElement(pref, "version")
        p_version.text = "0.0.1"
        p_type = etree.SubElement(pref, "type")
        p_type.set("image", "vmx")

        for disk_id, disk_data in self._data.system.get("disks", {}).items():
            if disk_id.startswith("/dev"):
                p_type.set("filesystem", disk_data.get("type") or "ext3")
                break

        p_type.set("installiso", "true")
        p_type.set("boot", "vmxboot/suse-leap42.1")
        p_type.set("format", self.format)
        p_type.set("bootloader", "grub2")
        p_type.set("timezone", __salt__["timezone.get_zone"]())
        p_type.set("hwclock", __salt__["timezone.get_hwclock"]())

        return pref

    def _get_user_groups(self, user):
        """
        Get user groups.

        :param user:
        :return:
        """
        return [g.gr_name for g in grp.getgrall() if user in g.gr_mem] + [
            grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name
        ]

    def _set_users(self, node):
        """
        Create existing local users.

        <users group="root">
          <user password="$1$wYJUgpM5$RXMMeASDc035eX.NbYWFl0" home="/root" name="root"/>
        </users>

        :param node:
        :return:
        """
        # Get real local users with the local passwords
        shadow = {}
        with salt.utils.files.fopen("/etc/shadow") as rfh:
            for sh_line in rfh.read().split(os.linesep):
                if sh_line.strip():
                    login, pwd = sh_line.split(":")[:2]
                    if pwd and pwd[0] not in "!*":
                        shadow[login] = {"p": pwd}

        with salt.utils.files.fopen("/etc/passwd") as rfh:
            for ps_line in rfh.read().split(os.linesep):
                if ps_line.strip():
                    ps_line = ps_line.strip().split(":")
                    if ps_line[0] in shadow:
                        shadow[ps_line[0]]["h"] = ps_line[5]
                        shadow[ps_line[0]]["s"] = ps_line[6]
                        shadow[ps_line[0]]["g"] = self._get_user_groups(ps_line[0])

        users_groups = []
        users_node = etree.SubElement(node, "users")
        for u_name, u_data in shadow.items():
            user_node = etree.SubElement(users_node, "user")
            user_node.set("password", u_data["p"])
            user_node.set("home", u_data["h"])
            user_node.set("name", u_name)
            users_groups.extend(u_data["g"])
        users_node.set("group", ",".join(users_groups))

        return users_node

    def _set_repositories(self, node):
        """
        Create repositories.

        :param node:
        :return:
        """
        priority = 99

        for repo_id, repo_data in self._data.software.get("repositories", {}).items():
            if type(repo_data) == list:
                repo_data = repo_data[0]
            if repo_data.get("enabled") or not repo_data.get(
                "disabled"
            ):  # RPM and Debian, respectively
                uri = repo_data.get("baseurl", repo_data.get("uri"))
                if not uri:
                    continue
                repo = etree.SubElement(node, "repository")
                if self.__grains__.get("os_family") in ("Kali", "Debian"):
                    repo.set("alias", repo_id)
                    repo.set("distribution", repo_data["dist"])
                else:
                    repo.set("alias", repo_data["alias"])
                    if self.__grains__.get("os_family", "") == "Suse":
                        repo.set("type", "yast2")  # TODO: Check for options!
                    repo.set("priority", str(priority))
                source = etree.SubElement(repo, "source")
                source.set("path", uri)  # RPM and Debian, respectively
                priority -= 1

    def _set_packages(self, node):
        """
        Set packages and collections.

        :param node:
        :return:
        """
        pkgs = etree.SubElement(node, "packages")
        for pkg_name, pkg_version in sorted(
            self._data.software.get("packages", {}).items()
        ):
            pkg = etree.SubElement(pkgs, "package")
            pkg.set("name", pkg_name)

        # Add collections (SUSE)
        if self.__grains__.get("os_family", "") == "Suse":
            for ptn_id, ptn_data in self._data.software.get("patterns", {}).items():
                if ptn_data.get("installed"):
                    ptn = etree.SubElement(pkgs, "namedCollection")
                    ptn.set("name", ptn_id)

        return pkgs

    def _set_description(self, node):
        """
        Create a system description.

        :return:
        """
        hostname = socket.getfqdn() or platform.node()

        descr = etree.SubElement(node, "description")
        author = etree.SubElement(descr, "author")
        author.text = f"salt.modules.node on {hostname}"
        contact = etree.SubElement(descr, "contact")
        contact.text = f"root@{hostname}"
        specs = etree.SubElement(descr, "specification")
        specs.text = f"Rebuild of {hostname}, based on Salt inspection."

        return descr

    def _create_doc(self):
        """
        Create document.

        :return:
        """
        root = etree.Element("image")
        root.set("schemaversion", "6.3")
        root.set("name", self.name)

        return root
