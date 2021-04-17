"""
Support for Apache

.. note::
    The functions in here are generic functions designed to work with
    all implementations of Apache. Debian-specific functions have been moved into
    deb_apache.py, but will still load under the ``apache`` namespace when a
    Debian-based system is detected.
"""


import io
import logging
import re
import urllib.error
import urllib.request

import salt.utils.data
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import SaltException

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load the module if apache is installed
    """
    cmd = _detect_os()
    if salt.utils.path.which(cmd):
        return "apache"
    return (
        False,
        "The apache execution module cannot be loaded: apache is not installed.",
    )


def _detect_os():
    """
    Apache commands and paths differ depending on packaging
    """
    # TODO: Add pillar support for the apachectl location
    os_family = __grains__["os_family"]
    if os_family == "RedHat":
        return "apachectl"
    elif os_family == "Debian" or os_family == "Suse":
        return "apache2ctl"
    else:
        return "apachectl"


def version():
    """
    Return server version (``apachectl -v``)

    CLI Example:

    .. code-block:: bash

        salt '*' apache.version
    """
    cmd = "{} -v".format(_detect_os())
    out = __salt__["cmd.run"](cmd).splitlines()
    ret = out[0].split(": ")
    return ret[1]


def fullversion():
    """
    Return server version (``apachectl -V``)

    CLI Example:

    .. code-block:: bash

        salt '*' apache.fullversion
    """
    cmd = "{} -V".format(_detect_os())
    ret = {}
    ret["compiled_with"] = []
    out = __salt__["cmd.run"](cmd).splitlines()
    # Example
    #  -D APR_HAS_MMAP
    define_re = re.compile(r"^\s+-D\s+")
    for line in out:
        if ": " in line:
            comps = line.split(": ")
            if not comps:
                continue
            ret[comps[0].strip().lower().replace(" ", "_")] = comps[1].strip()
        elif " -D" in line:
            cwith = define_re.sub("", line)
            ret["compiled_with"].append(cwith)
    return ret


def modules():
    """
    Return list of static and shared modules (``apachectl -M``)

    CLI Example:

    .. code-block:: bash

        salt '*' apache.modules
    """
    cmd = "{} -M".format(_detect_os())
    ret = {}
    ret["static"] = []
    ret["shared"] = []
    out = __salt__["cmd.run"](cmd).splitlines()
    for line in out:
        comps = line.split()
        if not comps:
            continue
        if "(static)" in line:
            ret["static"].append(comps[0])
        if "(shared)" in line:
            ret["shared"].append(comps[0])
    return ret


def servermods():
    """
    Return list of modules compiled into the server (``apachectl -l``)

    CLI Example:

    .. code-block:: bash

        salt '*' apache.servermods
    """
    cmd = "{} -l".format(_detect_os())
    ret = []
    out = __salt__["cmd.run"](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if ".c" in line:
            ret.append(line.strip())
    return ret


def directives():
    """
    Return list of directives together with expected arguments
    and places where the directive is valid (``apachectl -L``)

    CLI Example:

    .. code-block:: bash

        salt '*' apache.directives
    """
    cmd = "{} -L".format(_detect_os())
    ret = {}
    out = __salt__["cmd.run"](cmd)
    out = out.replace("\n\t", "\t")
    for line in out.splitlines():
        if not line:
            continue
        comps = line.split("\t")
        desc = "\n".join(comps[1:])
        ret[comps[0]] = desc
    return ret


def vhosts():
    """
    Show the settings as parsed from the config file (currently
    only shows the virtualhost settings) (``apachectl -S``).
    Because each additional virtual host adds to the execution
    time, this command may require a long timeout be specified
    by using ``-t 10``.

    CLI Example:

    .. code-block:: bash

        salt -t 10 '*' apache.vhosts
    """
    cmd = "{} -S".format(_detect_os())
    ret = {}
    namevhost = ""
    out = __salt__["cmd.run"](cmd)
    for line in out.splitlines():
        if not line:
            continue
        comps = line.split()
        if "is a NameVirtualHost" in line:
            namevhost = comps[0]
            ret[namevhost] = {}
        else:
            if comps[0] == "default":
                ret[namevhost]["default"] = {}
                ret[namevhost]["default"]["vhost"] = comps[2]
                ret[namevhost]["default"]["conf"] = re.sub(r"\(|\)", "", comps[3])
            if comps[0] == "port":
                ret[namevhost][comps[3]] = {}
                ret[namevhost][comps[3]]["vhost"] = comps[3]
                ret[namevhost][comps[3]]["conf"] = re.sub(r"\(|\)", "", comps[4])
                ret[namevhost][comps[3]]["port"] = comps[1]
    return ret


def signal(signal=None):
    """
    Signals httpd to start, restart, or stop.

    CLI Example:

    .. code-block:: bash

        salt '*' apache.signal restart
    """
    no_extra_args = ("configtest", "status", "fullstatus")
    valid_signals = ("start", "stop", "restart", "graceful", "graceful-stop")

    if signal not in valid_signals and signal not in no_extra_args:
        return
    # Make sure you use the right arguments
    if signal in valid_signals:
        arguments = " -k {}".format(signal)
    else:
        arguments = " {}".format(signal)
    cmd = _detect_os() + arguments
    out = __salt__["cmd.run_all"](cmd)

    # A non-zero return code means fail
    if out["retcode"] and out["stderr"]:
        ret = out["stderr"].strip()
    # 'apachectl configtest' returns 'Syntax OK' to stderr
    elif out["stderr"]:
        ret = out["stderr"].strip()
    elif out["stdout"]:
        ret = out["stdout"].strip()
    # No output for something like: apachectl graceful
    else:
        ret = 'Command: "{}" completed successfully!'.format(cmd)
    return ret


def useradd(pwfile, user, password, opts=""):
    """
    Add HTTP user using the ``htpasswd`` command. If the ``htpasswd`` file does not
    exist, it will be created. Valid options that can be passed are:

    .. code-block:: text

        n  Don't update file; display results on stdout.
        m  Force MD5 hashing of the password (default).
        d  Force CRYPT(3) hashing of the password.
        p  Do not hash the password (plaintext).
        s  Force SHA1 hashing of the password.

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.useradd /etc/httpd/htpasswd larry badpassword
        salt '*' apache.useradd /etc/httpd/htpasswd larry badpass opts=ns
    """
    return __salt__["webutil.useradd"](pwfile, user, password, opts)


def userdel(pwfile, user):
    """
    Delete HTTP user from the specified ``htpasswd`` file.

    CLI Example:

    .. code-block:: bash

        salt '*' apache.userdel /etc/httpd/htpasswd larry
    """
    return __salt__["webutil.userdel"](pwfile, user)


def server_status(profile="default"):
    """
    Get Information from the Apache server-status handler

    .. note::

        The server-status handler is disabled by default.
        In order for this function to work it needs to be enabled.
        See http://httpd.apache.org/docs/2.2/mod/mod_status.html

    The following configuration needs to exists in pillar/grains.
    Each entry nested in ``apache.server-status`` is a profile of a vhost/server.
    This would give support for multiple apache servers/vhosts.

    .. code-block:: yaml

        apache.server-status:
          default:
            url: http://localhost/server-status
            user: someuser
            pass: password
            realm: 'authentication realm for digest passwords'
            timeout: 5

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.server_status
        salt '*' apache.server_status other-profile
    """
    ret = {
        "Scoreboard": {
            "_": 0,
            "S": 0,
            "R": 0,
            "W": 0,
            "K": 0,
            "D": 0,
            "C": 0,
            "L": 0,
            "G": 0,
            "I": 0,
            ".": 0,
        },
    }

    # Get configuration from pillar
    url = __salt__["config.get"](
        "apache.server-status:{}:url".format(profile), "http://localhost/server-status"
    )
    user = __salt__["config.get"]("apache.server-status:{}:user".format(profile), "")
    passwd = __salt__["config.get"]("apache.server-status:{}:pass".format(profile), "")
    realm = __salt__["config.get"]("apache.server-status:{}:realm".format(profile), "")
    timeout = __salt__["config.get"](
        "apache.server-status:{}:timeout".format(profile), 5
    )

    # create authentication handler if configuration exists
    if user and passwd:
        basic = urllib.request.HTTPBasicAuthHandler()
        basic.add_password(realm=realm, uri=url, user=user, passwd=passwd)
        digest = urllib.request.HTTPDigestAuthHandler()
        digest.add_password(realm=realm, uri=url, user=user, passwd=passwd)
        urllib.request.install_opener(urllib.request.build_opener(basic, digest))

    # get http data
    url += "?auto"
    try:
        response = urllib.request.urlopen(url, timeout=timeout).read().splitlines()
    except urllib.error.URLError:
        return "error"

    # parse the data
    for line in response:
        splt = line.split(":", 1)
        splt[0] = splt[0].strip()
        splt[1] = splt[1].strip()

        if splt[0] == "Scoreboard":
            for c in splt[1]:
                ret["Scoreboard"][c] += 1
        else:
            if splt[1].isdigit():
                ret[splt[0]] = int(splt[1])
            else:
                ret[splt[0]] = float(splt[1])

    # return the good stuff
    return ret


def _parse_config(conf, slot=None):
    """
    Recursively goes through config structure and builds final Apache configuration

    :param conf: defined config structure
    :param slot: name of section container if needed
    """
    ret = io.StringIO()
    if isinstance(conf, str):
        if slot:
            print("{} {}".format(slot, conf), file=ret, end="")
        else:
            print("{}".format(conf), file=ret, end="")
    elif isinstance(conf, list):
        is_section = False
        for item in conf:
            if "this" in item:
                is_section = True
                slot_this = str(item["this"])
        if is_section:
            print("<{} {}>".format(slot, slot_this), file=ret)
            for item in conf:
                for key, val in item.items():
                    if key != "this":
                        print(_parse_config(val, str(key)), file=ret)
            print("</{}>".format(slot), file=ret)
        else:
            for value in conf:
                print(_parse_config(value, str(slot)), file=ret)
    elif isinstance(conf, dict):
        try:
            print("<{} {}>".format(slot, conf["this"]), file=ret)
        except KeyError:
            raise SaltException(
                'Apache section container "<{}>" expects attribute. '
                'Specify it using key "this".'.format(slot)
            )
        for key, value in conf.items():
            if key != "this":
                if isinstance(value, str):
                    print("{} {}".format(key, value), file=ret)
                elif isinstance(value, list):
                    print(_parse_config(value, key), file=ret)
                elif isinstance(value, dict):
                    print(_parse_config(value, key), file=ret)
        print("</{}>".format(slot), file=ret)

    ret.seek(0)
    return ret.read()


def config(name, config, edit=True):
    """
    Create VirtualHost configuration files

    name
        File for the virtual host
    config
        VirtualHost configurations

    .. note::

        This function is not meant to be used from the command line.
        Config is meant to be an ordered dict of all of the apache configs.

    CLI Example:

    .. code-block:: bash

        salt '*' apache.config /etc/httpd/conf.d/ports.conf config="[{'Listen': '22'}]"
    """

    configs = []
    for entry in config:
        key = next(iter(entry.keys()))
        configs.append(_parse_config(entry[key], key))

    # Python auto-correct line endings
    configstext = "\n".join(salt.utils.data.decode(configs))
    if edit:
        with salt.utils.files.fopen(name, "w") as configfile:
            configfile.write("# This file is managed by Salt.\n")
            configfile.write(salt.utils.stringutils.to_str(configstext))
    return configstext
