# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
# Copyright (C) 2015 SUSE LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

'''
Module for managing Oracle databases.
'''

from __future__ import absolute_import

import os
import logging
import textwrap
from subprocess import Popen, PIPE, STDOUT

from salt.utils.decorators import depends
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,no-name-in-module,redefined-builtin

import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)
__virtualname__ = 'oracle'
_ORACLE_HELPER = None


def __virtual__():
    '''
    Load module only on Linux and Solaris.
    '''
    # ToDO: pfexec support on Slowlaris?
    return (salt.utils.is_linux() or salt.utils.is_sunos()) and salt.utils.which("sudo") and __virtualname__


class _OracleScenarios(object):
    # Get default tablespaces
    tblsp_default = "SELECT username, temporary_tablespace, tblsp_default FROM dba_users"

    tblsp_size = """
SELECT tablespace_name, ROUND(SUM(total_mb)-SUM(free_mb)) CUR_USE_MB, ROUND(SUM(total_mb)) CUR_SZ_MB,
  ROUND((SUM(total_mb)-SUM(free_mb))/SUM(total_mb)*100) CUR_PCT_FULL, ROUND(SUM(max_mb) - (SUM(total_mb)-SUM(free_mb))) FREE_SPACE_MB,
  ROUND(SUM(max_mb)) MAX_SZ_MB, ROUND((SUM(total_mb)-SUM(free_mb))/SUM(max_mb)*100) PCT_FULL
FROM (SELECT tablespace_name, SUM(bytes)/1024/1024 FREE_MB, 0 TOTAL_MB, 0 MAX_MB
        FROM dba_free_space
    GROUP BY tablespace_name
       UNION
      SELECT tablespace_name, 0 CURRENT_MB, SUM(bytes)/1024/1024 TOTAL_MB, SUM(DECODE(maxbytes,0,bytes, maxbytes))/1024/1024 MAX_MB
        FROM dba_data_files
    GROUP BY tablespace_name)
    GROUP BY tablespace_name;
    """
    # tablespace sizes
    tblsp_usage = """
SELECT F.TABLESPACE_NAME,TO_CHAR ((T.TOTAL_SPACE - F.FREE_SPACE),'999,999') "USEDMB",
  TO_CHAR (F.FREE_SPACE, '999,999') "FREEMB",
  TO_CHAR (T.TOTAL_SPACE, '999,999') "TOTALMB",
  TO_CHAR ((ROUND ((F.FREE_SPACE/T.TOTAL_SPACE)*100)),'999')||' %' FREE
FROM (SELECT TABLESPACE_NAME,
  ROUND (SUM (BLOCKS*(SELECT VALUE/1024
FROM V\$PARAMETER
  WHERE NAME = 'db_block_size')/1024) ) FREE_SPACE
FROM DBA_FREE_SPACE
GROUP BY TABLESPACE_NAME ) F, (SELECT TABLESPACE_NAME, ROUND (SUM (BYTES/1048576)) TOTAL_SPACE
                                 FROM DBA_DATA_FILES
                             GROUP BY TABLESPACE_NAME ) T
  WHERE F.TABLESPACE_NAME = T.TABLESPACE_NAME"""

    # Actual database size (Gb)
    db_size = "SELECT sum(bytes)/1024/1024/1024 AS SIZE_GB FROM dba_data_files"

    # Used segments of the database (Gb)
    db_used = "SELECT sum(bytes)/1024/1024/1024 AS SIZE_GB FROM dba_segments"

    # Used database space per owner (Mb)
    db_used_owner = "SELECT SUM(bytes/1024/1024) SIZE_MB FROM dba_segments WHERE owner=UPPER('{0}')"

    # DB owners
    db_owners = "SELECT DISTINCT owner FROM dba_segments ORDER BY owner ASC"

    # DB parametrization
    db_params = "SELECT sid, name, value FROM v\$spparameter WHERE isspecified='TRUE'"


class _OracleHelper(object):
    '''
    Oracle helper constructs all the environment, required for SQL*Plus operations.
    '''

    LSNR_CTL = "{0}/bin/lsnrctl"
    ORATAB = ["/etc/oratab", "/var/opt/oracle/oratab"]

    def __init__(self):
        self.oratab = self.get_oratab()
        self.ora_home = self.get_orahome()
        self.ora_uid = "oracle"

        if not self.ora_home:
            raise Exception("Underlying error: cannot find Oracle home")

        # Setup environment
        os.environ['LANG'] = 'en_US.utf-8'
        os.environ['ORACLE_HOME'] = self.ora_home
        os.environ['ORACLE_BASE'] = self.ora_home.split("/oracle/product")[0] + "/oracle"
        os.environ['ORACLE_SID'] = sorted(self.oratab.keys())[0]
        os.environ['TNS_ADMIN'] = self.ora_home + "/network/admin"
        if os.environ.get('PATH', '').find(self.ora_home) < 0:
            os.environ['PATH'] = self.ora_home + "/bin:" + os.environ['PATH']

        self.lsnrctl = self.LSNR_CTL.format(self.ora_home)
        if not os.path.exists(self.lsnrctl):
            raise Exception("Underlying error: %s does not exists or cannot be executed." % self.lsnrctl)


    def get_oratab(self):
        '''
        File oratab is used for SQL*Net V1 and also list the databases.
        :return: parsed oratab
        '''
        data = {}
        found = False
        for oratab in self.ORATAB:
            if os.path.exists(oratab):
                found = True
                for tabline in filter(None, [line.strip() for line in open(oratab).readlines()]):
                    sid, home, default_start = tabline.split(":")
                    if sid != '*':  # Ignore NULL SID
                        data[sid] = {
                            'home': home,
                            'default_start': default_start,
                        }
                break

        if not found:
            raise CommandExecutionError('The ORATAB was not found nor in "{0}" neither in "{1}".'.format(*ORATAB))

        return data


    def syscall(self, command, input=None, env=None, *params):
        '''
        Call an external system command.
        '''
        stdout, stderr = Popen([command] + list(params),
                               stdout=PIPE,
                               stdin=PIPE,
                               stderr=STDOUT,
                               env=env or os.environ).communicate(input=input)
        stderr = (stderr or "") + self.extract_errors(stdout)

        return stdout and stdout or '', stderr and stderr or ''


    def extract_errors(self, stdout):
        """
        Extract errors from SQL*Plus.
        More: http://docs.oracle.com/cd/B28359_01/server.111/b28278/toc.htm
        """
        if not (stdout or "").strip():
            return ""

        out = []
        for line in filter(None, str(stdout).replace("\\n", "\n").split("\n")):
            if line.lower().startswith("ora-") and not line.find("===") > -1:
                out += textwrap.wrap(line.strip())

        return '\n'.join(out)


    def get_orahome(self, sid=None):
        '''
        Find out Oracle home.
        Either find "first wins" or per specific SID.

        :return:
        '''
        return (sid and self.oratab.get(sid, {}) or self.oratab[sorted(self.oratab.keys())[0]]).get('home')


    def get_owner(self):
        '''
        Find out main UID. Usually it is "oracle", but installations sometimes gets crazy.
        :return: UID
        '''


    def get_env(self):
        '''
        Construct environment.

        :return:
        '''
        e = os.environ.get
        scenario = []
        if e('PATH') and e('ORACLE_BASE') and e('ORACLE_SID') and e('ORACLE_HOME'):
            scenario.append("export ORACLE_BASE={0}".format(e('ORACLE_BASE')))
            scenario.append("export ORACLE_SID={0}".format(e('ORACLE_SID')))
            scenario.append("export ORACLE_HOME={0}".format(e('ORACLE_HOME')))
            scenario.append("export PATH={0}".format(e('PATH')))
        else:
            raise Exception("Underlying error: environment cannot be constructed.")

        return scenario


    def get_tnsping(self, address):
        '''
        Create TNS ping env.

        :param address:
        :return:
        '''
        scenario = self.get_env()
        scenario.append("{0}/bin/tnsping {1}".format(self.ora_home, address))

        return '\n'.join(scenario)


    def prepare_scenario(self, src, login=None):
        '''
        Generate a template for the Oracle SQL*Plus scenario.
        '''
        scenario = self.get_env()
        scenario.append("cat - << EOF | {0}/bin/sqlplus -S /nolog".format(self.ora_home))
        if not login:
            scenario.append("CONNECT / AS SYSDBA;")
        else:
            scenario.append("CONNECT {0};".format(login))
        scenario.append("SET TAB OFF;")
        scenario.append("SET FEEDBACK OFF;")
        scenario.append("SET LINESIZE 32000;")
        scenario.append("SET PAGESIZE 40000;")
        scenario.append("SET LONG 50000;")
        scenario.append("{0};".format(src.strip().strip(";")))
        scenario.append("EXIT;")
        scenario.append("EOF")

        return '\n'.join(scenario)


    def run(self, cmd):
        '''
        Run a result via sudo call.
        '''
        out = __salt__['cmd.run_all'](cmd)
        if out['retcode']:
            raise CommandExecutionError(out['stderr'])

        return out['stdout'], self.extract_errors(out['stdout'])


    def sqlplus_to_table(self, data):
        '''
        Parse SQL*Plus output to a type-less data.

        WARNING: this, of course, loses all the types.

        Working with the real database data must be done
        through the appropriate tools and drivers.
        '''

        # SQL*Plus can only return HTML v3.0 or ASCII text.
        # Parsing any of those is an odd task, where dealing with the text is still better.
        # That's the only way to have a driver-less database operations.

        def _extract(line, widths):
            '''
            Extract data on a field widths.
            '''
            data = list()
            offset = 0
            for idx in range(len(widths)):
                fwd = widths[idx]
                data.append(line[offset:offset + fwd].strip())
                offset += fwd + 1

            return data

        data = data.split(os.linesep)

        # Get width delimeter
        field_widths = None
        headers = None
        idx = 0
        for line in data:
            if line.startswith("---"):
                field_widths = line.strip()
                headers = data[idx - 1]
                break
            idx += 1

        if not field_widths:
           raise Exception("Unable to find an entry point to parse the output")
        field_widths = [len(elm) for elm in field_widths.split(" ") if elm]

        # Add headers
        hdr = tuple(_extract(headers, field_widths))

        # Add the rest of the output
        out = list()
        header_cutoff = False
        body_cutoff = True
        for line in data:
            try:
                if line.strip().startswith("---"):
                    header_cutoff = True
                    continue
            except:
                raise Exception(str(line))
            if header_cutoff and not line.strip():
                body_cutoff = False
            if not header_cutoff or not body_cutoff:
                continue
            out.append(tuple(_extract(line, field_widths)))

        return hdr, tuple(out)



def _orahlp():
    '''
    Cache oracle helper per session.
    :return:
    '''
    global _ORACLE_HELPER
    if not _ORACLE_HELPER:
        _ORACLE_HELPER = _OracleHelper()
    return _ORACLE_HELPER


def databases():
    '''
    List available databases.

    :return: A list of available databases.

    CLI example:

    .. code-block:: bash

       salt 'host' oracle.databases
    '''
    return sorted(_orahlp().oratab.keys())


def status():
    """
    Get Oracle listener status.
    """
    stdout, oraerr = _orahlp().run("sudo -u {0} ORACLE_HOME={1} {2} status"
                                   .format('oracle', _orahlp().ora_home, _orahlp().lsnrctl))
    ret = {}
    if stdout:
        for line in stdout.split("\n"):
            if line.lower().startswith("uptime"):
                ret['uptime'] = line.replace("\t", " ").split(" ", 1)[-1].strip()
                ret['ready'] = True
                break
        unknown = 0
        available = 0
        for line in stdout.split('Services')[-1].split("\n"):
            if line.find('READY') > -1:
                available += 1
            if line.find('UNKNOWN') > -1:
                unknown += 1
        ret['unknown'] = unknown
        ret['available'] = available

    if oraerr:
        ret['ORA-ERR'] = oraerr

    return ret


def query(sid, user, password, query):
    '''
    Execute an SQL query.

    :return A table result as a list of lists (on select), execution time on other queries if they were successful,
    raise an exception if not.

    * **sid**: SID of the database
    * **user**: Login user
    * **password**: Login password
    * **query**: SQL query to run

    CLI example:

    .. code-block:: bash

       salt '*' oracle.query SID "select sysdate from dual"
    '''

    if not sid:
        raise CommandExecutionError("SID cannot be empty.")
    elif not user:
        raise CommandExecutionError("User cannot be empty.")
    elif not query:
        raise CommandExecutionError("SQL query cannot be empty")
    # Password can be anything and even empty, thus no check

    hlp = _orahlp()
    out, err = hlp.syscall("sudo", hlp.prepare_scenario(query, "{0}/{1}@{2}".format(user, password, sid)),
                           None, "-u", hlp.ora_uid, "/bin/bash")
    ret = dict()
    if err:
        ret['oracle-error'] = err
    else:
        ret['query'] = {}
        ret['query']['headers'], ret['query']['data'] = hlp.sqlplus_to_table(out)

    return ret


def version(*args):
    '''
    Oracle database version

    * **instances**: Return versions of all existing databases in the current instance.

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.version
        salt '*' oracle.version instances
    '''

    query = "select * from V\${0}".format('instances' in args and "instance" or "version")
    out, err = _orahlp().syscall("sudo", _orahlp().prepare_scenario(query),
                                 None, "-u", _orahlp().ora_uid, "/bin/bash")
    ret = dict()
    if err:
        ret['oracle-error'] = err
    else:
        if 'instances' in args:
            ret['versions'] = list()
            headers, data = _orahlp().sqlplus_to_table(out)
            headers = [hdr.lower() for hdr in headers]
            for dbv in data:
                vrs = dict(zip(headers, dbv))
                ret['versions'].append({vrs.pop("instance_name"): vrs})
        elif not args:
            ret = list()  # Redefinition of "ret"
            cutoff = True
            for line in out.strip().split(os.linesep):
                if line.startswith("---"):
                    cutoff = False
                    continue
                if not cutoff:
                    ret.append(line.replace("\t", " ").strip())
            return ret
        else:
            raise CommandExecutionError("Unknown parameters: {0}".format(', '.join(args)))

    return ret


def tablespace(*args, **kwargs):
    '''
    Get default tablespaces for users.

    * **users**: Get mapping tablespace per user.
    * **usage**: Get usage data only for this user.
    * **size**: Get size of all tablespaces.
    * **as_text**: Return data as formatted text.

    :param args:
    :return:

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.tablespace users
        salt '*' oracle.tablespace size
        salt '*' oracle.tablespace size as_text=True
    '''
    query = None
    if 'users' in args:
        query = _OracleScenarios.tblsp_default
    elif 'usage' in args:
        query = _OracleScenarios.tblsp_usage
    elif 'size' in args:
        query = _OracleScenarios.tblsp_size

    if not query:
        raise CommandExecutionError("Unknown operation.")

    out, err = _orahlp().syscall("sudo", _orahlp().prepare_scenario(query), None, "-u", _orahlp().ora_uid, "/bin/bash")

    ret = dict()
    if err:
        ret['oracle-error'] = err
    else:
        if kwargs.get('as_text'):
            return out.strip()
        else:
            headers, data = _orahlp().sqlplus_to_table(out)
            if 'usage' in args:
                for tbs in data:
                    t_name, used, free, total, p_free = tbs
                    ret[t_name] = {
                        'used_mb': used,
                        'free_mb': free,
                        'total_mb': total,
                        'free': p_free,
                    }
                return ret
            if 'size' in args:
                for tbs in data:
                    t_name, curr_use_mb, curr_sz_mb, curr_pct_full, free_mb, max_size_mb, pct_full = tbs
                    ret[t_name] = {
                        'current_usage_mb': curr_use_mb,
                        'current_size_mb': curr_sz_mb,
                        'percent_current': curr_pct_full,
                        'percent_full': pct_full,
                        'free_space_mb': free_mb,
                        'max_size_mb': max_size_mb,
                    }
            elif 'users' in args:
                for row in data:
                    uid, tmp_tb, def_tb = row
                    if uid not in ret:
                        ret[uid] = {
                            'temporary': [],
                            'default': [],
                        }
                    # No joy for sets in serialization.
                    if tmp_tb not in ret[uid]['temporary']:
                        ret[uid]['temporary'].append(tmp_tb)
                    if def_tb not in ret[uid]['default']:
                        ret[uid]['default'].append(def_tb)
    return ret


def size(*args, **kwargs):
    '''
    Get actual size of the database

    used
        Show used segments out of the whole database.

        owner
            Show how much space takes one owner.

    :param args:
    :return:

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.size
        salt '*' oracle.size used
        salt '*' oracle.size used owner=Simon
    '''
    query = None
    if 'used' in args:
        if 'owner' in kwargs:
            query = _OracleScenarios.db_used_owner.format(kwargs['owner'])
        else:
            query = _OracleScenarios.db_used
    elif not args:
        query = _OracleScenarios.db_size
    else:
        raise CommandExecutionError("Unknown parameter: {0}".format(', '.join(args)))

    out, err = _orahlp().syscall("sudo", _orahlp().prepare_scenario(query), None, "-u", _orahlp().ora_uid, "/bin/bash")
    ret = dict()
    if err:
        ret['err'] = err
    else:
        hdr, data = _orahlp().sqlplus_to_table(out)
        if not data:
            raise CommandExecutionError("Unable to determine size of the database.")
        ret = {
            'size': round(float(data[0][0]), 2),
            'unit': 'owner' in kwargs and 'Mb' or 'Gb',
            }

    return ret


def owners():
    '''
    Get list of all owners.

    :return:

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.owners
    '''
    out, err = _orahlp().syscall("sudo", _orahlp().prepare_scenario(_OracleScenarios.db_owners),
                                 None, "-u", _orahlp().ora_uid, "/bin/bash")
    ret = dict()
    if err:
        ret['err'] = err
    else:
        hdr, data = _orahlp().sqlplus_to_table(out)
        ret = list()
        if not data:
            raise CommandExecutionError("Unable to determine size of the database.")
        for owner in data:
            ret.append(owner[0])

    return ret


def parameters():
    '''
    Get list of all database parameters.

    :return:

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.parameters
    '''
    out, err = _orahlp().syscall("sudo", _orahlp().prepare_scenario(_OracleScenarios.db_params),
                                 None, "-u", _orahlp().ora_uid, "/bin/bash")
    ret = dict()
    if err:
        ret['err'] = err
    else:
        hdr, data = _orahlp().sqlplus_to_table(out)
        ret = dict()
        if not data:
            raise CommandExecutionError("Unable to determine size of the database.")
        for sid, name, value in data:
            if sid == '*':
                sid = 'To all'
            else:
                sid = sid.lower()

            if sid not in ret:
                ret[sid] = list()
            ret[sid].append({name: value})

    return ret


def ping(sid):
    '''
    Perform TNS ping over an Oracle address.

    :return:

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.ping SID
    '''
    out, err = _orahlp().syscall("sudo", _orahlp().get_tnsping(sid),
                                 None, "-u", _orahlp().ora_uid, "/bin/bash")
    out = out.strip().split(os.linesep)
    for line in out:
        if line.startswith("TNS-"):
            return {'TNS-error': line}

    return {'TNS': out[-1].startswith("OK ") and out[-1] or 'N/A'}

