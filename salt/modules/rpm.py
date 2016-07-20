# -*- coding: utf-8 -*-
'''
Support for rpm
'''

# Import python libs
from __future__ import absolute_import
import logging
import os
import re
import datetime

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators
import salt.utils.pkg.rpm
# pylint: disable=import-error,redefined-builtin
from salt.ext.six.moves import shlex_quote as _cmd_quote
from salt.ext.six.moves import zip

try:
    import rpm
    HAS_RPM = True
except ImportError:
    HAS_RPM = False

try:
    import rpmUtils.miscutils
    HAS_RPMUTILS = True
except ImportError:
    HAS_RPMUTILS = False

# pylint: enable=import-error,redefined-builtin
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'lowpkg'


def __virtual__():
    '''
    Confine this module to rpm based systems
    '''
    if not salt.utils.which('rpm'):
        return False
    try:
        os_grain = __grains__['os'].lower()
        os_family = __grains__['os_family'].lower()
    except Exception:
        return False

    enabled = ('amazon', 'xcp', 'xenserver')

    if os_family in ['redhat', 'suse'] or os_grain in enabled:
        return __virtualname__
    return False


def bin_pkg_info(path, saltenv='base'):
    '''
    .. versionadded:: 2015.8.0

    Parses RPM metadata and returns a dictionary of information about the
    package (name, version, etc.).

    path
        Path to the file. Can either be an absolute path to a file on the
        minion, or a salt fileserver URL (e.g. ``salt://path/to/file.rpm``).
        If a salt fileserver URL is passed, the file will be cached to the
        minion so that it can be examined.

    saltenv : base
        Salt fileserver envrionment from which to retrieve the package. Ignored
        if ``path`` is a local file path on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.bin_pkg_info /root/salt-2015.5.1-2.el7.noarch.rpm
        salt '*' lowpkg.bin_pkg_info salt://salt-2015.5.1-2.el7.noarch.rpm
    '''
    # If the path is a valid protocol, pull it down using cp.cache_file
    if __salt__['config.valid_fileproto'](path):
        newpath = __salt__['cp.cache_file'](path, saltenv)
        if not newpath:
            raise CommandExecutionError(
                'Unable to retrieve {0} from saltenv \'{1}\''
                .format(path, saltenv)
            )
        path = newpath
    else:
        if not os.path.exists(path):
            raise CommandExecutionError(
                '{0} does not exist on minion'.format(path)
            )
        elif not os.path.isabs(path):
            raise SaltInvocationError(
                '{0} does not exist on minion'.format(path)
            )

    # REPOID is not a valid tag for the rpm command. Remove it and replace it
    # with 'none'
    queryformat = salt.utils.pkg.rpm.QUERYFORMAT.replace('%{REPOID}', 'none')
    output = __salt__['cmd.run_stdout'](
        'rpm -qp --queryformat {0} {1}'.format(_cmd_quote(queryformat), path),
        output_loglevel='trace',
        ignore_retcode=True
    )
    ret = {}
    pkginfo = salt.utils.pkg.rpm.parse_pkginfo(
        output,
        osarch=__grains__['osarch']
    )
    for field in pkginfo._fields:
        ret[field] = getattr(pkginfo, field)
    return ret


def list_pkgs(*packages):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.list_pkgs
    '''
    pkgs = {}
    if not packages:
        cmd = 'rpm -qa --qf \'%{NAME} %{VERSION}\\n\''
    else:
        cmd = 'rpm -q --qf \'%{{NAME}} %{{VERSION}}\\n\' {0}'.format(
            ' '.join(packages)
        )
    out = __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='trace')
    for line in out.splitlines():
        if 'is not installed' in line:
            continue
        comps = line.split()
        pkgs[comps[0]] = comps[1]
    return pkgs


def verify(*package, **kwargs):
    '''
    Runs an rpm -Va on a system, and returns the results in a dict

    Files with an attribute of config, doc, ghost, license or readme in the
    package header can be ignored using the ``ignore_types`` keyword argument

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.verify
        salt '*' lowpkg.verify httpd
        salt '*' lowpkg.verify 'httpd postfix'
        salt '*' lowpkg.verify 'httpd postfix' ignore_types=['config','doc']
    '''
    ftypes = {'c': 'config',
              'd': 'doc',
              'g': 'ghost',
              'l': 'license',
              'r': 'readme'}
    ret = {}
    ignore_types = kwargs.get('ignore_types', [])
    if package:
        packages = ' '.join(package)
        cmd = 'rpm -V {0}'.format(packages)
    else:
        cmd = 'rpm -Va'
    out = __salt__['cmd.run'](
            cmd,
            python_shell=False,
            output_loglevel='trace',
            ignore_retcode=True)
    for line in out.splitlines():
        fdict = {'mismatch': []}
        if 'missing' in line:
            line = ' ' + line
            fdict['missing'] = True
            del fdict['mismatch']
        fname = line[13:]
        if line[11:12] in ftypes:
            fdict['type'] = ftypes[line[11:12]]
        if 'type' not in fdict or fdict['type'] not in ignore_types:
            if line[0:1] == 'S':
                fdict['mismatch'].append('size')
            if line[1:2] == 'M':
                fdict['mismatch'].append('mode')
            if line[2:3] == '5':
                fdict['mismatch'].append('md5sum')
            if line[3:4] == 'D':
                fdict['mismatch'].append('device major/minor number')
            if line[4:5] == 'L':
                fdict['mismatch'].append('readlink path')
            if line[5:6] == 'U':
                fdict['mismatch'].append('user')
            if line[6:7] == 'G':
                fdict['mismatch'].append('group')
            if line[7:8] == 'T':
                fdict['mismatch'].append('mtime')
            if line[8:9] == 'P':
                fdict['mismatch'].append('capabilities')
            ret[fname] = fdict
    return ret


def modified(*packages, **flags):
    '''
    List the modified files that belong to a package. Not specifying any packages
    will return a list of _all_ modified files on the system's RPM database.

    .. versionadded:: 2015.5.0

    CLI examples:

    .. code-block:: bash

        salt '*' lowpkg.modified httpd
        salt '*' lowpkg.modified httpd postfix
        salt '*' lowpkg.modified
    '''
    ret = __salt__['cmd.run_all'](
        ['rpm', '-Va'] + list(packages),
        python_shell=False,
        output_loglevel='trace')

    data = {}

    # If verification has an output, then it means it failed
    # and the return code will be 1. We are interested in any bigger
    # than 1 code.
    if ret['retcode'] > 1:
        del ret['stdout']
        return ret
    elif not ret['retcode']:
        return data

    ptrn = re.compile(r"\s+")
    changes = cfg = f_name = None
    for f_info in ret['stdout'].splitlines():
        f_info = ptrn.split(f_info)
        if len(f_info) == 3:  # Config file
            changes, cfg, f_name = f_info
        else:
            changes, f_name = f_info
            cfg = None
        keys = ['size', 'mode', 'checksum', 'device', 'symlink',
                'owner', 'group', 'time', 'capabilities']
        changes = list(changes)
        if len(changes) == 8:  # Older RPMs do not support capabilities
            changes.append(".")
        stats = []
        for k, v in zip(keys, changes):
            if v != '.':
                stats.append(k)
        if cfg is not None:
            stats.append('config')
        data[f_name] = stats

    if not flags:
        return data

    # Filtering
    filtered_data = {}
    for f_name, stats in data.items():
        include = True
        for param, pval in flags.items():
            if param.startswith("_"):
                continue
            if (not pval and param in stats) or \
               (pval and param not in stats):
                include = False
                break
        if include:
            filtered_data[f_name] = stats

    return filtered_data


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's rpm database (not generally
    recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.file_list httpd
        salt '*' lowpkg.file_list httpd postfix
        salt '*' lowpkg.file_list
    '''
    if not packages:
        cmd = 'rpm -qla'
    else:
        cmd = 'rpm -ql {0}'.format(' '.join(packages))
    ret = __salt__['cmd.run'](
            cmd,
            python_shell=False,
            output_loglevel='trace').splitlines()
    return {'errors': [], 'files': ret}


def file_dict(*packages):
    '''
    List the files that belong to a package, sorted by group. Not specifying
    any packages will return a list of _every_ file on the system's rpm
    database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.file_dict httpd
        salt '*' lowpkg.file_dict httpd postfix
        salt '*' lowpkg.file_dict
    '''
    errors = []
    ret = {}
    pkgs = {}
    if not packages:
        cmd = 'rpm -qa --qf \'%{NAME} %{VERSION}\\n\''
    else:
        cmd = 'rpm -q --qf \'%{{NAME}} %{{VERSION}}\\n\' {0}'.format(
            ' '.join(packages)
        )
    out = __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='trace')
    for line in out.splitlines():
        if 'is not installed' in line:
            errors.append(line)
            continue
        comps = line.split()
        pkgs[comps[0]] = {'version': comps[1]}
    for pkg in pkgs:
        files = []
        cmd = 'rpm -ql {0}'.format(pkg)
        out = __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='trace')
        for line in out.splitlines():
            files.append(line)
        ret[pkg] = files
    return {'errors': errors, 'packages': ret}


def owner(*paths):
    '''
    Return the name of the package that owns the file. Multiple file paths can
    be passed. If a single path is passed, a string will be returned,
    and if multiple paths are passed, a dictionary of file/package name pairs
    will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.owner /usr/bin/apachectl
        salt '*' lowpkg.owner /usr/bin/apachectl /etc/httpd/conf/httpd.conf
    '''
    if not paths:
        return ''
    ret = {}
    cmd = 'rpm -qf --queryformat "%{{NAME}}" {0!r}'
    for path in paths:
        ret[path] = __salt__['cmd.run_stdout'](cmd.format(path),
                                               output_loglevel='trace')
        if 'not owned' in ret[path].lower():
            ret[path] = ''
    if len(ret) == 1:
        return list(ret.values())[0]
    return ret


@decorators.which('rpm2cpio')
@decorators.which('cpio')
@decorators.which('diff')
def diff(package, path):
    '''
    Return a formatted diff between current file and original in a package.
    NOTE: this function includes all files (configuration and not), but does
    not work on binary content.

    :param package: The name of the package
    :param path: Full path to the installed file
    :return: Difference or empty string. For binary files only a notification.

    CLI example:

    .. code-block:: bash

        salt '*' lowpkg.diff apache2 /etc/apache2/httpd.conf
    '''

    cmd = "rpm2cpio {0} " \
          "| cpio -i --quiet --to-stdout .{1} " \
          "| diff -u --label 'A {1}' --from-file=- --label 'B {1}' {1}"
    res = __salt__['cmd.shell'](cmd.format(package, path), output_loglevel='trace')
    if res and res.startswith('Binary file'):
        return 'File "{0}" is binary and its content has been modified.'.format(path)

    return res


def info(*packages, **attr):
    '''
    Return a detailed package(s) summary information.
    If no packages specified, all packages will be returned.

    :param packages:

    :param attr:
        Comma-separated package attributes. If no 'attr' is specified, all available attributes returned.

        Valid attributes are:
            version, vendor, release, build_date, build_date_time_t, install_date, install_date_time_t,
            build_host, group, source_rpm, arch, epoch, size, license, signature, packager, url, summary, description.

    :return:

    CLI example:

    .. code-block:: bash

        salt '*' lowpkg.info apache2 bash
        salt '*' lowpkg.info apache2 bash attr=version
        salt '*' lowpkg.info apache2 bash attr=version,build_date_iso,size
    '''
    # LONGSIZE is not a valid tag for all versions of rpm. If LONGSIZE isn't
    # available, then we can just use SIZE for older versions. See Issue #31366.
    rpm_tags = __salt__['cmd.run_stdout'](
        ['rpm', '--querytags'],
        python_shell=False).splitlines()
    if 'LONGSIZE' in rpm_tags:
        size_tag = '%{LONGSIZE}'
    else:
        size_tag = '%{SIZE}'

    cmd = packages and "rpm -q {0}".format(' '.join(packages)) or "rpm -qa"

    # Construct query format
    attr_map = {
        "name": "name: %{NAME}\\n",
        "relocations": "relocations: %|PREFIXES?{[%{PREFIXES} ]}:{(not relocatable)}|\\n",
        "version": "version: %{VERSION}\\n",
        "vendor": "vendor: %{VENDOR}\\n",
        "release": "release: %{RELEASE}\\n",
        "epoch": "%|EPOCH?{epoch: %{EPOCH}\\n}|",
        "build_date_time_t": "build_date_time_t: %{BUILDTIME}\\n",
        "build_date": "build_date: %{BUILDTIME}\\n",
        "install_date_time_t": "install_date_time_t: %|INSTALLTIME?{%{INSTALLTIME}}:{(not installed)}|\\n",
        "install_date": "install_date: %|INSTALLTIME?{%{INSTALLTIME}}:{(not installed)}|\\n",
        "build_host": "build_host: %{BUILDHOST}\\n",
        "group": "group: %{GROUP}\\n",
        "source_rpm": "source_rpm: %{SOURCERPM}\\n",
        "size": "size: " + size_tag + "\\n",
        "arch": "arch: %{ARCH}\\n",
        "license": "%|LICENSE?{license: %{LICENSE}\\n}|",
        "signature": "signature: %|DSAHEADER?{%{DSAHEADER:pgpsig}}:{%|RSAHEADER?{%{RSAHEADER:pgpsig}}:"
                     "{%|SIGGPG?{%{SIGGPG:pgpsig}}:{%|SIGPGP?{%{SIGPGP:pgpsig}}:{(none)}|}|}|}|\\n",
        "packager": "%|PACKAGER?{packager: %{PACKAGER}\\n}|",
        "url": "%|URL?{url: %{URL}\\n}|",
        "summary": "summary: %{SUMMARY}\\n",
        "description": "description:\\n%{DESCRIPTION}\\n",
        "edition": "edition: %|EPOCH?{%{EPOCH}:}|%{VERSION}-%{RELEASE}\\n",
    }

    attr = attr.get('attr', None) and attr['attr'].split(",") or None
    query = list()
    if attr:
        for attr_k in attr:
            if attr_k in attr_map and attr_k != 'description':
                query.append(attr_map[attr_k])
        if not query:
            raise CommandExecutionError('No valid attributes found.')
        if 'name' not in attr:
            attr.append('name')
            query.append(attr_map['name'])
        if 'edition' not in attr:
            attr.append('edition')
            query.append(attr_map['edition'])
    else:
        for attr_k, attr_v in attr_map.iteritems():
            if attr_k != 'description':
                query.append(attr_v)
    if attr and 'description' in attr or not attr:
        query.append(attr_map['description'])
    query.append("-----\\n")

    call = __salt__['cmd.run_all'](cmd + (" --queryformat '{0}'".format(''.join(query))),
                                   output_loglevel='trace', env={'TZ': 'UTC'}, clean_env=True)
    if call['retcode'] != 0:
        comment = ''
        if 'stderr' in call:
            comment += (call['stderr'] or call['stdout'])
        raise CommandExecutionError('{0}'.format(comment))
    elif 'error' in call['stderr']:
        raise CommandExecutionError(call['stderr'])
    else:
        out = call['stdout']

    _ret = list()
    for pkg_info in re.split(r"----*", out):
        pkg_info = pkg_info.strip()
        if not pkg_info:
            continue
        pkg_info = pkg_info.split(os.linesep)
        if pkg_info[-1].lower().startswith('distribution'):
            pkg_info = pkg_info[:-1]

        pkg_data = dict()
        pkg_name = None
        descr_marker = False
        descr = list()
        for line in pkg_info:
            if descr_marker:
                descr.append(line)
                continue
            line = [item.strip() for item in line.split(':', 1)]
            if len(line) != 2:
                continue
            key, value = line
            if key == 'description':
                descr_marker = True
                continue
            if key == 'name':
                pkg_name = value

            # Convert Unix ticks into ISO time format
            if key in ['build_date', 'install_date']:
                try:
                    pkg_data[key] = datetime.datetime.fromtimestamp(int(value)).isoformat() + "Z"
                except ValueError:
                    log.warning('Could not convert "{0}" into Unix time'.format(value))
                continue

            # Convert Unix ticks into an Integer
            if key in ['build_date_time_t', 'install_date_time_t']:
                try:
                    pkg_data[key] = int(value)
                except ValueError:
                    log.warning('Could not convert "{0}" into Unix time'.format(value))
                continue
            if key not in ['description', 'name'] and value:
                pkg_data[key] = value
        if attr and 'description' in attr or not attr:
            pkg_data['description'] = os.linesep.join(descr)
        if pkg_name:
            pkg_data['name'] = pkg_name
            _ret.append(pkg_data)

    # Force-sort package data by version,
    # pick only latest versions
    # (in case multiple packages installed, e.g. kernel)
    ret = dict()
    for pkg_data in reversed(sorted(_ret, cmp=lambda a_vrs, b_vrs: version_cmp(a_vrs['edition'], b_vrs['edition']))):
        pkg_name = pkg_data.pop('name')
        if pkg_name not in ret:
            ret[pkg_name] = pkg_data.copy()
            del ret[pkg_name]['edition']

    return ret


def version_cmp(ver1, ver2, ignore_epoch=False):
    '''
    .. versionadded:: 2015.8.9

    Do a cmp-style comparison on two packages. Return -1 if ver1 < ver2, 0 if
    ver1 == ver2, and 1 if ver1 > ver2. Return None if there was a problem
    making the comparison.

    ignore_epoch : False
        Set to ``True`` to ignore the epoch when comparing versions

        .. versionadded:: 2015.8.10,2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2-001' '0.2.0.1-002'
    '''
    normalize = lambda x: str(x).split(':', 1)[-1] if ignore_epoch else str(x)
    ver1 = normalize(ver1)
    ver2 = normalize(ver2)

    try:
        cmp_func = None
        if HAS_RPM:
            try:
                cmp_func = rpm.labelCompare
            except AttributeError:
                # Catches corner case where someone has a module named "rpm" in
                # their pythonpath.
                log.debug(
                    'rpm module imported, but it does not have the '
                    'labelCompare function. Not using rpm.labelCompare for '
                    'version comparison.'
                )
        if cmp_func is None and HAS_RPMUTILS:
            try:
                cmp_func = rpmUtils.miscutils.compareEVR
            except AttributeError:
                log.debug('rpmUtils.miscutils.compareEVR is not available')

        if cmp_func is None:
            if salt.utils.which('rpmdev-vercmp'):
                # rpmdev-vercmp always uses epochs, even when zero
                def _ensure_epoch(ver):
                    def _prepend(ver):
                        return '0:{0}'.format(ver)

                    try:
                        if ':' not in ver:
                            return _prepend(ver)
                    except TypeError:
                        return _prepend(ver)
                    return ver

                ver1 = _ensure_epoch(ver1)
                ver2 = _ensure_epoch(ver2)
                result = __salt__['cmd.run'](['rpmdev-vercmp', ver1, ver2],
                                             python_shell=False,
                                             ignore_retcode=True).strip()
                if result.endswith('equal'):
                    return 0
                elif 'is newer' in result:
                    newer_version = result.split()[0]
                    if newer_version == ver1:
                        return 1
                    elif newer_version == ver2:
                        return -1
                log.warning(
                    'Failed to interpret results of rpmdev-vercmp output: %s',
                    result
                )
            else:
                # We'll need to fall back to salt.utils.version_cmp()
                log.warning(
                    'rpmdevtools is not installed, please install it for '
                    'more accurate version comparisons'
                )
        else:
            cmp_result = cmp_func(salt.utils.str_version_to_evr(ver1),
                                  salt.utils.str_version_to_evr(ver2))
            if cmp_result not in (-1, 0, 1):
                raise CommandExecutionError(
                    'Comparison result \'{0}\' is invalid'.format(cmp_result)
                )

            return cmp_result

    except Exception as exc:
        log.warning(
            'Failed to compare version \'%s\' to \'%s\' using RPM: %s',
            ver1, ver2, exc
        )

    # We would already have normalized the versions at the beginning of this
    # function if ignore_epoch=True, so avoid unnecessary work and just pass
    # False for this value.
    return salt.utils.version_cmp(ver1, ver2, ignore_epoch=False)


def checksum(*paths):
    '''
    Return if the signature of a RPM file is valid.

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.checksum /path/to/package1.rpm
        salt '*' lowpkg.checksum /path/to/package1.rpm /path/to/package2.rpm
    '''
    ret = dict()

    if not paths:
        raise CommandExecutionError("No package files has been specified.")

    for package_file in paths:
        ret[package_file] = (bool(__salt__['file.file_exists'](package_file)) and
                            not __salt__['cmd.retcode'](["rpm", "-K", "--quiet", package_file],
                                                        ignore_retcode=True,
                                                        output_loglevel='trace',
                                                        python_shell=False))

    return ret
