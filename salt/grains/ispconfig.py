# -*- coding: utf-8 -*-

import os
import re

import logging
log = logging.getLogger(__name__)

class c_ispconfig:
    f_config="/usr/local/ispconfig/server/lib/config.inc.php"
    installed=os.path.exists(f_config)
    grains = {}
    grains['ispconfig'] = {}

    def _isc_version(self,config):
        regex = re.compile("ISPC_APP_VERSION', '(.*)'")
        for line in config:
            for match in re.finditer(regex, line):
                return match.group(1)

    def _isc_dbinfo(self,config):
        fields=('db_host', 'db_database', 'db_password', 'db_user' )
        dbinfo={}

        for item in fields:
            regex = re.compile(item+r"'] = '(.*)';")
            for line in config:
                for match in re.finditer(regex, line):
                    dbinfo[item]=match.group(1)
            config.seek(0)
        return dbinfo

    def info(self):
        if not self.installed:
            return None

        with open(self.f_config, "r") as config:
            self.grains['ispconfig']['version'] = self._isc_version(config)
            self.grains['ispconfig'].update(self._isc_dbinfo(config))
        return self.grains


def ispconfig():
    '''
    Return information about installed ispconfig
    '''
    isc=c_ispconfig()
    return isc.info()


if __name__ == '__main__':
    isc=ispconfig()
    print isc.info()
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
