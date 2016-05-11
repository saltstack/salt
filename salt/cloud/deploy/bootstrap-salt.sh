#!/bin/sh -
#======================================================================================================================
# vim: softtabstop=4 shiftwidth=4 expandtab fenc=utf-8 spell spelllang=en cc=120
#======================================================================================================================
#
#          FILE: bootstrap-salt.sh
#
#   DESCRIPTION: Bootstrap Salt installation for various systems/distributions
#
#          BUGS: https://github.com/saltstack/salt-bootstrap/issues
#
#     COPYRIGHT: (c) 2012-2016 by the SaltStack Team, see AUTHORS.rst for more
#                details.
#
#       LICENSE: Apache 2.0
#  ORGANIZATION: SaltStack (saltstack.com)
#       CREATED: 10/15/2012 09:49:37 PM WEST
#======================================================================================================================
set -o nounset                              # Treat unset variables as an error

__ScriptVersion="2016.05.11"
__ScriptName="bootstrap-salt.sh"

#======================================================================================================================
#  Environment variables taken into account.
#----------------------------------------------------------------------------------------------------------------------
#   * BS_COLORS:                If 0 disables colour support
#   * BS_PIP_ALLOWED:           If 1 enable pip based installations(if needed)
#   * BS_PIP_ALL:               If 1 enable all python packages to be installed via pip instead of apt, requires setting virtualenv
#   * BS_VIRTUALENV_DIR:        The virtualenv to install salt into (shouldn't exist yet)
#   * BS_ECHO_DEBUG:            If 1 enable debug echo which can also be set by -D
#   * BS_SALT_ETC_DIR:          Defaults to /etc/salt (Only tweak'able on git based installations)
#   * BS_SALT_CACHE_DIR:        Defaults to /var/cache/salt (Only tweak'able on git based installations)
#   * BS_KEEP_TEMP_FILES:       If 1, don't move temporary files, instead copy them
#   * BS_FORCE_OVERWRITE:       Force overriding copied files(config, init.d, etc)
#   * BS_UPGRADE_SYS:           If 1 and an option, upgrade system. Default 0.
#   * BS_GENTOO_USE_BINHOST:    If 1 add `--getbinpkg` to gentoo's emerge
#   * BS_SALT_MASTER_ADDRESS:   The IP or DNS name of the salt-master the minion should connect to
#   * BS_SALT_GIT_CHECKOUT_DIR: The directory where to clone Salt on git installations
#======================================================================================================================


#======================================================================================================================
#  LET THE BLACK MAGIC BEGIN!!!!
#======================================================================================================================

# Bootstrap script truth values
BS_TRUE=1
BS_FALSE=0

# Default sleep time used when waiting for daemons to start, restart and checking for these running
__DEFAULT_SLEEP=3

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __detect_color_support
#   DESCRIPTION:  Try to detect color support.
#----------------------------------------------------------------------------------------------------------------------
_COLORS=${BS_COLORS:-$(tput colors 2>/dev/null || echo 0)}
__detect_color_support() {
    if [ $? -eq 0 ] && [ "$_COLORS" -gt 2 ]; then
        RC="\033[1;31m"
        GC="\033[1;32m"
        BC="\033[1;34m"
        YC="\033[1;33m"
        EC="\033[0m"
    else
        RC=""
        GC=""
        BC=""
        YC=""
        EC=""
    fi
}
__detect_color_support


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echoerr
#   DESCRIPTION:  Echo errors to stderr.
#----------------------------------------------------------------------------------------------------------------------
echoerror() {
    printf "${RC} * ERROR${EC}: %s\n" "$@" 1>&2;
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echoinfo
#   DESCRIPTION:  Echo information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echoinfo() {
    printf "${GC} *  INFO${EC}: %s\n" "$@";
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echowarn
#   DESCRIPTION:  Echo warning informations to stdout.
#----------------------------------------------------------------------------------------------------------------------
echowarn() {
    printf "${YC} *  WARN${EC}: %s\n" "$@";
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echodebug
#   DESCRIPTION:  Echo debug information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echodebug() {
    if [ "$_ECHO_DEBUG" -eq $BS_TRUE ]; then
        printf "${BC} * DEBUG${EC}: %s\n" "$@";
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_command_exists
#   DESCRIPTION:  Check if a command exists.
#----------------------------------------------------------------------------------------------------------------------
__check_command_exists() {
    command -v "$1" > /dev/null 2>&1
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_pip_allowed
#   DESCRIPTION:  Simple function to let the users know that -P needs to be
#                 used.
#----------------------------------------------------------------------------------------------------------------------
__check_pip_allowed() {
    if [ $# -eq 1 ]; then
        _PIP_ALLOWED_ERROR_MSG=$1
    else
        _PIP_ALLOWED_ERROR_MSG="pip based installations were not allowed. Retry using '-P'"
    fi

    if [ "$_PIP_ALLOWED" -eq $BS_FALSE ]; then
        echoerror "$_PIP_ALLOWED_ERROR_MSG"
        __usage
        exit 1
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __check_config_dir
#  DESCRIPTION:  Checks the config directory, retrieves URLs if provided.
#----------------------------------------------------------------------------------------------------------------------
__check_config_dir() {
    CC_DIR_NAME="$1"
    CC_DIR_BASE=$(basename "${CC_DIR_NAME}")

    case "$CC_DIR_NAME" in
        http://*|https://*)
            __fetch_url "/tmp/${CC_DIR_BASE}" "${CC_DIR_NAME}"
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
        ftp://*)
            __fetch_url "/tmp/${CC_DIR_BASE}" "${CC_DIR_NAME}"
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
        *)
            if [ ! -e "${CC_DIR_NAME}" ]; then
                echo "null"
                return 0
            fi
            ;;
    esac

    case "$CC_DIR_NAME" in
        *.tgz|*.tar.gz)
            tar -zxf "${CC_DIR_NAME}" -C /tmp
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tgz")
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tar.gz")
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
        *.tbz|*.tar.bz2)
            tar -xjf "${CC_DIR_NAME}" -C /tmp
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tbz")
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tar.bz2")
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
        *.txz|*.tar.xz)
            tar -xJf "${CC_DIR_NAME}" -C /tmp
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".txz")
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tar.xz")
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
    esac

    echo "${CC_DIR_NAME}"
}


#----------------------------------------------------------------------------------------------------------------------
#  Handle command line arguments
#----------------------------------------------------------------------------------------------------------------------
_KEEP_TEMP_FILES=${BS_KEEP_TEMP_FILES:-$BS_FALSE}
_TEMP_CONFIG_DIR="null"
_SALTSTACK_REPO_URL="git://github.com/saltstack/salt.git"
_SALT_REPO_URL=${_SALTSTACK_REPO_URL}
_DOWNSTREAM_PKG_REPO=$BS_FALSE
_TEMP_KEYS_DIR="null"
_SLEEP="${__DEFAULT_SLEEP}"
_INSTALL_MASTER=$BS_FALSE
_INSTALL_SYNDIC=$BS_FALSE
_INSTALL_MINION=$BS_TRUE
_INSTALL_CLOUD=$BS_FALSE
_VIRTUALENV_DIR=${BS_VIRTUALENV_DIR:-"null"}
_START_DAEMONS=$BS_TRUE
_ECHO_DEBUG=${BS_ECHO_DEBUG:-$BS_FALSE}
_CONFIG_ONLY=$BS_FALSE
_PIP_ALLOWED=${BS_PIP_ALLOWED:-$BS_FALSE}
_PIP_ALL=${BS_PIP_ALL:-$BS_FALSE}
_SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/etc/salt}
_SALT_CACHE_DIR=${BS_SALT_CACHE_DIR:-/var/cache/salt}
_PKI_DIR=${_SALT_ETC_DIR}/pki
_FORCE_OVERWRITE=${BS_FORCE_OVERWRITE:-$BS_FALSE}
_GENTOO_USE_BINHOST=${BS_GENTOO_USE_BINHOST:-$BS_FALSE}
_EPEL_REPO=${BS_EPEL_REPO:-epel}
_EPEL_REPOS_INSTALLED=$BS_FALSE
_UPGRADE_SYS=${BS_UPGRADE_SYS:-$BS_FALSE}
_INSECURE_DL=${BS_INSECURE_DL:-$BS_FALSE}
_WGET_ARGS=${BS_WGET_ARGS:-}
_CURL_ARGS=${BS_CURL_ARGS:-}
_FETCH_ARGS=${BS_FETCH_ARGS:-}
_ENABLE_EXTERNAL_ZMQ_REPOS=${BS_ENABLE_EXTERNAL_ZMQ_REPOS:-$BS_FALSE}
_SALT_MASTER_ADDRESS=${BS_SALT_MASTER_ADDRESS:-null}
_SALT_MINION_ID="null"
# _SIMPLIFY_VERSION is mostly used in Solaris based distributions
_SIMPLIFY_VERSION=$BS_TRUE
_LIBCLOUD_MIN_VERSION="0.14.0"
_PY_REQUESTS_MIN_VERSION="2.0"
_EXTRA_PACKAGES=""
_HTTP_PROXY=""
_DISABLE_SALT_CHECKS=$BS_FALSE
_SALT_GIT_CHECKOUT_DIR=${BS_SALT_GIT_CHECKOUT_DIR:-/tmp/git/salt}
_NO_DEPS=$BS_FALSE
_FORCE_SHALLOW_CLONE=$BS_FALSE
_DISABLE_SSL=$BS_FALSE
_DISABLE_REPOS=$BS_FALSE


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __usage
#  DESCRIPTION:  Display usage information.
#----------------------------------------------------------------------------------------------------------------------
__usage() {
    cat << EOT

  Usage :  ${__ScriptName} [options] <install-type> [install-type-args]

  Installation types:
    - stable              Install latest stable release. This is the default
                          install type
    - stable [branch]     Install latest version on a branch. Only supported
                          for packages available at repo.saltstack.com
    - stable [version]    Install a specific version. Only supported for
                          packages available at repo.saltstack.com
    - daily               Ubuntu specific: configure SaltStack Daily PPA
    - testing             RHEL-family specific: configure EPEL testing repo
    - git                 Install from the head of the develop branch
    - git [ref]           Install from any git ref (such as a branch, tag, or
                          commit)

  Examples:
    - ${__ScriptName}
    - ${__ScriptName} stable
    - ${__ScriptName} stable 2015.8
    - ${__ScriptName} stable 2015.8.9
    - ${__ScriptName} daily
    - ${__ScriptName} testing
    - ${__ScriptName} git
    - ${__ScriptName} git 2015.8
    - ${__ScriptName} git v2015.8.9
    - ${__ScriptName} git 8c3fadf15ec183e5ce8c63739850d543617e4357

  Options:
    -h  Display this message
    -v  Display script version
    -n  No colours.
    -D  Show debug output.
    -c  Temporary configuration directory
    -g  Salt repository URL. Default: ${_SALTSTACK_REPO_URL}
    -G  Instead of cloning from ${_SALTSTACK_REPO_URL}, clone from
        https://${_SALTSTACK_REPO_URL#*://}
        (Usually necessary on systems which have the regular git protocol port
        blocked, where https usually is not)
    -w  Install packages from downstream package repository rather than
        upstream, saltstack package repository.  This is currently only
        implemented for SUSE.
    -k  Temporary directory holding the minion keys which will pre-seed
        the master.
    -s  Sleep time used when waiting for daemons to start, restart and when
        checking for the services running. Default: ${__DEFAULT_SLEEP}
    -M  Also install salt-master
    -S  Also install salt-syndic
    -N  Do not install salt-minion
    -X  Do not start daemons after installation
    -C  Only run the configuration function. This option automatically bypasses
        any installation. Implies -F (forced overwrite). To overwrite master or
        syndic configs, -M or -S, respectively, must also be specified.
    -P  Allow pip based installations. On some distributions the required salt
        packages or its dependencies are not available as a package for that
        distribution. Using this flag allows the script to use pip as a last
        resort method. NOTE: This only works for functions which actually
        implement pip based installations.
    -F  Allow copied files to overwrite existing (config, init.d, etc).
    -U  If set, fully upgrade the system prior to bootstrapping salt
    -K  If set, keep the temporary files in the temporary directories specified
        with -c and -k.
    -I  If set, allow insecure connections while downloading any files. For
        example, pass '--no-check-certificate' to 'wget' or '--insecure' to
        'curl'
    -A  Pass the salt-master DNS name or IP. This will be stored under
        \${BS_SALT_ETC_DIR}/minion.d/99-master-address.conf
    -i  Pass the salt-minion id. This will be stored under
        \${BS_SALT_ETC_DIR}/minion_id
    -L  Install the Apache Libcloud package if possible(required for salt-cloud)
    -p  Extra-package to install while installing salt dependencies. One package
        per -p flag. You're responsible for providing the proper package name.
    -d  Disable check_service functions. Setting this flag disables the
        'install_<distro>_check_services' checks. You can also do this by
        touching /tmp/disable_salt_checks on the target host.
        Default: \${BS_FALSE}
    -H  Use the specified HTTP proxy for all download URLs (including https://).
        For example: http://myproxy.example.com:3128
    -Z  Enable additional package repository for newer ZeroMQ
        (Only available for RHEL/CentOS/Fedora/Ubuntu based distributions)
    -b  Assume that dependencies are already installed and software sources are
        set up. If git is selected, git tree is still checked out as dependency
        step.
    -f  Force shallow cloning for git installations.
        This may result in an "n/a" in the version number.
    -l  Disable ssl checks. When passed, switches "https" calls to "http" where
        possible.
    -V  Install salt into virtualenv(Only available for Ubuntu base distributions)
    -a  Pip install all python pkg dependencies for salt. Requires -V to install
        all pip pkgs into the virtualenv(Only available for Ubuntu base
        distributions)
    -r  Disable all repository configuration performed by this script. This
        option assumes all necessary repository configuration is already present
        on the system.

EOT
}   # ----------  end of function __usage  ----------


while getopts ":hvnDc:Gg:wk:s:MSNXCPFUKIA:i:Lp:dH:ZbflV:ar" opt
do
  case "${opt}" in

    h )  __usage; exit 0                                ;;
    v )  echo "$0 -- Version $__ScriptVersion"; exit 0  ;;
    n )  _COLORS=0; __detect_color_support              ;;
    D )  _ECHO_DEBUG=$BS_TRUE                           ;;

    c )  _TEMP_CONFIG_DIR=$(__check_config_dir "$OPTARG")
         # If the configuration directory does not exist, error out
         if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
             echoerror "Unsupported URI scheme for $OPTARG"
             exit 1
         fi
         if [ ! -d "$_TEMP_CONFIG_DIR" ]; then
             echoerror "The configuration directory ${_TEMP_CONFIG_DIR} does not exist."
             exit 1
         fi
         ;;

    g )  _SALT_REPO_URL=$OPTARG                         ;;

    G )  if [ "${_SALT_REPO_URL}" = "${_SALTSTACK_REPO_URL}" ]; then
             _SALTSTACK_REPO_URL="https://github.com/saltstack/salt.git"
             _SALT_REPO_URL=${_SALTSTACK_REPO_URL}
         else
             _SALTSTACK_REPO_URL="https://github.com/saltstack/salt.git"
         fi
         ;;

    w )  _DOWNSTREAM_PKG_REPO=$BS_TRUE                  ;;

    k )  _TEMP_KEYS_DIR="$OPTARG"
         # If the configuration directory does not exist, error out
         if [ ! -d "$_TEMP_KEYS_DIR" ]; then
             echoerror "The pre-seed keys directory ${_TEMP_KEYS_DIR} does not exist."
             exit 1
         fi
         ;;
    s )  _SLEEP=$OPTARG                                 ;;
    M )  _INSTALL_MASTER=$BS_TRUE                       ;;
    S )  _INSTALL_SYNDIC=$BS_TRUE                       ;;
    N )  _INSTALL_MINION=$BS_FALSE                      ;;
    X )  _START_DAEMONS=$BS_FALSE                       ;;
    C )  _CONFIG_ONLY=$BS_TRUE                          ;;
    P )  _PIP_ALLOWED=$BS_TRUE                          ;;
    F )  _FORCE_OVERWRITE=$BS_TRUE                      ;;
    U )  _UPGRADE_SYS=$BS_TRUE                          ;;
    K )  _KEEP_TEMP_FILES=$BS_TRUE                      ;;
    I )  _INSECURE_DL=$BS_TRUE                          ;;
    A )  _SALT_MASTER_ADDRESS=$OPTARG                   ;;
    i )  _SALT_MINION_ID=$OPTARG                        ;;
    L )  _INSTALL_CLOUD=$BS_TRUE                        ;;
    p )  _EXTRA_PACKAGES="$_EXTRA_PACKAGES $OPTARG"     ;;
    d )  _DISABLE_SALT_CHECKS=$BS_TRUE                  ;;
    H )  _HTTP_PROXY="$OPTARG"                          ;;
    Z )  _ENABLE_EXTERNAL_ZMQ_REPOS=$BS_TRUE            ;;
    b )  _NO_DEPS=$BS_TRUE                              ;;
    f )  _FORCE_SHALLOW_CLONE=$BS_TRUE                  ;;
    l )  _DISABLE_SSL=$BS_TRUE                          ;;
    V )  _VIRTUALENV_DIR="$OPTARG"                      ;;
    a )  _PIP_ALL=$BS_TRUE                              ;;
    r )  _DISABLE_REPOS=$BS_TRUE                        ;;

    \?)  echo
         echoerror "Option does not exist : $OPTARG"
         __usage
         exit 1
         ;;

  esac    # --- end of case ---
done
shift $((OPTIND-1))


__check_unparsed_options() {
    shellopts="$1"
    # grep alternative for SunOS
    if [ -f /usr/xpg4/bin/grep ]; then
        grep='/usr/xpg4/bin/grep'
    else
        grep='grep'
    fi
    unparsed_options=$( echo "$shellopts" | ${grep} -E '(^|[[:space:]])[-]+[[:alnum:]]' )
    if [ "$unparsed_options" != "" ]; then
        __usage
        echo
        echoerror "options are only allowed before install arguments"
        echo
        exit 1
    fi
}


# Check that we're actually installing one of minion/master/syndic
if [ "$_INSTALL_MINION" -eq $BS_FALSE ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    echowarn "Nothing to install or configure"
    exit 0
fi

# Check that we're installing a minion if we're being passed a master address
if [ "$_INSTALL_MINION" -eq $BS_FALSE ] && [ "$_SALT_MASTER_ADDRESS" != "null" ]; then
    echoerror "Don't pass a master address (-A) if no minion is going to be bootstrapped."
    exit 1
fi

# Check that we're installing a minion if we're being passed a minion id
if [ "$_INSTALL_MINION" -eq $BS_FALSE ] && [ "$_SALT_MINION_ID" != "null" ]; then
    echoerror "Don't pass a minion id (-i) if no minion is going to be bootstrapped."
    exit 1
fi


# Define installation type
if [ "$#" -eq 0 ];then
    ITYPE="stable"
else
    __check_unparsed_options "$*"
    ITYPE=$1
    shift
fi

# Check installation type
if [ "$(echo "$ITYPE" | egrep '(stable|testing|daily|git)')" = "" ]; then
    echoerror "Installation type \"$ITYPE\" is not known..."
    exit 1
fi

# If doing a git install, check what branch/tag/sha will be checked out
if [ "$ITYPE" = "git" ]; then
    if [ "$#" -eq 0 ];then
        GIT_REV="develop"
    else
        __check_unparsed_options "$*"
        GIT_REV="$1"
        shift
    fi
# If doing stable install, check if version specified
elif [ "$ITYPE" = "stable" ]; then
    if [ "$#" -eq 0 ];then
        STABLE_REV="latest"
    else
        __check_unparsed_options "$*"
        if [ "$(echo "$1" | egrep '^(latest|1\.6|1\.7|2014\.1|2014\.7|2015\.5|2015\.8)$')" != "" ]; then
          STABLE_REV="$1"
          shift
        elif [ "$(echo "$1" | egrep '^([0-9]*\.[0-9]*\.[0-9]*)$')" != "" ]; then
          STABLE_REV="archive/$1"
          shift
        else
          echo "Unknown stable version: $1 (valid: 1.6, 1.7, 2014.1, 2014.7, 2015.5, 2015.8, latest, \$MAJOR.\$MINOR.\$PATCH)"
          exit 1

        fi
    fi
fi

# -a and -V only work from git
if [ "$ITYPE" != "git" ]; then
    if [ $_PIP_ALL -eq $BS_TRUE ]; then
        echoerror "Pip installing all python packages with -a is only possible when installing salt via git"
        exit 1
    fi
    if [ "$_VIRTUALENV_DIR" != "null" ]; then
        echoerror "Virtualenv installs via -V is only possible when installing salt via git"
        exit 1
    fi
fi

# Check for any unparsed arguments. Should be an error.
if [ "$#" -gt 0 ]; then
    __check_unparsed_options "$*"
    __usage
    echo
    echoerror "Too many arguments."
    exit 1
fi

# Check the _DISABLE_SSL value and set HTTP or HTTPS.
if [ "$_DISABLE_SSL" -eq "${BS_TRUE}" ]; then
    HTTP_VAL="http"
else
    HTTP_VAL="https"
fi

# whoami alternative for SunOS
if [ -f /usr/xpg4/bin/id ]; then
    whoami='/usr/xpg4/bin/id -un'
else
    whoami='whoami'
fi

# Root permissions are required to run this script
if [ "$(${whoami})" != "root" ]; then
    echoerror "Salt requires root privileges to install. Please re-run this script as root."
    exit 1
fi

# Export the http_proxy configuration to our current environment
if [ "${_HTTP_PROXY}" != "" ]; then
    export http_proxy="$_HTTP_PROXY"
    export https_proxy="$_HTTP_PROXY"
fi

# Let's discover how we're being called
# shellcheck disable=SC2009
CALLER=$(ps -a -o pid,args | grep $$ | grep -v grep | tr -s ' ' | cut -d ' ' -f 3)

if [ "${CALLER}x" = "${0}x" ]; then
    CALLER="PIPED THROUGH"
fi

# Work around for 'Docker + salt-bootstrap failure' https://github.com/saltstack/salt-bootstrap/issues/394
if [ ${_DISABLE_SALT_CHECKS} -eq 0 ]; then
    [ -f /tmp/disable_salt_checks ] && _DISABLE_SALT_CHECKS=$BS_TRUE && \
        echowarn "Found file: /tmp/disable_salt_checks, setting \$_DISABLE_SALT_CHECKS=true"
fi

# Because -a can only be installed into virtualenv
if ([ $_PIP_ALL -eq $BS_TRUE ] && [ "$_VIRTUALENV_DIR" = "null" ]); then
    usage
    # Could possibly set up a default virtualenv location when -a flag is passed
    echoerror "Using -a requires -V because pip pkgs should be siloed from python system pkgs"
    exit 1
fi

# Make sure virtualenv directory does not already exist
if [ -d "$_VIRTUALENV_DIR" ]; then
    echoerror "The directory ${_VIRTUALENV_DIR} for virtualenv already exists"
    exit 1
fi

echoinfo "${CALLER} ${0} -- Version ${__ScriptVersion}"
#echowarn "Running the unstable version of ${__ScriptName}"

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __exit_cleanup
#   DESCRIPTION:  Cleanup any leftovers after script has ended
#
#
#   http://www.unix.com/man-page/POSIX/1posix/trap/
#
#               Signal Number   Signal Name
#               1               SIGHUP
#               2               SIGINT
#               3               SIGQUIT
#               6               SIGABRT
#               9               SIGKILL
#              14               SIGALRM
#              15               SIGTERM
#----------------------------------------------------------------------------------------------------------------------
__exit_cleanup() {
    EXIT_CODE=$?

    if [ "$ITYPE" = "git" ] && [ -d "${_SALT_GIT_CHECKOUT_DIR}" ]; then
        if [ $_KEEP_TEMP_FILES -eq $BS_FALSE ]; then
            # Clean up the checked out repository
            echodebug "Cleaning up the Salt Temporary Git Repository"
            # shellcheck disable=SC2164
            cd "${__SALT_GIT_CHECKOUT_PARENT_DIR}"
            rm -rf "${_SALT_GIT_CHECKOUT_DIR}"
        else
            echowarn "Not cleaning up the Salt Temporary git repository on request"
            echowarn "Note that if you intend to re-run this script using the git approach, you might encounter some issues"
        fi
    fi

    # Remove the logging pipe when the script exits
    echodebug "Removing the logging pipe $LOGPIPE"
    rm -f "$LOGPIPE"

    # Kill tee when exiting, CentOS, at least requires this
    # shellcheck disable=SC2009
    TEE_PID=$(ps ax | grep tee | grep "$LOGFILE" | awk '{print $1}')

    [ "$TEE_PID" = "" ] && exit $EXIT_CODE

    echodebug "Killing logging pipe tee's with pid(s): $TEE_PID"

    # We need to trap errors since killing tee will cause a 127 errno
    # We also do this as late as possible so we don't "mis-catch" other errors
    __trap_errors() {
        echoinfo "Errors Trapped: $EXIT_CODE"
        # Exit with the "original" exit code, not the trapped code
        exit $EXIT_CODE
    }
    trap "__trap_errors" INT ABRT QUIT TERM

    # Now we're "good" to kill tee
    kill -s TERM "$TEE_PID"

    # In case the 127 errno is not triggered, exit with the "original" exit code
    exit $EXIT_CODE
}
trap "__exit_cleanup" EXIT INT


# Define our logging file and pipe paths
LOGFILE="/tmp/$( echo $__ScriptName | sed s/.sh/.log/g )"
LOGPIPE="/tmp/$( echo $__ScriptName | sed s/.sh/.logpipe/g )"

# Create our logging pipe
# On FreeBSD we have to use mkfifo instead of mknod
mknod "$LOGPIPE" p >/dev/null 2>&1 || mkfifo "$LOGPIPE" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echoerror "Failed to create the named pipe required to log"
    exit 1
fi

# What ever is written to the logpipe gets written to the logfile
tee < "$LOGPIPE" "$LOGFILE" &

# Close STDOUT, reopen it directing it to the logpipe
exec 1>&-
exec 1>"$LOGPIPE"
# Close STDERR, reopen it directing it to the logpipe
exec 2>&-
exec 2>"$LOGPIPE"


# Handle the insecure flags
if [ "$_INSECURE_DL" -eq $BS_TRUE ]; then
    _CURL_ARGS="${_CURL_ARGS} --insecure"
    _WGET_ARGS="${_WGET_ARGS} --no-check-certificate"
    _FETCH_ARGS="${_FETCH_ARGS} --no-verify-peer"
fi

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __fetch_url
#  DESCRIPTION:  Retrieves a URL and writes it to a given path
#----------------------------------------------------------------------------------------------------------------------
__fetch_url() {
    # shellcheck disable=SC2086
    curl $_CURL_ARGS -L -s -o "$1" "$2" >/dev/null 2>&1 ||
        wget $_WGET_ARGS -q -O "$1" "$2" >/dev/null 2>&1 ||
            fetch $_FETCH_ARGS -q -o "$1" "$2" >/dev/null 2>&1 ||
                fetch -q -o "$1" "$2" >/dev/null 2>&1 ||        # Pre FreeBSD 10
                    ftp -o "$1" "$2" >/dev/null 2>&1            # OpenBSD
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __fetch_verify
#  DESCRIPTION:  Retrieves a URL, verifies its content and writes it to standard output
#----------------------------------------------------------------------------------------------------------------------
__fetch_verify() {
    fetch_verify_url="$1"
    fetch_verify_sum="$2"
    fetch_verify_size="$3"

    fetch_verify_tmpf=$(mktemp) && \
    __fetch_url "$fetch_verify_tmpf" "$fetch_verify_url" && \
    test "$(stat --format=%s "$fetch_verify_tmpf")" -eq "$fetch_verify_size" && \
    test "$(md5sum "$fetch_verify_tmpf" | awk '{ print $1 }')" = "$fetch_verify_sum" && \
    cat "$fetch_verify_tmpf" && \
    rm -f "$fetch_verify_tmpf"
    if [ $? -eq 0 ]; then
        return 0
    fi
    echo "Failed verification of $fetch_verify_url"
    return 1
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_hardware_info
#   DESCRIPTION:  Discover hardware information
#----------------------------------------------------------------------------------------------------------------------
__gather_hardware_info() {
    if [ -f /proc/cpuinfo ]; then
        CPU_VENDOR_ID=$(awk '/vendor_id|Processor/ {sub(/-.*$/,"",$3); print $3; exit}' /proc/cpuinfo )
    elif [ -f /usr/bin/kstat ]; then
        # SmartOS.
        # Solaris!?
        # This has only been tested for a GenuineIntel CPU
        CPU_VENDOR_ID=$(/usr/bin/kstat -p cpu_info:0:cpu_info0:vendor_id | awk '{print $2}')
    else
        CPU_VENDOR_ID=$( sysctl -n hw.model )
    fi
    # shellcheck disable=SC2034
    CPU_VENDOR_ID_L=$( echo "$CPU_VENDOR_ID" | tr '[:upper:]' '[:lower:]' )
    CPU_ARCH=$(uname -m 2>/dev/null || uname -p 2>/dev/null || echo "unknown")
    CPU_ARCH_L=$( echo "$CPU_ARCH" | tr '[:upper:]' '[:lower:]' )
}
__gather_hardware_info


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_os_info
#   DESCRIPTION:  Discover operating system information
#----------------------------------------------------------------------------------------------------------------------
__gather_os_info() {
    OS_NAME=$(uname -s 2>/dev/null)
    OS_NAME_L=$( echo "$OS_NAME" | tr '[:upper:]' '[:lower:]' )
    OS_VERSION=$(uname -r)
    # shellcheck disable=SC2034
    OS_VERSION_L=$( echo "$OS_VERSION" | tr '[:upper:]' '[:lower:]' )
}
__gather_os_info


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __parse_version_string
#   DESCRIPTION:  Parse version strings ignoring the revision.
#                 MAJOR.MINOR.REVISION becomes MAJOR.MINOR
#----------------------------------------------------------------------------------------------------------------------
__parse_version_string() {
    VERSION_STRING="$1"
    PARSED_VERSION=$(
        echo "$VERSION_STRING" |
        sed -e 's/^/#/' \
            -e 's/^#[^0-9]*\([0-9][0-9]*\.[0-9][0-9]*\)\(\.[0-9][0-9]*\).*$/\1/' \
            -e 's/^#[^0-9]*\([0-9][0-9]*\.[0-9][0-9]*\).*$/\1/' \
            -e 's/^#[^0-9]*\([0-9][0-9]*\).*$/\1/' \
            -e 's/^#.*$//'
    )
    echo "$PARSED_VERSION"
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __derive_debian_numeric_version
#   DESCRIPTION:  Derive the numeric version from a Debian version string.
#----------------------------------------------------------------------------------------------------------------------
__derive_debian_numeric_version() {
    NUMERIC_VERSION=""
    INPUT_VERSION="$1"
    if echo "$INPUT_VERSION" | grep -q '^[0-9]'; then
        NUMERIC_VERSION="$INPUT_VERSION"
    elif [ -z "$INPUT_VERSION" ] && [ -f "/etc/debian_version" ]; then
        INPUT_VERSION="$(cat /etc/debian_version)"
    fi
    if [ -z "$NUMERIC_VERSION" ]; then
        if [ "$INPUT_VERSION" = "wheezy/sid" ]; then
            # I've found an EC2 wheezy image which did not tell its version
            NUMERIC_VERSION=$(__parse_version_string "7.0")
        elif [ "$INPUT_VERSION" = "jessie/sid" ]; then
            # Let's start detecting the upcoming Debian 8 (Jessie)
            NUMERIC_VERSION=$(__parse_version_string "8.0")
        else
            echowarn "Unable to parse the Debian Version (codename: '$INPUT_VERSION')"
        fi
    fi
    echo "$NUMERIC_VERSION"
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __unquote_string
#   DESCRIPTION:  Strip single or double quotes from the provided string.
#----------------------------------------------------------------------------------------------------------------------
__unquote_string() {
    echo "${@}" | sed "s/^\([\"']\)\(.*\)\1\$/\2/g"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __camelcase_split
#   DESCRIPTION:  Convert CamelCased strings to Camel_Cased
#----------------------------------------------------------------------------------------------------------------------
__camelcase_split() {
    echo "${@}" | sed -r 's/([^A-Z-])([A-Z])/\1 \2/g'
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __strip_duplicates
#   DESCRIPTION:  Strip duplicate strings
#----------------------------------------------------------------------------------------------------------------------
__strip_duplicates() {
    echo "${@}" | tr -s '[:space:]' '\n' | awk '!x[$0]++'
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __sort_release_files
#   DESCRIPTION:  Custom sort function. Alphabetical or numerical sort is not
#                 enough.
#----------------------------------------------------------------------------------------------------------------------
__sort_release_files() {
    KNOWN_RELEASE_FILES=$(echo "(arch|centos|debian|ubuntu|fedora|redhat|suse|\
        mandrake|mandriva|gentoo|slackware|turbolinux|unitedlinux|lsb|system|\
        oracle|os)(-|_)(release|version)" | sed -r 's:[[:space:]]::g')
    primary_release_files=""
    secondary_release_files=""
    # Sort know VS un-known files first
    for release_file in $(echo "${@}" | sed -r 's:[[:space:]]:\n:g' | sort --unique --ignore-case); do
        match=$(echo "$release_file" | egrep -i "${KNOWN_RELEASE_FILES}")
        if [ "${match}" != "" ]; then
            primary_release_files="${primary_release_files} ${release_file}"
        else
            secondary_release_files="${secondary_release_files} ${release_file}"
        fi
    done

    # Now let's sort by know files importance, max important goes last in the max_prio list
    max_prio="redhat-release centos-release oracle-release"
    for entry in $max_prio; do
        if [ "$(echo "${primary_release_files}" | grep "$entry")" != "" ]; then
            primary_release_files=$(echo "${primary_release_files}" | sed -e "s:\(.*\)\($entry\)\(.*\):\2 \1 \3:g")
        fi
    done
    # Now, least important goes last in the min_prio list
    min_prio="lsb-release"
    for entry in $min_prio; do
        if [ "$(echo "${primary_release_files}" | grep "$entry")" != "" ]; then
            primary_release_files=$(echo "${primary_release_files}" | sed -e "s:\(.*\)\($entry\)\(.*\):\1 \3 \2:g")
        fi
    done

    # Echo the results collapsing multiple white-space into a single white-space
    echo "${primary_release_files} ${secondary_release_files}" | sed -r 's:[[:space:]]+:\n:g'
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_linux_system_info
#   DESCRIPTION:  Discover Linux system information
#----------------------------------------------------------------------------------------------------------------------
__gather_linux_system_info() {
    DISTRO_NAME=""
    DISTRO_VERSION=""

    # Let's test if the lsb_release binary is available
    rv=$(lsb_release >/dev/null 2>&1)
    if [ $? -eq 0 ]; then
        DISTRO_NAME=$(lsb_release -si)
        if [ "${DISTRO_NAME}" = "Scientific" ]; then
            DISTRO_NAME="Scientific Linux"
        elif [ "$(echo "$DISTRO_NAME" | grep RedHat)" != "" ]; then
            # Let's convert CamelCase to Camel Case
            DISTRO_NAME=$(__camelcase_split "$DISTRO_NAME")
        elif [ "${DISTRO_NAME}" = "openSUSE project" ]; then
            # lsb_release -si returns "openSUSE project" on openSUSE 12.3
            DISTRO_NAME="opensuse"
        elif [ "${DISTRO_NAME}" = "SUSE LINUX" ]; then
            if [ "$(lsb_release -sd | grep -i opensuse)" != "" ]; then
                # openSUSE 12.2 reports SUSE LINUX on lsb_release -si
                DISTRO_NAME="opensuse"
            else
                # lsb_release -si returns "SUSE LINUX" on SLES 11 SP3
                DISTRO_NAME="suse"
            fi
        elif [ "${DISTRO_NAME}" = "EnterpriseEnterpriseServer" ]; then
            # This the Oracle Linux Enterprise ID before ORACLE LINUX 5 UPDATE 3
            DISTRO_NAME="Oracle Linux"
        elif [ "${DISTRO_NAME}" = "OracleServer" ]; then
            # This the Oracle Linux Server 6.5
            DISTRO_NAME="Oracle Linux"
        elif [ "${DISTRO_NAME}" = "AmazonAMI" ]; then
            DISTRO_NAME="Amazon Linux AMI"
        elif [ "${DISTRO_NAME}" = "Arch" ]; then
            DISTRO_NAME="Arch Linux"
            return
        elif [ "${DISTRO_NAME}" = "Raspbian" ]; then
           DISTRO_NAME="Debian"
        fi
        rv=$(lsb_release -sr)
        [ "${rv}" != "" ] && DISTRO_VERSION=$(__parse_version_string "$rv")
    elif [ -f /etc/lsb-release ]; then
        # We don't have the lsb_release binary, though, we do have the file it parses
        DISTRO_NAME=$(grep DISTRIB_ID /etc/lsb-release | sed -e 's/.*=//')
        rv=$(grep DISTRIB_RELEASE /etc/lsb-release | sed -e 's/.*=//')
        [ "${rv}" != "" ] && DISTRO_VERSION=$(__parse_version_string "$rv")
    fi

    if [ "$DISTRO_NAME" != "" ] && [ "$DISTRO_VERSION" != "" ]; then
        # We already have the distribution name and version
        return
    fi

    # shellcheck disable=SC2035,SC2086
    for rsource in $(__sort_release_files "$(
            cd /etc && /bin/ls *[_-]release *[_-]version 2>/dev/null | env -i sort | \
            sed -e '/^redhat-release$/d' -e '/^lsb-release$/d'; \
            echo redhat-release lsb-release
            )"); do

        [ -L "/etc/${rsource}" ] && continue        # Don't follow symlinks
        [ ! -f "/etc/${rsource}" ] && continue      # Does not exist

        n=$(echo "${rsource}" | sed -e 's/[_-]release$//' -e 's/[_-]version$//')
        shortname=$(echo "${n}" | tr '[:upper:]' '[:lower:]')
        if [ "$shortname" = "debian" ]; then
            rv=$(__derive_debian_numeric_version "$(cat /etc/${rsource})")
        else
            rv=$( (grep VERSION "/etc/${rsource}"; cat "/etc/${rsource}") | grep '[0-9]' | sed -e 'q' )
        fi
        [ "${rv}" = "" ] && [ "$shortname" != "arch" ] && continue  # There's no version information. Continue to next rsource
        v=$(__parse_version_string "$rv")
        case $shortname in
            redhat             )
                if [ "$(egrep 'CentOS' /etc/${rsource})" != "" ]; then
                    n="CentOS"
                elif [ "$(egrep 'Scientific' /etc/${rsource})" != "" ]; then
                    n="Scientific Linux"
                elif [ "$(egrep 'Red Hat Enterprise Linux' /etc/${rsource})" != "" ]; then
                    n="<R>ed <H>at <E>nterprise <L>inux"
                else
                    n="<R>ed <H>at <L>inux"
                fi
                ;;
            arch               ) n="Arch Linux"     ;;
            centos             ) n="CentOS"         ;;
            debian             ) n="Debian"         ;;
            ubuntu             ) n="Ubuntu"         ;;
            fedora             ) n="Fedora"         ;;
            suse               ) n="SUSE"           ;;
            mandrake*|mandriva ) n="Mandriva"       ;;
            gentoo             ) n="Gentoo"         ;;
            slackware          ) n="Slackware"      ;;
            turbolinux         ) n="TurboLinux"     ;;
            unitedlinux        ) n="UnitedLinux"    ;;
            oracle             ) n="Oracle Linux"   ;;
            system             )
                while read -r line; do
                    [ "${n}x" != "systemx" ] && break
                    case "$line" in
                        *Amazon*Linux*AMI*)
                            n="Amazon Linux AMI"
                            break
                    esac
                done < "/etc/${rsource}"
                ;;
            os                 )
                nn="$(__unquote_string "$(grep '^ID=' /etc/os-release | sed -e 's/^ID=\(.*\)$/\1/g')")"
                rv="$(__unquote_string "$(grep '^VERSION_ID=' /etc/os-release | sed -e 's/^VERSION_ID=\(.*\)$/\1/g')")"
                [ "${rv}" != "" ] && v=$(__parse_version_string "$rv") || v=""
                case $(echo "${nn}" | tr '[:upper:]' '[:lower:]') in
                    amzn        )
                        # Amazon AMI's after 2014.09 match here
                        n="Amazon Linux AMI"
                        ;;
                    arch        )
                        n="Arch Linux"
                        v=""  # Arch Linux does not provide a version.
                        ;;
                    debian      )
                        n="Debian"
                        v=$(__derive_debian_numeric_version "$v")
                        ;;
                    sles        )
                        n="SUSE"
                        v="${rv}"
                        ;;
                    *           )
                        n=${nn}
                        ;;
                esac
                ;;
            *                  ) n="${n}"           ;
        esac
        DISTRO_NAME=$n
        DISTRO_VERSION=$v
        break
    done
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_sunos_system_info
#   DESCRIPTION:  Discover SunOS system info
#----------------------------------------------------------------------------------------------------------------------
__gather_sunos_system_info() {
    if [ -f /sbin/uname ]; then
        DISTRO_VERSION=$(/sbin/uname -X | awk '/[kK][eE][rR][nN][eE][lL][iI][dD]/ { print $3 }')
    fi

    DISTRO_NAME=""
    if [ -f /etc/release ]; then
        while read -r line; do
            [ "${DISTRO_NAME}" != "" ] && break
            case "$line" in
                *OpenIndiana*oi_[0-9]*)
                    DISTRO_NAME="OpenIndiana"
                    DISTRO_VERSION=$(echo "$line" | sed -nr "s/OpenIndiana(.*)oi_([[:digit:]]+)(.*)/\2/p")
                    break
                    ;;
                *OpenSolaris*snv_[0-9]*)
                    DISTRO_NAME="OpenSolaris"
                    DISTRO_VERSION=$(echo "$line" | sed -nr "s/OpenSolaris(.*)snv_([[:digit:]]+)(.*)/\2/p")
                    break
                    ;;
                *Oracle*Solaris*[0-9]*)
                    DISTRO_NAME="Oracle Solaris"
                    DISTRO_VERSION=$(echo "$line" | sed -nr "s/(Oracle Solaris) ([[:digit:]]+)(.*)/\2/p")
                    break
                    ;;
                *Solaris*)
                    DISTRO_NAME="Solaris"
                    # Let's make sure we not actually on a Joyent's SmartOS VM since some releases
                    # don't have SmartOS in `/etc/release`, only `Solaris`
                    uname -v | grep joyent >/dev/null 2>&1
                    if [ $? -eq 0 ]; then
                        DISTRO_NAME="SmartOS"
                    fi
                    break
                    ;;
                *NexentaCore*)
                    DISTRO_NAME="Nexenta Core"
                    break
                    ;;
                *SmartOS*)
                    DISTRO_NAME="SmartOS"
                    break
                    ;;
                *OmniOS*)
                    DISTRO_NAME="OmniOS"
                    DISTRO_VERSION=$(echo "$line" | awk '{print $3}')
                    _SIMPLIFY_VERSION=$BS_FALSE
                    break
                    ;;
            esac
        done < /etc/release
    fi

    if [ "${DISTRO_NAME}" = "" ]; then
        DISTRO_NAME="Solaris"
        DISTRO_VERSION=$(
            echo "${OS_VERSION}" |
            sed -e 's;^4\.;1.;' \
                -e 's;^5\.\([0-6]\)[^0-9]*$;2.\1;' \
                -e 's;^5\.\([0-9][0-9]*\).*;\1;'
        )
    fi

    if [ "${DISTRO_NAME}" = "SmartOS" ]; then
        VIRTUAL_TYPE="smartmachine"
        if [ "$(zonename)" = "global" ]; then
            VIRTUAL_TYPE="global"
        fi
    fi
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_bsd_system_info
#   DESCRIPTION:  Discover OpenBSD, NetBSD and FreeBSD systems information
#----------------------------------------------------------------------------------------------------------------------
__gather_bsd_system_info() {
    DISTRO_NAME=${OS_NAME}
    DISTRO_VERSION=$(echo "${OS_VERSION}" | sed -e 's;[()];;' -e 's/-.*$//')
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_system_info
#   DESCRIPTION:  Discover which system and distribution we are running.
#----------------------------------------------------------------------------------------------------------------------
__gather_system_info() {
    case ${OS_NAME_L} in
        linux )
            __gather_linux_system_info
            ;;
        sunos )
            __gather_sunos_system_info
            ;;
        openbsd|freebsd|netbsd )
            __gather_bsd_system_info
            ;;
        * )
            echoerror "${OS_NAME} not supported.";
            exit 1
            ;;
    esac

}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __ubuntu_derivatives_translation
#   DESCRIPTION:  Map Ubuntu derivatives to their Ubuntu base versions.
#                 If distro has a known Ubuntu base version, use those install
#                 functions by pretending to be Ubuntu (i.e. change global vars)
#----------------------------------------------------------------------------------------------------------------------
# shellcheck disable=SC2034
__ubuntu_derivatives_translation() {
    UBUNTU_DERIVATIVES="(trisquel|linuxmint|linaro|elementary_os)"
    # Mappings
    trisquel_6_ubuntu_base="12.04"
    linuxmint_13_ubuntu_base="12.04"
    linuxmint_14_ubuntu_base="12.10"
    #linuxmint_15_ubuntu_base="13.04"
    # Bug preventing add-apt-repository from working on Mint 15:
    # https://bugs.launchpad.net/linuxmint/+bug/1198751

    linuxmint_16_ubuntu_base="13.10"
    linuxmint_17_ubuntu_base="14.04"
    linaro_12_ubuntu_base="12.04"
    elementary_os_02_ubuntu_base="12.04"

    # Translate Ubuntu derivatives to their base Ubuntu version
    match=$(echo "$DISTRO_NAME_L" | egrep ${UBUNTU_DERIVATIVES})

    if [ "${match}" != "" ]; then
        case $match in
            "elementary_os")
                _major=$(echo "$DISTRO_VERSION" | sed 's/\.//g')
                ;;
            "linuxmint")
                export LSB_ETC_LSB_RELEASE=/etc/upstream-release/lsb-release
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                ;;
            *)
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                ;;
        esac

        _ubuntu_version=$(eval echo "\$${match}_${_major}_ubuntu_base")

        if [ "$_ubuntu_version" != "" ]; then
            echodebug "Detected Ubuntu $_ubuntu_version derivative"
            DISTRO_NAME_L="ubuntu"
            DISTRO_VERSION="$_ubuntu_version"
        fi
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __ubuntu_codename_translation
#   DESCRIPTION:  Map Ubuntu major versions to their corresponding codenames
#----------------------------------------------------------------------------------------------------------------------
# shellcheck disable=SC2034
__ubuntu_codename_translation() {

    case $DISTRO_MINOR_VERSION in
        "04")
            _april="yes"
            ;;
        "10")
            _april=""
            ;;
        *)
            _april="yes"
            ;;
    esac

    case $DISTRO_MAJOR_VERSION in
        "12")
            DISTRO_CODENAME="precise"
            ;;
        "14")
            DISTRO_CODENAME="trusty"
            ;;
        "15")
            if [ -n "$_april" ]; then
                DISTRO_CODENAME="vivid"
            else
                DISTRO_CODENAME="wily"
            fi
            ;;
        *)
            DISTRO_CODENAME="trusty"
            ;;
    esac
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __debian_derivatives_translation
#   DESCRIPTION:  Map Debian derivatives to their Debian base versions.
#                 If distro has a known Debian base version, use those install
#                 functions by pretending to be Debian (i.e. change global vars)
#----------------------------------------------------------------------------------------------------------------------
# shellcheck disable=SC2034
__debian_derivatives_translation() {

    # If the file does not exist, return
    [ ! -f /etc/os-release ] && return

    DEBIAN_DERIVATIVES="(kali|linuxmint)"
    # Mappings
    kali_1_debian_base="7.0"
    linuxmint_1_debian_base="8.0"

    # Detect derivates, Kali and LinuxMint *only* for now
    rv=$(grep ^ID= /etc/os-release | sed -e 's/.*=//')

    # Translate Debian derivatives to their base Debian version
    match=$(echo "$rv" | egrep ${DEBIAN_DERIVATIVES})

    if [ "${match}" != "" ]; then
        case $match in
            kali)
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                _debian_derivative="kali"
                ;;
            linuxmint)
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                _debian_derivative="linuxmint"
                ;;
        esac

        _debian_version=$(eval echo "\$${_debian_derivative}_${_major}_debian_base")

        if [ "$_debian_version" != "" ]; then
            echodebug "Detected Debian $_debian_version derivative"
            DISTRO_NAME_L="debian"
            DISTRO_VERSION="$_debian_version"
        fi
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __set_suse_pkg_repo
#   DESCRIPTION:  Set SUSE_PKG_URL to either the upstream SaltStack repo or the
#                 downstream SUSE repo
#----------------------------------------------------------------------------------------------------------------------
__set_suse_pkg_repo() {
    suse_pkg_url_path="${DISTRO_REPO}/systemsmanagement:saltstack.repo"
    if [ "$_DOWNSTREAM_PKG_REPO" -eq $BS_TRUE ]; then
        # FIXME: cleartext download over unsecure protocol (HTTP)
        suse_pkg_url_base="http://download.opensuse.org/repositories/systemsmanagement:saltstack"
    else
        suse_pkg_url_base="${HTTP_VAL}://repo.saltstack.com/opensuse"
    fi
    SUSE_PKG_URL="$suse_pkg_url_base/$suse_pkg_url_path"
}

__gather_system_info

echo
echoinfo "System Information:"
echoinfo "  CPU:          ${CPU_VENDOR_ID}"
echoinfo "  CPU Arch:     ${CPU_ARCH}"
echoinfo "  OS Name:      ${OS_NAME}"
echoinfo "  OS Version:   ${OS_VERSION}"
echoinfo "  Distribution: ${DISTRO_NAME} ${DISTRO_VERSION}"
echo

echodebug "Binaries will be searched using the following \$PATH: ${PATH}"

# Let users know that we'll use a proxy
if [ "${_HTTP_PROXY}" != "" ]; then
    echoinfo "Using http proxy $_HTTP_PROXY"
fi

# Let users know what's going to be installed/configured
if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
    if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
        echoinfo "Installing minion"
    else
        echoinfo "Configuring minion"
    fi
fi

if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
    if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
        echoinfo "Installing master"
    else
        echoinfo "Configuring master"
    fi
fi

if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
    if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
        echoinfo "Installing syndic"
    else
        echoinfo "Configuring syndic"
    fi
fi

if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ] && [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    echoinfo "Installing Apache-Libcloud required for salt-cloud"
fi

if [ $_START_DAEMONS -eq $BS_FALSE ]; then
    echoinfo "Daemons will not be started"
fi

# Simplify distro name naming on functions
DISTRO_NAME_L=$(echo "$DISTRO_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-zA-Z0-9_ ]//g' | sed -re 's/([[:space:]])+/_/g')

# For Ubuntu derivatives, pretend to be their Ubuntu base version
__ubuntu_derivatives_translation

# For Debian derivates, pretend to be their Debian base version
__debian_derivatives_translation

# Simplify version naming on functions
if [ "$DISTRO_VERSION" = "" ] || [ ${_SIMPLIFY_VERSION} -eq $BS_FALSE ]; then
    DISTRO_MAJOR_VERSION=""
    DISTRO_MINOR_VERSION=""
    PREFIXED_DISTRO_MAJOR_VERSION=""
    PREFIXED_DISTRO_MINOR_VERSION=""
else
    DISTRO_MAJOR_VERSION=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
    DISTRO_MINOR_VERSION=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).\([0-9]*\).*/\2/g')
    PREFIXED_DISTRO_MAJOR_VERSION="_${DISTRO_MAJOR_VERSION}"
    if [ "${PREFIXED_DISTRO_MAJOR_VERSION}" = "_" ]; then
        PREFIXED_DISTRO_MAJOR_VERSION=""
    fi
    PREFIXED_DISTRO_MINOR_VERSION="_${DISTRO_MINOR_VERSION}"
    if [ "${PREFIXED_DISTRO_MINOR_VERSION}" = "_" ]; then
        PREFIXED_DISTRO_MINOR_VERSION=""
    fi
fi

# For ubuntu versions, obtain the codename from the release version
__ubuntu_codename_translation

# Only Ubuntu has daily packages, let's let users know about that
if ([ "${DISTRO_NAME_L}" != "ubuntu" ] && [ "$ITYPE" = "daily" ]); then
    echoerror "${DISTRO_NAME} does not have daily packages support"
    exit 1
elif ([ "$(echo "${DISTRO_NAME_L}" | egrep '(debian|ubuntu|centos|red_hat|oracle|scientific)')" = "" ] && [ "$ITYPE" = "stable" ] && [ "$STABLE_REV" != "latest" ]); then
    echoerror "${DISTRO_NAME} does not have major version pegged packages support"
    exit 1
fi

# Only RedHat based distros have testing support
if [ "${ITYPE}" = "testing" ]; then
    if [ "$(echo "${DISTRO_NAME_L}" | egrep '(centos|red_hat|amazon|oracle)')" = "" ]; then
        echoerror "${DISTRO_NAME} does not have testing packages support"
        exit 1
    fi
    _EPEL_REPO="epel-testing"
fi

# Only Ubuntu has support for installing to virtualenvs
if ([ "${DISTRO_NAME_L}" != "ubuntu" ] && [ "$_VIRTUALENV_DIR" != "null" ]); then
    echoerror "${DISTRO_NAME} does not have -V support"
    exit 1
fi

# Only Ubuntu has support for pip installing all packages
if ([ "${DISTRO_NAME_L}" != "ubuntu" ] && [ $_PIP_ALL -eq $BS_TRUE ]);then
    echoerror "${DISTRO_NAME} does not have -a support"
    exit 1
fi
#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __function_defined
#   DESCRIPTION:  Checks if a function is defined within this scripts scope
#    PARAMETERS:  function name
#       RETURNS:  0 or 1 as in defined or not defined
#----------------------------------------------------------------------------------------------------------------------
__function_defined() {
    FUNC_NAME=$1
    if [ "$(command -v "$FUNC_NAME")" != "" ]; then
        echoinfo "Found function $FUNC_NAME"
        return 0
    fi
    echodebug "$FUNC_NAME not found...."
    return 1
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __git_clone_and_checkout
#   DESCRIPTION:  (DRY) Helper function to clone and checkout salt to a
#                 specific revision.
#----------------------------------------------------------------------------------------------------------------------
__git_clone_and_checkout() {

    echodebug "Installed git version: $(git --version | awk '{ print $3 }')"

    __SALT_GIT_CHECKOUT_PARENT_DIR=$(dirname "${_SALT_GIT_CHECKOUT_DIR}" 2>/dev/null)
    __SALT_GIT_CHECKOUT_PARENT_DIR="${__SALT_GIT_CHECKOUT_PARENT_DIR:-/tmp/git}"
    __SALT_CHECKOUT_REPONAME="$(basename "${_SALT_GIT_CHECKOUT_DIR}" 2>/dev/null)"
    __SALT_CHECKOUT_REPONAME="${__SALT_CHECKOUT_REPONAME:-salt}"
    [ -d "${__SALT_GIT_CHECKOUT_PARENT_DIR}" ] || mkdir "${__SALT_GIT_CHECKOUT_PARENT_DIR}"
    # shellcheck disable=SC2164
    cd "${__SALT_GIT_CHECKOUT_PARENT_DIR}"
    if [ -d "${_SALT_GIT_CHECKOUT_DIR}" ]; then
        echodebug "Found a checked out Salt repository"
        # shellcheck disable=SC2164
        cd "${_SALT_GIT_CHECKOUT_DIR}"
        echodebug "Fetching git changes"
        git fetch || return 1
        # Tags are needed because of salt's versioning, also fetch that
        echodebug "Fetching git tags"
        git fetch --tags || return 1

        # If we have the SaltStack remote set as upstream, we also need to fetch the tags from there
        if [ "$(git remote -v | grep $_SALTSTACK_REPO_URL)" != "" ]; then
            echodebug "Fetching upstream(SaltStack's Salt repository) git tags"
            git fetch --tags upstream
        else
            echoinfo "Adding SaltStack's Salt repository as a remote"
            git remote add upstream "$_SALTSTACK_REPO_URL"
            echodebug "Fetching upstream(SaltStack's Salt repository) git tags"
            git fetch --tags upstream
        fi

        echodebug "Hard reseting the cloned repository to ${GIT_REV}"
        git reset --hard "$GIT_REV" || return 1

        # Just calling `git reset --hard $GIT_REV` on a branch name that has
        # already been checked out will not update that branch to the upstream
        # HEAD; instead it will simply reset to itself.  Check the ref to see
        # if it is a branch name, check out the branch, and pull in the
        # changes.
        git branch -a | grep -q "${GIT_REV}"
        if [ $? -eq 0 ]; then
            echodebug "Rebasing the cloned repository branch"
            git pull --rebase || return 1
        fi
    else
        if [ "$_FORCE_SHALLOW_CLONE" -eq "${BS_TRUE}" ]; then
            echoinfo "Forced shallow cloning of git repository."
            __SHALLOW_CLONE="${BS_TRUE}"
        elif [ "$(echo "$GIT_REV" | sed 's/^.*\(v\?[[:digit:]]\{1,4\}\.[[:digit:]]\{1,2\}\)\(\.[[:digit:]]\{1,2\}\)\?.*$/MATCH/')" = "MATCH" ]; then
            echoinfo "Git revision matches a Salt version tag, shallow cloning enabled."
            __SHALLOW_CLONE="${BS_TRUE}"
        else
            echowarn "The git revision being installed does not match a Salt version tag. Shallow cloning disabled"
            __SHALLOW_CLONE="${BS_FALSE}"
        fi

        if [ "$__SHALLOW_CLONE" -eq "${BS_TRUE}" ]; then
            # Let's try shallow cloning to speed up.
            # Test for "--single-branch" option introduced in git 1.7.10, the minimal version of git where the shallow
            # cloning we need actually works
            if [ "$(git clone 2>&1 | grep 'single-branch')" != "" ]; then
                # The "--single-branch" option is supported, attempt shallow cloning
                echoinfo "Attempting to shallow clone $GIT_REV from Salt's repository ${_SALT_REPO_URL}"
                git clone --depth 1 --branch "$GIT_REV" "$_SALT_REPO_URL" "$__SALT_CHECKOUT_REPONAME"
                if [ $? -eq 0 ]; then
                    # shellcheck disable=SC2164
                    cd "${_SALT_GIT_CHECKOUT_DIR}"
                    __SHALLOW_CLONE="${BS_TRUE}"
                else
                    # Shallow clone above failed(missing upstream tags???), let's resume the old behaviour.
                    echowarn "Failed to shallow clone."
                    echoinfo "Resuming regular git clone and remote SaltStack repository addition procedure"
                    __SHALLOW_CLONE="${BS_FALSE}"
                fi
            else
                echodebug "Shallow cloning not possible. Required git version not met."
                __SHALLOW_CLONE="${BS_FALSE}"
            fi
        fi

        if [ "$__SHALLOW_CLONE" -eq "${BS_FALSE}" ]; then
            git clone "$_SALT_REPO_URL" "$__SALT_CHECKOUT_REPONAME" || return 1
            # shellcheck disable=SC2164
            cd "${_SALT_GIT_CHECKOUT_DIR}"

            if [ "$(echo "$_SALT_REPO_URL" | grep -c -e '\(\(git\|https\)://github\.com/\|git@github\.com:\)saltstack/salt\.git')" -eq 0 ]; then
                # We need to add the saltstack repository as a remote and fetch tags for proper versioning
                echoinfo "Adding SaltStack's Salt repository as a remote"
                git remote add upstream "$_SALTSTACK_REPO_URL" || return 1
                echodebug "Fetching upstream(SaltStack's Salt repository) git tags"
                git fetch --tags upstream || return 1
                GIT_REV="origin/$GIT_REV"
            fi

            echodebug "Checking out $GIT_REV"
            git checkout "$GIT_REV" || return 1
        fi

    fi
    echoinfo "Cloning Salt's git repository succeeded"
    return 0
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __apt_get_install_noinput
#   DESCRIPTION:  (DRY) apt-get install with noinput options
#----------------------------------------------------------------------------------------------------------------------
__apt_get_install_noinput() {
    apt-get install -y -o DPkg::Options::=--force-confold "${@}"; return $?
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __apt_get_upgrade_noinput
#   DESCRIPTION:  (DRY) apt-get upgrade with noinput options
#----------------------------------------------------------------------------------------------------------------------
__apt_get_upgrade_noinput() {
    apt-get upgrade -y -o DPkg::Options::=--force-confold; return $?
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_end_of_life_versions
#   DESCRIPTION:  Check for end of life distribution versions
#----------------------------------------------------------------------------------------------------------------------
__check_end_of_life_versions() {
    case "${DISTRO_NAME_L}" in
        debian)
            # Debian versions bellow 6 are not supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 6 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://wiki.debian.org/DebianReleases"
                exit 1
            fi
            ;;

        ubuntu)
            # Ubuntu versions not supported
            #
            #  < 12.04
            if [ "$DISTRO_MAJOR_VERSION" -lt 12 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://wiki.ubuntu.com/Releases"
                exit 1
            fi
            ;;

        opensuse)
            # openSUSE versions not supported
            #
            #  <= 12.1
            if ([ "$DISTRO_MAJOR_VERSION" -eq 12 ] && [ "$DISTRO_MINOR_VERSION" -eq 1 ]) || [ "$DISTRO_MAJOR_VERSION" -lt 12 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    http://en.opensuse.org/Lifetime"
                exit 1
            fi
            ;;

        suse)
            # SuSE versions not supported
            #
            # < 11 SP2
            SUSE_PATCHLEVEL=$(awk '/PATCHLEVEL/ {print $3}' /etc/SuSE-release )
            if [ "${SUSE_PATCHLEVEL}" = "" ]; then
                SUSE_PATCHLEVEL="00"
            fi
            if ([ "$DISTRO_MAJOR_VERSION" -eq 11 ] && [ "$SUSE_PATCHLEVEL" -lt 02 ]) || [ "$DISTRO_MAJOR_VERSION" -lt 11 ]; then
                echoerror "Versions lower than SuSE 11 SP2 are not supported."
                echoerror "Please consider upgrading to the next stable"
                exit 1
            fi
            ;;

        fedora)
            # Fedora lower than 18 are no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 18 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://fedoraproject.org/wiki/Releases"
                exit 1
            fi
            ;;

        centos)
            # CentOS versions lower than 5 are no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 5 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    http://wiki.centos.org/Download"
                exit 1
            fi
            ;;

        red_hat*linux)
            # Red Hat (Enterprise) Linux versions lower than 5 are no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 5 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://access.redhat.com/support/policy/updates/errata/"
                exit 1
            fi
            ;;

        amazon*linux*ami)
            # Amazon Linux versions lower than 2012.0X no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 2012 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://aws.amazon.com/amazon-linux-ami/"
                exit 1
            fi
            ;;

        freebsd)
            # FreeBSD versions lower than 9.1 are not supported.
            if ([ "$DISTRO_MAJOR_VERSION" -eq 9 ] && [ "$DISTRO_MINOR_VERSION" -lt 01 ]) || [ "$DISTRO_MAJOR_VERSION" -lt 9 ]; then
                echoerror "Versions lower than FreeBSD 9.1 are not supported."
                exit 1
            fi
            ;;

        *)
            ;;
    esac
}
# Fail soon for end of life versions
__check_end_of_life_versions


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __copyfile
#   DESCRIPTION:  Simple function to copy files. Overrides if asked.
#----------------------------------------------------------------------------------------------------------------------
__copyfile() {
    overwrite=$_FORCE_OVERWRITE
    if [ $# -eq 2 ]; then
        sfile=$1
        dfile=$2
    elif [ $# -eq 3 ]; then
        sfile=$1
        dfile=$2
        overwrite=$3
    else
        echoerror "Wrong number of arguments for __copyfile()"
        echoinfo "USAGE: __copyfile <source> <dest>  OR  __copyfile <source> <dest> <overwrite>"
        exit 1
    fi

    # Does the source file exist?
    if [ ! -f "$sfile" ]; then
        echowarn "$sfile does not exist!"
        return 1
    fi

    # If the destination is a directory, let's make it a full path so the logic
    # below works as expected
    if [ -d "$dfile" ]; then
        echodebug "The passed destination($dfile) is a directory"
        dfile="${dfile}/$(basename "$sfile")"
        echodebug "Full destination path is now: $dfile"
    fi

    if [ ! -f "$dfile" ]; then
        # The destination file does not exist, copy
        echodebug "Copying $sfile to $dfile"
        cp "$sfile" "$dfile" || return 1
    elif [ -f "$dfile" ] && [ "$overwrite" -eq $BS_TRUE ]; then
        # The destination exist and we're overwriting
        echodebug "Overriding $dfile with $sfile"
        cp -f "$sfile" "$dfile" || return 1
    elif [ -f "$dfile" ] && [ "$overwrite" -ne $BS_TRUE ]; then
        echodebug "Not overriding $dfile with $sfile"
    fi
    return 0
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __movefile
#   DESCRIPTION:  Simple function to move files. Overrides if asked.
#----------------------------------------------------------------------------------------------------------------------
__movefile() {
    overwrite=$_FORCE_OVERWRITE
    if [ $# -eq 2 ]; then
        sfile=$1
        dfile=$2
    elif [ $# -eq 3 ]; then
        sfile=$1
        dfile=$2
        overwrite=$3
    else
        echoerror "Wrong number of arguments for __movefile()"
        echoinfo "USAGE: __movefile <source> <dest>  OR  __movefile <source> <dest> <overwrite>"
        exit 1
    fi

    if [ $_KEEP_TEMP_FILES -eq $BS_TRUE ]; then
        # We're being told not to move files, instead copy them so we can keep
        # them around
        echodebug "Since BS_KEEP_TEMP_FILES=1 we're copying files instead of moving them"
        __copyfile "$sfile" "$dfile" "$overwrite"
        return $?
    fi

    # Does the source file exist?
    if [ ! -f "$sfile" ]; then
        echowarn "$sfile does not exist!"
        return 1
    fi

    # If the destination is a directory, let's make it a full path so the logic
    # below works as expected
    if [ -d "$dfile" ]; then
        echodebug "The passed destination($dfile) is a directory"
        dfile="${dfile}/$(basename "$sfile")"
        echodebug "Full destination path is now: $dfile"
    fi

    if [ ! -f "$dfile" ]; then
        # The destination file does not exist, move
        echodebug "Moving $sfile to $dfile"
        mv "$sfile" "$dfile" || return 1
    elif [ -f "$dfile" ] && [ "$overwrite" -eq $BS_TRUE ]; then
        # The destination exist and we're overwriting
        echodebug "Overriding $dfile with $sfile"
        mv -f "$sfile" "$dfile" || return 1
    elif [ -f "$dfile" ] && [ "$overwrite" -ne $BS_TRUE ]; then
        echodebug "Not overriding $dfile with $sfile"
    fi

    return 0
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __linkfile
#   DESCRIPTION:  Simple function to create symlinks. Overrides if asked. Accepts globs.
#----------------------------------------------------------------------------------------------------------------------
__linkfile() {
    overwrite=$_FORCE_OVERWRITE
    if [ $# -eq 2 ]; then
        target=$1
        linkname=$2
    elif [ $# -eq 3 ]; then
        target=$1
        linkname=$2
        overwrite=$3
    else
        echoerror "Wrong number of arguments for __linkfile()"
        echoinfo "USAGE: __linkfile <target> <link>  OR  __linkfile <tagret> <link> <overwrite>"
        exit 1
    fi

    for sfile in $target; do
        # Does the source file exist?
        if [ ! -f "$sfile" ]; then
            echowarn "$sfile does not exist!"
            return 1
        fi

        # If the destination is a directory, let's make it a full path so the logic
        # below works as expected
        if [ -d "$linkname" ]; then
            echodebug "The passed link name ($linkname) is a directory"
            linkname="${linkname}/$(basename "$sfile")"
            echodebug "Full destination path is now: $linkname"
        fi

        if [ ! -e "$linkname" ]; then
            # The destination file does not exist, create link
            echodebug "Creating $linkname symlink pointing to $sfile"
            ln -s "$sfile" "$linkname" || return 1
        elif [ -e "$linkname" ] && [ "$overwrite" -eq $BS_TRUE ]; then
            # The destination exist and we're overwriting
            echodebug "Overwriting $linkname symlink to point on $sfile"
            ln -sf "$sfile" "$linkname" || return 1
        elif [ -e "$linkname" ] && [ "$overwrite" -ne $BS_TRUE ]; then
            echodebug "Not overwriting $linkname symlink to point on $sfile"
        fi
    done

    return 0
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __rpm_import_gpg
#   DESCRIPTION:  Download and import GPG public key to rpm database
#    PARAMETERS:  url
#----------------------------------------------------------------------------------------------------------------------
__rpm_import_gpg() {
    url="$1"

    if __check_command_exists mktemp; then
        tempfile="$(mktemp /tmp/salt-gpg-XXXXXXXX.pub 2>/dev/null)"

        if [ -z "$tempfile" ]; then
            echoerror "Failed to create temporary file in /tmp"
            return 1
        fi
    else
        tempfile="/tmp/salt-gpg-$$.pub"
    fi

    __fetch_url "$tempfile" "$url" || return 1
    rpm --import "$tempfile" || return 1
    rm -f "$tempfile"

    return 0
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_systemd
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_systemd() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    if [ "$(systemctl is-enabled "${servicename}")" = "enabled" ]; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_systemd  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_upstart
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_upstart() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    # Check if service is enabled to start at boot
    initctl list | grep "${servicename}" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_upstart  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_sysvinit
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_sysvinit() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    if [ "$(LC_ALL=C /sbin/chkconfig --list  | grep salt-"$fname" | grep '[2-5]:on')" != "" ]; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_sysvinit  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_debian
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_debian() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    # shellcheck disable=SC2086,SC2046,SC2144
    if [ -f /etc/rc$(runlevel | awk '{ print $2 }').d/S*${servicename} ]; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_debian  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_openbsd
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_openbsd() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    # shellcheck disable=SC2086,SC2046,SC2144
    if [ -f /etc/rc.d/${servicename} ] && [ $(grep ${servicename} /etc/rc.conf.local) -ne "" ] ; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        # return 1
    fi
}   # ----------  end of function __check_services_openbsd  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __create_virtualenv
#   DESCRIPTION:  Return 0 or 1 depending on successful creation of virtualenv
#----------------------------------------------------------------------------------------------------------------------
__create_virtualenv() {
    if [ ! -d "$_VIRTUALENV_DIR" ]; then
        echoinfo "Creating virtualenv ${_VIRTUALENV_DIR}"
        if [ $_PIP_ALL -eq $BS_TRUE ]; then
            virtualenv --no-site-packages "${_VIRTUALENV_DIR}" || return 1
        else
            virtualenv --system-site-packages "${_VIRTUALENV_DIR}" || return 1
        fi
    fi
    return 0
}   # ----------  end of function __create_virtualenv  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __activate_virtualenv
#   DESCRIPTION:  Return 0 or 1 depending on successful activation of virtualenv
#----------------------------------------------------------------------------------------------------------------------
__activate_virtualenv() {
    set +o nounset
    # Is virtualenv empty
    if [ -z "$VIRTUAL_ENV" ]; then
        __create_virtualenv || return 1
        # shellcheck source=/dev/null
        . "${_VIRTUALENV_DIR}/bin/activate" || return 1
        echoinfo "Activated virtualenv ${_VIRTUALENV_DIR}"
    fi
    set -o nounset
    return 0
}   # ----------  end of function __activate_virtualenv  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __install_pip_deps
#   DESCRIPTION:  Return 0 or 1 if successfully able to install pip packages via requirements file
#    PARAMETERS:  requirements_files
#----------------------------------------------------------------------------------------------------------------------
__install_pip_deps() {
    # Install virtualenv to system pip before activating virtualenv if thats going to be used
    # We assume pip pkg is installed since that is distro specific
    if [ "$_VIRTUALENV_DIR" != "null" ]; then
        if ! __check_command_exists pip; then
            echoerror "Pip not installed: required for -a installs"
            exit 1
        fi
        pip install -U virtualenv
        __activate_virtualenv || return 1
    else
        echoerror "Must have virtualenv dir specified for -a installs"
    fi

    requirements_file=$1
    if [ ! -f "${requirements_file}" ]; then
        echoerror "Requirements file: ${requirements_file} cannot be found, needed for -a (pip pkg) installs"
        exit 1
    fi

    __PIP_PACKAGES=''
    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        # shellcheck disable=SC2089
        __PIP_PACKAGES="${__PIP_PACKAGES} 'apache-libcloud>=$_LIBCLOUD_MIN_VERSION'"
    fi

    # shellcheck disable=SC2086,SC2090
    pip install -U -r ${requirements_file} ${__PIP_PACKAGES}
}


#######################################################################################################################
#
#   Distribution install functions
#
#   In order to install salt for a distribution you need to define:
#
#   To Install Dependencies, which is required, one of:
#       1. install_<distro>_<major_version>_<install_type>_deps
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>_deps
#       3. install_<distro>_<major_version>_deps
#       4  install_<distro>_<major_version>_<minor_version>_deps
#       5. install_<distro>_<install_type>_deps
#       6. install_<distro>_deps
#
#   Optionally, define a salt configuration function, which will be called if
#   the -c (config-dir) option is passed. One of:
#       1. config_<distro>_<major_version>_<install_type>_salt
#       2. config_<distro>_<major_version>_<minor_version>_<install_type>_salt
#       3. config_<distro>_<major_version>_salt
#       4  config_<distro>_<major_version>_<minor_version>_salt
#       5. config_<distro>_<install_type>_salt
#       6. config_<distro>_salt
#       7. config_salt [THIS ONE IS ALREADY DEFINED AS THE DEFAULT]
#
#   Optionally, define a salt master pre-seed function, which will be called if
#   the -k (pre-seed master keys) option is passed. One of:
#       1. preseed_<distro>_<major_version>_<install_type>_master
#       2. preseed_<distro>_<major_version>_<minor_version>_<install_type>_master
#       3. preseed_<distro>_<major_version>_master
#       4  preseed_<distro>_<major_version>_<minor_version>_master
#       5. preseed_<distro>_<install_type>_master
#       6. preseed_<distro>_master
#       7. preseed_master [THIS ONE IS ALREADY DEFINED AS THE DEFAULT]
#
#   To install salt, which, of course, is required, one of:
#       1. install_<distro>_<major_version>_<install_type>
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>
#       3. install_<distro>_<install_type>
#
#   Optionally, define a post install function, one of:
#       1. install_<distro>_<major_version>_<install_type>_post
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>_post
#       3. install_<distro>_<major_version>_post
#       4  install_<distro>_<major_version>_<minor_version>_post
#       5. install_<distro>_<install_type>_post
#       6. install_<distro>_post
#
#   Optionally, define a start daemons function, one of:
#       1. install_<distro>_<major_version>_<install_type>_restart_daemons
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>_restart_daemons
#       3. install_<distro>_<major_version>_restart_daemons
#       4  install_<distro>_<major_version>_<minor_version>_restart_daemons
#       5. install_<distro>_<install_type>_restart_daemons
#       6. install_<distro>_restart_daemons
#
#       NOTE: The start daemons function should be able to restart any daemons
#             which are running, or start if they're not running.
#
#   Optionally, define a daemons running function, one of:
#       1. daemons_running_<distro>_<major_version>_<install_type>
#       2. daemons_running_<distro>_<major_version>_<minor_version>_<install_type>
#       3. daemons_running_<distro>_<major_version>
#       4  daemons_running_<distro>_<major_version>_<minor_version>
#       5. daemons_running_<distro>_<install_type>
#       6. daemons_running_<distro>
#       7. daemons_running  [THIS ONE IS ALREADY DEFINED AS THE DEFAULT]
#
#   Optionally, check enabled Services:
#       1. install_<distro>_<major_version>_<install_type>_check_services
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>_check_services
#       3. install_<distro>_<major_version>_check_services
#       4  install_<distro>_<major_version>_<minor_version>_check_services
#       5. install_<distro>_<install_type>_check_services
#       6. install_<distro>_check_services
#
#######################################################################################################################


#######################################################################################################################
#
#   Ubuntu Install Functions
#
__enable_universe_repository() {
    if [ "$(grep -R universe /etc/apt/sources.list /etc/apt/sources.list.d/ | grep -v '#')" != "" ]; then
        # The universe repository is already enabled
        return 0
    fi

    echodebug "Enabling the universe repository"

    # Ubuntu versions higher than 12.04 do not live in the old repositories
    if [ "$DISTRO_MAJOR_VERSION" -gt 12 ] || ([ "$DISTRO_MAJOR_VERSION" -eq 12 ] && [ "$DISTRO_MINOR_VERSION" -gt 04 ]); then
        add-apt-repository -y "deb http://archive.ubuntu.com/ubuntu $(lsb_release -sc) universe" || return 1
    elif [ "$DISTRO_MAJOR_VERSION" -lt 11 ] && [ "$DISTRO_MINOR_VERSION" -lt 10 ]; then
        # Below Ubuntu 11.10, the -y flag to add-apt-repository is not supported
        add-apt-repository "deb http://old-releases.ubuntu.com/ubuntu $(lsb_release -sc) universe" || return 1
    else
        add-apt-repository -y "deb http://old-releases.ubuntu.com/ubuntu $(lsb_release -sc) universe" || return 1
    fi

    add-apt-repository -y "deb http://old-releases.ubuntu.com/ubuntu $(lsb_release -sc) universe" || return 1

    return 0
}

install_ubuntu_deps() {
    if ([ "${_SLEEP}" -eq "${__DEFAULT_SLEEP}" ] && [ "$DISTRO_MAJOR_VERSION" -lt 15 ]); then
        # The user did not pass a custom sleep value as an argument, let's increase the default value
        echodebug "On Ubuntu systems we increase the default sleep value to 10."
        echodebug "See https://github.com/saltstack/salt/issues/12248 for more info."
        _SLEEP=10
    fi
    if [ $_START_DAEMONS -eq $BS_FALSE ]; then
        echowarn "Not starting daemons on Debian based distributions is not working mostly because starting them is the default behaviour."
    fi
    # No user interaction, libc6 restart services for example
    export DEBIAN_FRONTEND=noninteractive

    apt-get update

    # Install Keys
    __apt_get_install_noinput debian-archive-keyring && apt-get update

    if [ "$DISTRO_MAJOR_VERSION" -gt 12 ] || ([ "$DISTRO_MAJOR_VERSION" -eq 12 ] && [ "$DISTRO_MINOR_VERSION" -eq 10 ]); then
        # Above Ubuntu 12.04 add-apt-repository is in a different package
        __apt_get_install_noinput software-properties-common || return 1
    else
        __apt_get_install_noinput python-software-properties || return 1
    fi


    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        __enable_universe_repository || return 1

        # Versions starting with 2015.5.6 and 2015.8.1 are hosted at repo.saltstack.com
        if [ "$(echo "$STABLE_REV" | egrep '^(2015\.5|2015\.8|latest|archive\/)')" = "" ]; then
            if [ "$DISTRO_MAJOR_VERSION" -lt 14 ]; then
                echoinfo "Installing Python Requests/Chardet from Chris Lea's PPA repository"
                if [ "$DISTRO_MAJOR_VERSION" -gt 11 ] || ([ "$DISTRO_MAJOR_VERSION" -eq 11 ] && [ "$DISTRO_MINOR_VERSION" -gt 04 ]); then
                    # Above Ubuntu 11.04 add a -y flag
                    add-apt-repository -y "ppa:chris-lea/python-requests" || return 1
                    add-apt-repository -y "ppa:chris-lea/python-chardet" || return 1
                    add-apt-repository -y "ppa:chris-lea/python-urllib3" || return 1
                    add-apt-repository -y "ppa:chris-lea/python-crypto" || return 1
                else
                    add-apt-repository "ppa:chris-lea/python-requests" || return 1
                    add-apt-repository "ppa:chris-lea/python-chardet" || return 1
                    add-apt-repository "ppa:chris-lea/python-urllib3" || return 1
                    add-apt-repository "ppa:chris-lea/python-crypto" || return 1
                fi
            fi

            if [ "$DISTRO_MAJOR_VERSION" -gt 12 ] || ([ "$DISTRO_MAJOR_VERSION" -eq 12 ] && [ "$DISTRO_MINOR_VERSION" -gt 03 ]); then
                if ([ "$DISTRO_MAJOR_VERSION" -lt 15 ] && [ "$_ENABLE_EXTERNAL_ZMQ_REPOS" -eq $BS_TRUE ]); then
                    echoinfo "Installing ZMQ>=4/PyZMQ>=14 from Chris Lea's PPA repository"
                    add-apt-repository -y ppa:chris-lea/zeromq || return 1
                fi
            fi
        fi
    fi

    __PIP_PACKAGES=""

    # Minimal systems might not have upstart installed, install it
    __PACKAGES="upstart"

    if [ "$DISTRO_MAJOR_VERSION" -ge 15 ]; then
        __PACKAGES="${__PACKAGES} python2.7"
    fi
    if [ "$_VIRTUALENV_DIR" != "null" ]; then
        __PACKAGES="${__PACKAGES} python-virtualenv"
    fi
    # Need python-apt for managing packages via Salt
    __PACKAGES="${__PACKAGES} python-apt"

    # requests is still used by many salt modules
    __PACKAGES="${__PACKAGES} python-requests"

    # Additionally install procps and pciutils which allows for Docker bootstraps. See 366#issuecomment-39666813
    __PACKAGES="${__PACKAGES} procps pciutils"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install 'apache-libcloud'"
        if ! __check_command_exists pip; then
            __PACKAGES="${__PACKAGES} python-setuptools python-pip"
        fi
        # shellcheck disable=SC2089
        __PIP_PACKAGES="${__PIP_PACKAGES} 'apache-libcloud>=$_LIBCLOUD_MIN_VERSION'"
    fi

    apt-get update
    # shellcheck disable=SC2086,SC2090
    __apt_get_install_noinput ${__PACKAGES} || return 1

    if [ "${__PIP_PACKAGES}" != "" ]; then
        # shellcheck disable=SC2086,SC2090
        if [ "$_VIRTUALENV_DIR" != "null" ]; then
            __activate_virtualenv
        fi
        pip install -U "${__PIP_PACKAGES}"
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_ubuntu_stable_deps() {

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        if [ "$CPU_ARCH_L" = "amd64" ] || [ "$CPU_ARCH_L" = "x86_64" ]; then
            repo_arch="amd64"
        elif [ "$CPU_ARCH_L" = "i386" ] || [ "$CPU_ARCH_L" = "i686" ]; then
            echoerror "repo.saltstack.com likely doesn't have 32-bit packages for Ubuntu (yet?)"
            repo_arch="i386"
        fi
    fi

    install_ubuntu_deps || return 1

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Versions starting with 2015.5.6 and 2015.8.1 are hosted at repo.saltstack.com
        if [ "$(echo "$STABLE_REV" | egrep '^(2015\.5|2015\.8|latest|archive\/)')" != "" ]; then
            # Workaround for latest non-LTS ubuntu
            if [ "$DISTRO_MAJOR_VERSION" -eq 15 ]; then
                echowarn "Non-LTS Ubuntu detected, but stable packages requested. Trying packages from latest LTS release. You may experience problems"
                UBUNTU_VERSION=14.04
                UBUNTU_CODENAME=trusty
            else
                UBUNTU_VERSION=$DISTRO_VERSION
                UBUNTU_CODENAME=$DISTRO_CODENAME
            fi

            # SaltStack's stable Ubuntu repository
            SALTSTACK_UBUNTU_URL="${HTTP_VAL}://repo.saltstack.com/apt/ubuntu/$UBUNTU_VERSION/$repo_arch/$STABLE_REV"
            if [ "$(grep -ER 'latest .+ main' /etc/apt)" = "" ]; then
                set +o nounset
                echo "deb $SALTSTACK_UBUNTU_URL $UBUNTU_CODENAME main" > "/etc/apt/sources.list.d/saltstack.list"
                set -o nounset
            fi

            # Make sure wget is available
            __apt_get_install_noinput wget

            # shellcheck disable=SC2086
            wget $_WGET_ARGS -q $SALTSTACK_UBUNTU_URL/SALTSTACK-GPG-KEY.pub -O - | apt-key add - || return 1

        else
            # Alternate PPAs: salt16, salt17, salt2014-1, salt2014-7
            if [ ! "$(echo "$STABLE_REV" | egrep '^(1\.6|1\.7)$')" = "" ]; then
              STABLE_PPA="saltstack/salt$(echo "$STABLE_REV" | tr -d .)"
            elif [ ! "$(echo "$STABLE_REV" | egrep '^(2014\.1|2014\.7)$')" = "" ]; then
              STABLE_PPA="saltstack/salt$(echo "$STABLE_REV" | tr . -)"
            else
              STABLE_PPA="saltstack/salt"
            fi

            if [ "$DISTRO_MAJOR_VERSION" -gt 11 ] || ([ "$DISTRO_MAJOR_VERSION" -eq 11 ] && [ "$DISTRO_MINOR_VERSION" -gt 04 ]); then
                # Above Ubuntu 11.04 add a -y flag
                add-apt-repository -y "ppa:$STABLE_PPA" || return 1
            else
                add-apt-repository "ppa:$STABLE_PPA" || return 1
            fi
        fi
    fi

    apt-get update
}

install_ubuntu_daily_deps() {
    install_ubuntu_deps || return 1

    if [ "$DISTRO_MAJOR_VERSION" -ge 12 ]; then
        # Above Ubuntu 11.10 add-apt-repository is in a different package
        __apt_get_install_noinput software-properties-common || return 1
    else
        __apt_get_install_noinput python-software-properties || return 1
    fi

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        __enable_universe_repository || return 1

        # for anything up to and including 11.04 do not use the -y option
        if [ "$DISTRO_MAJOR_VERSION" -gt 11 ] || ([ "$DISTRO_MAJOR_VERSION" -eq 11 ] && [ "$DISTRO_MINOR_VERSION" -gt 04 ]); then
            # Above Ubuntu 11.04 add a -y flag
            add-apt-repository -y ppa:saltstack/salt-daily || return 1
        else
            add-apt-repository ppa:saltstack/salt-daily || return 1
        fi

        apt-get update
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    return 0
}

install_ubuntu_git_deps() {
    if [ "$DISTRO_MAJOR_VERSION" -eq 12 ]; then
        apt-get update
    fi
    __apt_get_install_noinput git-core || return 1
    __git_clone_and_checkout || return 1

    __PACKAGES=""
    # See how we are installing packages
    if [ ${_PIP_ALL} -eq $BS_TRUE ]; then
        __PACKAGES="python-dev swig libssl-dev libzmq3 libzmq3-dev"
        if ! __check_command_exists pip; then
            __PACKAGES="${__PACKAGES} python-setuptools python-pip"
        fi
        # Get just the apt packages that are required to build all the pythons
        __apt_get_install_noinput "$__PACKAGES" || return 1
        # Install the pythons from requirements (only zmq for now)
        __install_pip_deps "${_SALT_GIT_CHECKOUT_DIR}/requirements/zeromq.txt" || return 1
    else
        install_ubuntu_deps || return 1
        __apt_get_install_noinput python-yaml python-m2crypto python-crypto \
            msgpack-python python-zmq python-jinja2 || return 1
        if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
            # We're on the develop branch, install whichever tornado is on the requirements file
            __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
            if [ "${__REQUIRED_TORNADO}" != "" ]; then
                __PACKAGES="${__PACKAGES} python-dev"
                check_pip_allowed "You need to allow pip based installations (-P) in order to install the python package '${__REQUIRED_TORNADO}'"
                if ! __check_command_exists pip; then
                    __PACKAGES="${__PACKAGES} python-setuptools python-pip"
                fi
                # shellcheck disable=SC2086
                __apt_get_install_noinput $__PACKAGES || return 1
                pip install -U "${__REQUIRED_TORNADO}"
            fi
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_ubuntu_stable() {
    __PACKAGES=""
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi
    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1
    return 0
}

install_ubuntu_daily() {
    install_ubuntu_stable || return 1
    return 0
}

install_ubuntu_git() {
    # Activate virtualenv before install
    if [ "${_VIRTUALENV_DIR}" != "null" ]; then
        __activate_virtualenv || return 1
    fi

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" install --install-layout=deb || return 1
    else
        python setup.py install --install-layout=deb || return 1
    fi
    return 0
}

install_ubuntu_stable_post() {
    # Workaround for latest LTS packages on latest ubuntu. Normally packages on
    # debian-based systems will automatically start the corresponding daemons
    if [ "$DISTRO_MAJOR_VERSION" -ne 15 ]; then
       return 0
    fi

    for fname in minion master syndic api; do
        # Skip if not meant to be installed
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            # Using systemd
            /bin/systemctl is-enabled salt-$fname.service > /dev/null 2>&1 || (
                /bin/systemctl preset salt-$fname.service > /dev/null 2>&1 &&
                /bin/systemctl enable salt-$fname.service > /dev/null 2>&1
            )
            sleep 0.1
            /usr/bin/systemctl daemon-reload
        elif [ -f /etc/init.d/salt-$fname ]; then
            update-rc.d salt-$fname defaults
        fi
    done
}
install_ubuntu_git_post() {
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ] && [ "$DISTRO_MAJOR_VERSION" -ge 15 ]; then
            __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            systemctl is-enabled salt-$fname.service || (systemctl preset salt-$fname.service && systemctl enable salt-$fname.service)
            sleep 0.1
            systemctl daemon-reload
        elif [ -f /sbin/initctl ]; then
            _upstart_conf="/etc/init/salt-$fname.conf"
            # We have upstart support
            echodebug "There's upstart support"
            if [ ! -f $_upstart_conf ]; then
                # upstart does not know about our service, let's copy the proper file
                echowarn "Upstart does not appear to know about salt-$fname"
                echodebug "Copying ${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-$fname.upstart to $_upstart_conf"
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.upstart" "$_upstart_conf"
                # Set service to know about virtualenv
                if [ "${_VIRTUALENV_DIR}" != "null" ]; then
                    echo "SALT_USE_VIRTUALENV=${_VIRTUALENV_DIR}" > /etc/default/salt-${fname}
                fi
                /sbin/initctl reload-configuration || return 1
            fi
        # No upstart support in Ubuntu!?
        elif [ -f "${_SALT_GIT_CHECKOUT_DIR}/debian/salt-${fname}.init" ]; then
            echodebug "There's NO upstart support!?"
            echodebug "Copying ${_SALT_GIT_CHECKOUT_DIR}/debian/salt-${fname}.init to /etc/init.d/salt-$fname"
            __copyfile "${_SALT_GIT_CHECKOUT_DIR}/debian/salt-${fname}.init" "/etc/init.d/salt-$fname"
            chmod +x /etc/init.d/salt-$fname

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            update-rc.d salt-$fname defaults
        else
            echoerror "Neither upstart nor init.d was setup for salt-$fname"
        fi
    done
}

install_ubuntu_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    # Ensure upstart configs / systemd units are loaded
    if [ -f /bin/systemctl ] && [ "$DISTRO_MAJOR_VERSION" -ge 15 ]; then
        systemctl daemon-reload
    elif [ -f /sbin/initctl ]; then
        /sbin/initctl reload-configuration
    fi
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ] && [ "$DISTRO_MAJOR_VERSION" -ge 15 ]; then
            echodebug "There's systemd support while checking salt-$fname"
            systemctl stop salt-$fname > /dev/null 2>&1
            systemctl start salt-$fname.service
            [ $? -eq 0 ] && continue
            # We failed to start the service, let's test the SysV code below
            echodebug "Failed to start salt-$fname using systemd"
        fi

        if [ -f /sbin/initctl ]; then
            echodebug "There's upstart support while checking salt-$fname"

            status salt-$fname 2>/dev/null | grep -q running
            if [ $? -eq 0 ]; then
                stop salt-$fname || (echodebug "Failed to stop salt-$fname" && return 1)
            fi

            start salt-$fname
            [ $? -eq 0 ] && continue
            # We failed to start the service, let's test the SysV code below
            echodebug "Failed to start salt-$fname using Upstart"
        fi

        if [ ! -f /etc/init.d/salt-$fname ]; then
            echoerror "No init.d support for salt-$fname was found"
            return 1
        fi

        /etc/init.d/salt-$fname stop > /dev/null 2>&1
        /etc/init.d/salt-$fname start
    done
    return 0
}

install_ubuntu_check_services() {
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ] && [ "$DISTRO_MAJOR_VERSION" -ge 15 ]; then
            __check_services_systemd salt-$fname || return 1
        elif [ -f /sbin/initctl ] && [ -f /etc/init/salt-${fname}.conf ]; then
            __check_services_upstart salt-$fname || return 1
        elif [ -f /etc/init.d/salt-$fname ]; then
            __check_services_debian salt-$fname || return 1
        fi
    done
    return 0
}
#
#   End of Ubuntu Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Debian Install Functions
#
install_debian_deps() {
    if [ $_START_DAEMONS -eq $BS_FALSE ]; then
        echowarn "Not starting daemons on Debian based distributions is not working mostly because starting them is the default behaviour."
    fi
    # No user interaction, libc6 restart services for example
    export DEBIAN_FRONTEND=noninteractive

    apt-get update

    # Install Keys
    __apt_get_install_noinput debian-archive-keyring && apt-get update

    # Install procps and pciutils which allows for Docker bootstraps. See #366#issuecomment-39666813
    __PACKAGES="procps pciutils"
    __PIP_PACKAGES=""

    if [ "$DISTRO_MAJOR_VERSION" -lt 6 ]; then
        # Both python-requests which is a hard dependency and apache-libcloud which is a soft dependency, under debian < 6
        # need to be installed using pip
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install the python 'requests' package"
        __PACKAGES="${__PACKAGES} python-pip"
        # shellcheck disable=SC2089
        __PIP_PACKAGES="${__PIP_PACKAGES} 'requests>=$_PY_REQUESTS_MIN_VERSION'"
    fi

    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        # shellcheck disable=SC2089
        __PIP_PACKAGES="${__PIP_PACKAGES} 'apache-libcloud>=$_LIBCLOUD_MIN_VERSION'"
    fi

    if [ "${__PIP_PACKAGES}" != "" ]; then
        # shellcheck disable=SC2086,SC2090
        pip install -U ${__PIP_PACKAGES} || return 1
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_debian_6_deps() {
    if [ $_START_DAEMONS -eq $BS_FALSE ]; then
        echowarn "Not starting daemons on Debian based distributions is not working mostly because starting them is the default behaviour."
    fi
    # No user interaction, libc6 restart services for example
    export DEBIAN_FRONTEND=noninteractive

    apt-get update

    # Make sure wget is available
    __apt_get_install_noinput wget

    # Install Keys
    __apt_get_install_noinput debian-archive-keyring && apt-get update

    # Install Debian Archive Automatic Signing Key (6.0/squeeze), see #557
    if [ "$(apt-key finger | grep '9FED 2BCB DCD2 9CDF 7626  78CB AED4 B06F 4730 41FA')" = "" ]; then
        apt-key adv --keyserver keyserver.ubuntu.com --recv-keys AED4B06F473041FA || return 1
    fi

    # shellcheck disable=SC2086
    __fetch_verify http://debian.saltstack.com/debian-salt-team-joehealy.gpg.key 267d1f152d0cc94b23eb4c6993ba3d67 3100 | apt-key add - || return 1

    if [ "$_PIP_ALLOWED" -eq $BS_TRUE ]; then
        echowarn "PyZMQ will be installed from PyPI in order to compile it against ZMQ3"
        echowarn "This is required for long term stable minion connections to the master."
        echowarn "YOU WILL END UP WITH QUITE A FEW PACKAGES FROM DEBIAN UNSTABLE"
        echowarn "Sleeping for 5 seconds so you can cancel..."
        sleep 5

        if [ ! -f /etc/apt/sources.list.d/debian-unstable.list ]; then
           cat <<_eof > /etc/apt/sources.list.d/debian-unstable.list
deb http://ftp.debian.org/debian unstable main
deb-src http://ftp.debian.org/debian unstable main
_eof

           cat <<_eof > /etc/apt/preferences.d/libzmq3-debian-unstable.pref
Package: libzmq3
Pin: release a=unstable
Pin-Priority: 800

Package: libzmq3-dev
Pin: release a=unstable
Pin-Priority: 800
_eof
        fi

        apt-get update
        # We NEED to install the unstable dpkg or mime-support WILL fail to install
        __apt_get_install_noinput -t unstable dpkg liblzma5 python mime-support || return 1
        __apt_get_install_noinput -t unstable libzmq3 libzmq3-dev || return 1
        __apt_get_install_noinput build-essential python-dev python-pip python-setuptools || return 1

        if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
            # Saltstack's Unstable Debian repository
            if [ "$(grep -R 'debian.saltstack.com' /etc/apt)" = "" ]; then
                echo "deb http://debian.saltstack.com/debian unstable main" >> \
                    /etc/apt/sources.list.d/saltstack.list
            fi
        fi
        return 0
    fi

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Debian Backports
        if [ "$(grep -R 'squeeze-backports' /etc/apt | grep -v "^#")" = "" ]; then
            echo "deb http://ftp.de.debian.org/debian-backports squeeze-backports main" >> \
                /etc/apt/sources.list.d/backports.list
        fi

        # Saltstack's Stable Debian repository
        if [ "$(grep -R 'squeeze-saltstack' /etc/apt)" = "" ]; then
            echo "deb http://debian.saltstack.com/debian squeeze-saltstack main" >> \
                /etc/apt/sources.list.d/saltstack.list
        fi
        apt-get update || return 1
    fi

    # Python requests is available through Squeeze backports
    # Additionally install procps and pciutils which allows for Docker bootstraps. See 366#issuecomment-39666813
    __apt_get_install_noinput python-pip procps pciutils python-requests

    # Need python-apt for managing packages via Salt
    __apt_get_install_noinput python-apt

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud/requests"
        pip install -U "apache-libcloud>=$_LIBCLOUD_MIN_VERSION"

    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    __apt_get_install_noinput python-zmq || return 1

    if [ "$_PIP_ALLOWED" -eq $BS_TRUE ]; then
        # Building pyzmq from source to build it against libzmq3.
        # Should override current installation
        # Using easy_install instead of pip because at least on Debian 6,
        # there's no default virtualenv active.
        easy_install -U pyzmq || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_debian_7_deps() {
    if [ $_START_DAEMONS -eq $BS_FALSE ]; then
        echowarn "Not starting daemons on Debian based distributions is not working mostly because starting them is the default behaviour."
    fi
    # No user interaction, libc6 restart services for example
    export DEBIAN_FRONTEND=noninteractive

    apt-get update

    # Make sure wget is available
    __apt_get_install_noinput wget

    # Install Keys
    __apt_get_install_noinput debian-archive-keyring && apt-get update

    # Install Debian Archive Automatic Signing Key (7.0/wheezy), see #557
    if [ "$(apt-key finger | grep 'A1BD 8E9D 78F7 FE5C 3E65  D8AF 8B48 AD62 4692 5553')" = "" ]; then
        apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 8B48AD6246925553 || return 1
    fi

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Debian Backports
        if [ "$(grep -R 'wheezy-backports' /etc/apt | grep -v "^#")" = "" ]; then
            echo "deb http://httpredir.debian.org/debian wheezy-backports main" >> \
                /etc/apt/sources.list.d/backports.list
        fi

        # Saltstack's Stable Debian repository
        if [ "$(grep -R 'wheezy-saltstack' /etc/apt)" = "" ]; then
            echo "deb http://debian.saltstack.com/debian wheezy-saltstack main" >> \
                /etc/apt/sources.list.d/saltstack.list
        fi
    fi

    # shellcheck disable=SC2086
    __fetch_verify http://debian.saltstack.com/debian-salt-team-joehealy.gpg.key 267d1f152d0cc94b23eb4c6993ba3d67 3100 | apt-key add - || return 1

    apt-get update || return 1
    __apt_get_install_noinput -t wheezy-backports libzmq3 libzmq3-dev python-zmq python-apt || return 1
    # Install procps and pciutils which allows for Docker bootstraps. See 366#issuecomment-39666813
    __PACKAGES="procps pciutils"
    # Also install python-requests
    __PACKAGES="${__PACKAGES} python-requests"
    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1


    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="build-essential python-dev python-pip"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${__PACKAGES} || return 1
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
        pip install -U "apache-libcloud>=$_LIBCLOUD_MIN_VERSION" || return 1
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_debian_8_deps() {
    echodebug "install_debian_8_deps"

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        if [ "$CPU_ARCH_L" = "amd64" ] || [ "$CPU_ARCH_L" = "x86_64" ]; then
            repo_arch="amd64"
        elif [ "$CPU_ARCH_L" = "i386" ] || [ "$CPU_ARCH_L" = "i686" ]; then
            echoerror "repo.saltstack.com likely doesn't have 32-bit packages for Debian (yet?)"
            repo_arch="i386"
        fi
    fi

    if [ $_START_DAEMONS -eq $BS_FALSE ]; then
        echowarn "Not starting daemons on Debian based distributions is not working mostly because starting them is the default behaviour."
    fi
    # No user interaction, libc6 restart services for example
    export DEBIAN_FRONTEND=noninteractive

    apt-get update

    # Make sure wget is available
    __apt_get_install_noinput wget

    # Install Keys
    __apt_get_install_noinput debian-archive-keyring && apt-get update

    # Install Debian Archive Automatic Signing Key (8/jessie), see #557
    if [ "$(apt-key finger | grep '126C 0D24 BD8A 2942 CC7D  F8AC 7638 D044 2B90 D010')" = "" ]; then
        apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 7638D0442B90D010 || return 1
    fi

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Versions starting with 2015.5.6 and 2015.8.1 are hosted at repo.saltstack.com
        if [ "$(echo "$STABLE_REV" | egrep '^(2015\.5|2015\.8|latest|archive\/)')" != "" ]; then
            SALTSTACK_DEBIAN_URL="${HTTP_VAL}://repo.saltstack.com/apt/debian/$DISTRO_MAJOR_VERSION/$repo_arch/$STABLE_REV"
            echo "deb $SALTSTACK_DEBIAN_URL jessie main" > "/etc/apt/sources.list.d/saltstack.list"

            # shellcheck disable=SC2086
            wget $_WGET_ARGS -q "$SALTSTACK_DEBIAN_URL/SALTSTACK-GPG-KEY.pub" -O - | apt-key add - || return 1

            if [ "${HTTP_VAL}" = "https" ] ; then
                __apt_get_install_noinput apt-transport-https || return 1
            fi
        fi
    fi

    apt-get update || return 1
    __PACKAGES="libzmq3 libzmq3-dev python-zmq python-requests python-apt"

    # Additionally install procps and pciutils which allows for Docker bootstraps. See 366#issuecomment-39666813
    __PACKAGES="${__PACKAGES} procps pciutils"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        # Install python-libcloud if asked to
        __PACKAGES="${__PACKAGES} python-libcloud"
    fi

    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_debian_git_deps() {
    if [ $_START_DAEMONS -eq $BS_FALSE ]; then
        echowarn "Not starting daemons on Debian based distributions is not working mostly because starting them is the default behaviour."
    fi
    # No user interaction, libc6 restart services for example
    export DEBIAN_FRONTEND=noninteractive

    apt-get update

    # Install Keys
    __apt_get_install_noinput debian-archive-keyring && apt-get update

    if ! __check_command_exists git; then
        __apt_get_install_noinput git || return 1
    fi

    __apt_get_install_noinput lsb-release python python-pkg-resources python-crypto \
        python-jinja2 python-m2crypto python-yaml msgpack-python python-pip || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __check_pip_allowed "You need to allow pip based installations (-P) in order to install the python package '${__REQUIRED_TORNADO}'"
            __apt_get_install_noinput python-dev
            pip install -U "${__REQUIRED_TORNADO}" || return 1
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
        pip install -U "apache-libcloud>=$_LIBCLOUD_MIN_VERSION"
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_debian_6_git_deps() {
    install_debian_6_deps || return 1
    if [ "$_PIP_ALLOWED" -eq $BS_TRUE ]; then
        __PACKAGES="build-essential lsb-release python python-dev python-pkg-resources python-crypto"
        __PACKAGES="${__PACKAGES} python-m2crypto python-yaml msgpack-python python-pip python-setuptools"

        if ! __check_command_exists git; then
            __PACKAGES="${__PACKAGES} git"
        fi

        # shellcheck disable=SC2086
        __apt_get_install_noinput ${__PACKAGES} || return 1

        easy_install -U pyzmq Jinja2 || return 1

        __git_clone_and_checkout || return 1

        # Let's trigger config_salt()
        if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
            _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
            CONFIG_SALT_FUNC="config_salt"
        fi
    else
        install_debian_git_deps || return 1  # Grab the actual deps
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    return 0
}

install_debian_7_git_deps() {
    install_debian_7_deps || return 1
    install_debian_git_deps || return 1  # Grab the actual deps
    return 0
}

install_debian_8_git_deps() {
    install_debian_8_deps || return 1
    # No user interaction, libc6 restart services for example
    export DEBIAN_FRONTEND=noninteractive

    if ! __check_command_exists git; then
        __apt_get_install_noinput git || return 1
    fi

    if [ "$(dpkg-query -l 'python-zmq')" = "" ]; then
        __apt_get_install_noinput libzmq3 libzmq3-dev python-zmq || return 1
    fi

    __apt_get_install_noinput lsb-release python python-pkg-resources python-crypto \
        python-jinja2 python-m2crypto python-yaml msgpack-python python-pip || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install tornado
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __apt_get_install_noinput python-tornado
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_debian_stable() {
    __PACKAGES=""
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi
    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1

    return 0
}

install_debian_6_stable() {
    install_debian_stable || return 1
    return 0
}

install_debian_7_stable() {
    install_debian_stable || return 1
    return 0
}

install_debian_8_stable() {
    install_debian_stable || return 1
    return 0
}

install_debian_git() {
    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
      python setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" install --install-layout=deb || return 1
    else
        python setup.py install --install-layout=deb || return 1
    fi
}

install_debian_6_git() {
    install_debian_git || return 1
    return 0
}

install_debian_7_git() {
    install_debian_git || return 1
    return 0
}

install_debian_8_git() {
    install_debian_git || return 1
    return 0
}

install_debian_git_post() {
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            if [ ! -f /etc/systemd/system/salt-${fname}.service ] || ([ -f /etc/systemd/system/salt-${fname}.service ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" /etc/systemd/system
            fi

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            /bin/systemctl enable salt-${fname}.service
            SYSTEMD_RELOAD=$BS_TRUE

        elif [ ! -f /etc/init.d/salt-$fname ] || ([ -f /etc/init.d/salt-$fname ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
            if [ -f "${_SALT_GIT_CHECKOUT_DIR}/debian/salt-$fname.init" ]; then
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/debian/salt-$fname.init" "/etc/init.d/salt-$fname"
            else
                __fetch_url "/etc/init.d/salt-$fname" "${HTTP_VAL}://anonscm.debian.org/cgit/pkg-salt/salt.git/plain/debian/salt-${fname}.init"
            fi
            if [ ! -f "/etc/init.d/salt-$fname" ]; then
                echowarn "The init script for salt-$fname was not found, skipping it..."
                continue
            fi
            chmod +x "/etc/init.d/salt-$fname"

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            update-rc.d "salt-$fname" defaults
        fi

    done
}

install_debian_restart_daemons() {
    [ "$_START_DAEMONS" -eq $BS_FALSE ] && return

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ ! -f "/etc/init.d/salt-$fname" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        if [ -f /bin/systemctl ]; then
            # Debian 8 uses systemd
            /bin/systemctl stop salt-$fname > /dev/null 2>&1
            /bin/systemctl start salt-$fname.service
        elif [ -f /etc/init.d/salt-$fname ]; then
            # Still in SysV init
            /etc/init.d/salt-$fname stop > /dev/null 2>&1
            /etc/init.d/salt-$fname start
        fi
    done
}

install_debian_check_services() {
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ ! -f "/etc/init.d/salt-$fname" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        if [ -f /bin/systemctl ]; then
            __check_services_systemd salt-$fname || return 1
        elif [ -f /etc/init.d/salt-$fname ]; then
            __check_services_debian salt-$fname || return 1
        fi
    done
    return 0
}
#
#   Ended Debian Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Fedora Install Functions
#

FEDORA_PACKAGE_MANAGER="yum"

__fedora_get_package_manager() {
  if [ "$DISTRO_MAJOR_VERSION" -ge 22 ] || __check_command_exists dnf; then
    FEDORA_PACKAGE_MANAGER="dnf"
  fi
}

install_fedora_deps() {
    __fedora_get_package_manager

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        if [ "$_ENABLE_EXTERNAL_ZMQ_REPOS" -eq $BS_TRUE ]; then
            __install_saltstack_copr_zeromq_repository || return 1
        fi

        __install_saltstack_copr_salt_repository || return 1
    fi

    __PACKAGES="yum-utils PyYAML libyaml m2crypto python-crypto python-jinja2 python-msgpack python-zmq python-requests"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-libcloud"
    fi

    # shellcheck disable=SC2086
    $FEDORA_PACKAGE_MANAGER install -y ${__PACKAGES} || return 1

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        $FEDORA_PACKAGE_MANAGER -y update || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        $FEDORA_PACKAGE_MANAGER install -y ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_fedora_stable() {
    __fedora_get_package_manager
    __PACKAGES=""
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ] || [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    # shellcheck disable=SC2086
    $FEDORA_PACKAGE_MANAGER install -y ${__PACKAGES} || return 1
    return 0
}

install_fedora_stable_post() {
    for fname in minion master syndic api; do
        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        systemctl is-enabled salt-$fname.service || (systemctl preset salt-$fname.service && systemctl enable salt-$fname.service)
        sleep 0.1
        systemctl daemon-reload
    done
}

install_fedora_git_deps() {
    __fedora_get_package_manager
    install_fedora_deps || return 1

    if ! __check_command_exists git; then
        $FEDORA_PACKAGE_MANAGER install -y git || return 1
    fi

    $FEDORA_PACKAGE_MANAGER install -y systemd-python || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __check_pip_allowed "You need to allow pip based installations (-P) in order to install tornado"

            # Install pip and pip dependencies
            if ! __check_command_exists pip; then
                $FEDORA_PACKAGE_MANAGER install -y python-setuptools python-pip gcc python-devel
            fi

            pip install -U tornado

        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_fedora_git() {
    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" install || return 1
    else
        python setup.py install || return 1
    fi
    return 0
}

install_fedora_git_post() {
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"

        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        systemctl is-enabled salt-$fname.service || (systemctl preset salt-$fname.service && systemctl enable salt-$fname.service)
        sleep 0.1
        systemctl daemon-reload
    done
}

install_fedora_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        systemctl stop salt-$fname > /dev/null 2>&1
        systemctl start salt-$fname.service
    done
}

install_fedora_check_services() {
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        __check_services_systemd salt-$fname || return 1
    done
    return 0
}
#
#   Ended Fedora Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   CentOS Install Functions
#
__install_epel_repository() {
    if [ ${_EPEL_REPOS_INSTALLED} -eq $BS_TRUE ]; then
        return 0
    fi

    # Check if epel repo is already enabled and flag it accordingly
    yum repolist | grep -q "^[!]${_EPEL_REPO}/"
    if [ $? -eq 0 ]; then
        _EPEL_REPOS_INSTALLED=$BS_TRUE
        return 0
    fi

    # Check if epel-release is already installed and flag it accordingly
    rpm --nodigest --nosignature -q epel-release > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        _EPEL_REPOS_INSTALLED=$BS_TRUE
        return 0
    fi

    # Download latest 'epel-release' package for the distro version directly
    epel_repo_url="${HTTP_VAL}://dl.fedoraproject.org/pub/epel/epel-release-latest-${DISTRO_MAJOR_VERSION}.noarch.rpm"
    if [ "$DISTRO_MAJOR_VERSION" -eq 5 ]; then
        __fetch_url /tmp/epel-release.rpm "$epel_repo_url" || return 1
        rpm -Uvh --force /tmp/epel-release.rpm || return 1
        rm -f /tmp/epel-release.rpm
    elif [ "$DISTRO_MAJOR_VERSION" -ge 6 ]; then
        rpm -Uvh --force "$epel_repo_url" || return 1
    else
        echoerror "Failed add EPEL repository support."
        return 1
    fi

    _EPEL_REPOS_INSTALLED=$BS_TRUE
    return 0
}

__install_saltstack_copr_zeromq_repository() {
    echoinfo "Installing Zeromq >=4 and PyZMQ>=14 from SaltStack's COPR repository"
    if [ ! -s /etc/yum.repos.d/saltstack-zeromq4.repo ]; then
        if [ "${DISTRO_NAME_L}" = "fedora" ]; then
            __REPOTYPE="${DISTRO_NAME_L}"
        else
            __REPOTYPE="epel"
        fi
        __fetch_url /etc/yum.repos.d/saltstack-zeromq4.repo \
            "${HTTP_VAL}://copr.fedorainfracloud.org/coprs/saltstack/zeromq4/repo/${__REPOTYPE}-${DISTRO_MAJOR_VERSION}/saltstack-zeromq4-${__REPOTYPE}-${DISTRO_MAJOR_VERSION}.repo" || return 1
    fi
    return 0
}

__install_saltstack_rhel_repository() {
    if [ "$ITYPE" = "stable" ]; then
        repo_rev="$STABLE_REV"
    else
        repo_rev="latest"
    fi

    base_url="${HTTP_VAL}://repo.saltstack.com/yum/redhat/\$releasever/\$basearch/${repo_rev}/"
    fetch_url="${HTTP_VAL}://repo.saltstack.com/yum/redhat/${DISTRO_MAJOR_VERSION}/${CPU_ARCH_L}/${repo_rev}/"

    if [ "${DISTRO_MAJOR_VERSION}" -eq 5 ]; then
        gpg_key="SALTSTACK-EL5-GPG-KEY.pub"
    else
        gpg_key="SALTSTACK-GPG-KEY.pub"
    fi

    repo_file="/etc/yum.repos.d/saltstack.repo"
    if [ ! -s "$repo_file" ]; then
        cat <<_eof > "$repo_file"
[saltstack]
name=SaltStack ${repo_rev} Release Channel for RHEL/CentOS \$releasever
baseurl=$base_url
skip_if_unavailable=True
gpgcheck=1
gpgkey=${base_url}${gpg_key}
enabled=1
enabled_metadata=1
_eof

        __rpm_import_gpg "${fetch_url}${gpg_key}" || return 1
    fi

    if [ "$DISTRO_MAJOR_VERSION" -eq 7 ] && ([ "$repo_rev" = "latest" ] || [ "$repo_rev" = "2015.8" ]); then
        # Import CentOS 7 GPG key on RHEL for installing base dependencies from
        # Salt corporate repository
        rpm -qa gpg-pubkey\* --qf "%{name}-%{version}\n" | grep -q ^gpg-pubkey-f4a80eb5$ || \
            __rpm_import_gpg "${HTTP_VAL}://repo.saltstack.com/yum/redhat/7/x86_64/${repo_rev}/base/RPM-GPG-KEY-CentOS-7" || return 1
    fi

    return 0
}

__install_saltstack_copr_salt_repository() {
    echoinfo "Adding SaltStack's COPR repository"

    if [ "${DISTRO_NAME_L}" = "fedora" ]; then
        [ "$DISTRO_MAJOR_VERSION" -ge 22 ] && return 0
        __REPOTYPE="${DISTRO_NAME_L}"
    else
        __REPOTYPE="epel"
    fi

    __REPO_FILENAME="saltstack-salt-${__REPOTYPE}-${DISTRO_MAJOR_VERSION}.repo"

    if [ ! -s "/etc/yum.repos.d/${__REPO_FILENAME}" ]; then
        __fetch_url "/etc/yum.repos.d/${__REPO_FILENAME}" \
            "${HTTP_VAL}://copr.fedorainfracloud.org/coprs/saltstack/salt/repo/${__REPOTYPE}-${DISTRO_MAJOR_VERSION}/${__REPO_FILENAME}" || return 1
    fi
    return 0
}

install_centos_stable_deps() {
    if [ "$DISTRO_MAJOR_VERSION" -eq 5 ]; then
        # Install curl which is not included in @core CentOS 5 installation
        __check_command_exists curl || yum -y install "curl.${CPU_ARCH_L}" || return 1
    fi

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        __install_epel_repository || return 1
        __install_saltstack_rhel_repository || return 1
    fi

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            if [ "$DISTRO_MAJOR_VERSION" -eq 5 ]; then
                yum install -y python26-tornado
            else
                yum install -y python-tornado
            fi
        fi
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        yum -y update || return 1
    fi

    __PACKAGES="yum-utils chkconfig"

    if [ "$DISTRO_MAJOR_VERSION" -eq 5 ]; then
        __PACKAGES="${__PACKAGES} python26-PyYAML python26-m2crypto m2crypto python26 python26-requests"
        __PACKAGES="${__PACKAGES} python26-crypto python26-msgpack python26-zmq python26-jinja2"
        if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
            __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
            __PACKAGES="${__PACKAGES} python26-setuptools"
        fi
    else
        __PACKAGES="${__PACKAGES} PyYAML m2crypto python-crypto python-msgpack python-zmq python-jinja2 python-requests"
        if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
            __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
            __PACKAGES="${__PACKAGES} python-pip"
        fi
    fi

    if [ "$DISTRO_NAME_L" = "oracle_linux" ]; then
        # We need to install one package at a time because --enablerepo=X disables ALL OTHER REPOS!!!!
        for package in ${__PACKAGES}; do
            # shellcheck disable=SC2086
            yum -y install ${package} || yum -y install ${package} --enablerepo=${_EPEL_REPO} || return 1
        done
    else
        # shellcheck disable=SC2086
        yum -y install ${__PACKAGES} --enablerepo=${_EPEL_REPO} || return 1
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
        if [ "$DISTRO_MAJOR_VERSION" -eq 5 ]; then
            easy_install-2.6 "apache-libcloud>=$_LIBCLOUD_MIN_VERSION"
        else
            pip install "apache-libcloud>=$_LIBCLOUD_MIN_VERSION"
        fi
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        if [ "$DISTRO_NAME_L" = "oracle_linux" ]; then
            # We need to install one package at a time because --enablerepo=X disables ALL OTHER REPOS!!!!
            for package in ${_EXTRA_PACKAGES}; do
                # shellcheck disable=SC2086
                yum -y install ${package} || yum -y install ${package} --enablerepo=${_EPEL_REPO} || return 1
            done
        else
            # shellcheck disable=SC2086
            yum install -y ${_EXTRA_PACKAGES} --enablerepo=${_EPEL_REPO} || return 1
        fi
    fi

    return 0
}

install_centos_stable() {
    __PACKAGES=""
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi

    if [ "$DISTRO_NAME_L" = "oracle_linux" ]; then
        # We need to install one package at a time because --enablerepo=X disables ALL OTHER REPOS!!!!
        for package in ${__PACKAGES}; do
            # shellcheck disable=SC2086
            yum -y install ${package} || yum -y install ${package} --enablerepo=${_EPEL_REPO} || return 1
        done
    else
        # shellcheck disable=SC2086
        yum -y install ${__PACKAGES} --enablerepo=${_EPEL_REPO} || return 1
    fi
    return 0
}

install_centos_stable_post() {
    for fname in minion master syndic api; do
        # Skip if not meant to be installed
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /etc/init.d/salt-$fname ]; then
            # Still in SysV init!?
            /sbin/chkconfig salt-$fname on
        elif [ -f /usr/bin/systemctl ]; then
            # Using systemd
            /usr/bin/systemctl is-enabled salt-$fname.service > /dev/null 2>&1 || (
                /usr/bin/systemctl preset salt-$fname.service > /dev/null 2>&1 &&
                /usr/bin/systemctl enable salt-$fname.service > /dev/null 2>&1
            )
            sleep 0.1
            /usr/bin/systemctl daemon-reload
        fi
    done
}

install_centos_git_deps() {
    install_centos_stable_deps || return 1
    if ! __check_command_exists git; then
        # git not installed - need to install it
        if [ "$DISTRO_NAME_L" = "oracle_linux" ]; then
            # try both ways --enablerepo=X disables ALL OTHER REPOS!!!!
            yum install -y git || yum install -y git --enablerepo=${_EPEL_REPO} || return 1
        else
            yum install -y git --enablerepo=${_EPEL_REPO} || return 1
        fi
    fi

    if [ "$DISTRO_MAJOR_VERSION" -gt 6 ]; then
        if [ "$DISTRO_NAME_L" != "oracle_linux" ]; then
            yum install -y systemd-python || yum install -y systemd-python --enablerepo=${_EPEL_REPO} || return 1
        else
            yum install -y systemd-python --enablerepo=${_EPEL_REPO} || return 1
        fi
    fi

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            if [ "$DISTRO_MAJOR_VERSION" -eq 5 ]; then
                yum install -y python26-tornado
            else
                yum install -y python-tornado
            fi
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_centos_git() {
    if [ "$DISTRO_MAJOR_VERSION" -eq 5 ]; then
        _PYEXE=python2.6
    else
        _PYEXE=python2
    fi
    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        $_PYEXE setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" install --prefix=/usr || return 1
    else
        $_PYEXE setup.py install --prefix=/usr || return 1
    fi
    return 0
}

install_centos_git_post() {
    SYSTEMD_RELOAD=$BS_FALSE
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            if [ ! -f /usr/lib/systemd/system/salt-${fname}.service ] || ([ -f /usr/lib/systemd/system/salt-${fname}.service ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" /usr/lib/systemd/system/
            fi

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            /bin/systemctl enable salt-${fname}.service
            SYSTEMD_RELOAD=$BS_TRUE

        elif [ ! -f /etc/init.d/salt-$fname ] || ([ -f /etc/init.d/salt-$fname ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
            __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}" /etc/init.d/
            chmod +x /etc/init.d/salt-${fname}

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            /sbin/chkconfig salt-${fname} on
        fi

    done

    if [ "$SYSTEMD_RELOAD" -eq $BS_TRUE ]; then
        /bin/systemctl daemon-reload
    fi
}

install_centos_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in minion master syndic api; do
        # Skip if not meant to be installed
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /sbin/initctl ] && [ -f /etc/init/salt-${fname}.conf ]; then
            # We have upstart support and upstart knows about our service
            /sbin/initctl status salt-$fname > /dev/null 2>&1
            if [ $? -ne 0 ]; then
                # Everything is in place and upstart gave us an error code? Fail!
                return 1
            fi

            # upstart knows about this service.
            # Let's try to stop it, and then start it
            /sbin/initctl stop salt-$fname > /dev/null 2>&1
            /sbin/initctl start salt-$fname > /dev/null 2>&1
            # Restart service
            if [ $? -ne 0 ]; then
                # Failed the restart?!
                return 1
            fi
        elif [ -f /etc/init.d/salt-$fname ]; then
            # Still in SysV init!?
            /etc/init.d/salt-$fname stop > /dev/null 2>&1
            /etc/init.d/salt-$fname start
        elif [ -f /usr/bin/systemctl ]; then
            # CentOS 7 uses systemd
            /usr/bin/systemctl stop salt-$fname > /dev/null 2>&1
            /usr/bin/systemctl start salt-$fname.service
        fi
    done
}

install_centos_testing_deps() {
    install_centos_stable_deps || return 1
    return 0
}

install_centos_testing() {
    install_centos_stable || return 1
    return 0
}

install_centos_testing_post() {
    install_centos_stable_post || return 1
    return 0
}

install_centos_check_services() {
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        if [ -f /sbin/initctl ] && [ -f /etc/init/salt-${fname}.conf ]; then
            __check_services_upstart salt-$fname || return 1
        elif [ -f /etc/init.d/salt-$fname ]; then
            __check_services_sysvinit salt-$fname || return 1
        elif [ -f /usr/bin/systemctl ]; then
            __check_services_systemd salt-$fname || return 1
        fi
    done
    return 0
}
#
#   Ended CentOS Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   RedHat Install Functions
#
install_red_hat_linux_stable_deps() {
    install_centos_stable_deps || return 1
    return 0
}

install_red_hat_linux_git_deps() {
    install_centos_git_deps || return 1
    return 0
}

install_red_hat_enterprise_linux_stable_deps() {
    install_red_hat_linux_stable_deps || return 1
    return 0
}

install_red_hat_enterprise_linux_git_deps() {
    install_red_hat_linux_git_deps || return 1
    return 0
}

install_red_hat_enterprise_server_stable_deps() {
    install_red_hat_linux_stable_deps || return 1
    return 0
}

install_red_hat_enterprise_server_git_deps() {
    install_red_hat_linux_git_deps || return 1
    return 0
}

install_red_hat_enterprise_workstation_stable_deps() {
    install_red_hat_linux_stable_deps || return 1
    return 0
}

install_red_hat_enterprise_workstation_git_deps() {
    install_red_hat_linux_git_deps || return 1
    return 0
}

install_red_hat_linux_stable() {
    install_centos_stable || return 1
    return 0
}

install_red_hat_linux_git() {
    install_centos_git || return 1
    return 0
}

install_red_hat_enterprise_linux_stable() {
    install_red_hat_linux_stable || return 1
    return 0
}

install_red_hat_enterprise_linux_git() {
    install_red_hat_linux_git || return 1
    return 0
}

install_red_hat_enterprise_server_stable() {
    install_red_hat_linux_stable || return 1
    return 0
}

install_red_hat_enterprise_server_git() {
    install_red_hat_linux_git || return 1
    return 0
}

install_red_hat_enterprise_workstation_stable() {
    install_red_hat_linux_stable || return 1
    return 0
}

install_red_hat_enterprise_workstation_git() {
    install_red_hat_linux_git || return 1
    return 0
}

install_red_hat_linux_stable_post() {
    install_centos_stable_post || return 1
    return 0
}

install_red_hat_linux_restart_daemons() {
    install_centos_restart_daemons || return 1
    return 0
}

install_red_hat_linux_git_post() {
    install_centos_git_post || return 1
    return 0
}

install_red_hat_enterprise_linux_stable_post() {
    install_red_hat_linux_stable_post || return 1
    return 0
}

install_red_hat_enterprise_linux_restart_daemons() {
    install_red_hat_linux_restart_daemons || return 1
    return 0
}

install_red_hat_enterprise_linux_git_post() {
    install_red_hat_linux_git_post || return 1
    return 0
}

install_red_hat_enterprise_server_stable_post() {
    install_red_hat_linux_stable_post || return 1
    return 0
}

install_red_hat_enterprise_server_restart_daemons() {
    install_red_hat_linux_restart_daemons || return 1
    return 0
}

install_red_hat_enterprise_server_git_post() {
    install_red_hat_linux_git_post || return 1
    return 0
}

install_red_hat_enterprise_workstation_stable_post() {
    install_red_hat_linux_stable_post || return 1
    return 0
}

install_red_hat_enterprise_workstation_restart_daemons() {
    install_red_hat_linux_restart_daemons || return 1
    return 0
}

install_red_hat_enterprise_workstation_git_post() {
    install_red_hat_linux_git_post || return 1
    return 0
}

install_red_hat_linux_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_red_hat_linux_testing() {
    install_centos_testing || return 1
    return 0
}

install_red_hat_linux_testing_post() {
    install_centos_testing_post || return 1
    return 0
}

install_red_hat_enterprise_server_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_red_hat_enterprise_server_testing() {
    install_centos_testing || return 1
    return 0
}

install_red_hat_enterprise_server_testing_post() {
    install_centos_testing_post || return 1
    return 0
}

install_red_hat_enterprise_workstation_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_red_hat_enterprise_workstation_testing() {
    install_centos_testing || return 1
    return 0
}

install_red_hat_enterprise_workstation_testing_post() {
    install_centos_testing_post || return 1
    return 0
}
#
#   Ended RedHat Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Oracle Linux Install Functions
#
install_oracle_linux_stable_deps() {
    install_centos_stable_deps || return 1
    return 0
}

install_oracle_linux_git_deps() {
    install_centos_git_deps || return 1
    return 0
}

install_oracle_linux_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_oracle_linux_stable() {
    install_centos_stable || return 1
    return 0
}

install_oracle_linux_git() {
    install_centos_git || return 1
    return 0
}

install_oracle_linux_testing() {
    install_centos_testing || return 1
    return 0
}

install_oracle_linux_stable_post() {
    install_centos_stable_post || return 1
    return 0
}

install_oracle_linux_git_post() {
    install_centos_git_post || return 1
    return 0
}

install_oracle_linux_testing_post() {
    install_centos_testing_post || return 1
    return 0
}

install_oracle_linux_restart_daemons() {
    install_centos_restart_daemons || return 1
    return 0
}

install_oracle_linux_check_services() {
    install_centos_check_services || return 1
    return 0
}
#
#   Ended Oracle Linux Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Scientific Linux Install Functions
#
install_scientific_linux_stable_deps() {
    install_centos_stable_deps || return 1
    return 0
}

install_scientific_linux_git_deps() {
    install_centos_git_deps || return 1
    return 0
}

install_scientific_linux_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_scientific_linux_stable() {
    install_centos_stable || return 1
    return 0
}

install_scientific_linux_git() {
    install_centos_git || return 1
    return 0
}

install_scientific_linux_testing() {
    install_centos_testing || return 1
    return 0
}

install_scientific_linux_stable_post() {
    install_centos_stable_post || return 1
    return 0
}

install_scientific_linux_git_post() {
    install_centos_git_post || return 1
    return 0
}

install_scientific_linux_testing_post() {
    install_centos_testing_post || return 1
    return 0
}

install_scientific_linux_restart_daemons() {
    install_centos_restart_daemons || return 1
    return 0
}

install_scientific_linux_check_services() {
    install_centos_check_services || return 1
    return 0
}
#
#   Ended Scientific Linux Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Amazon Linux AMI Install Functions
#

install_amazon_linux_ami_deps() {

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # enable the EPEL repo
        /usr/bin/yum-config-manager --enable epel || return 1

        # exclude Salt and ZeroMQ packages from EPEL
        /usr/bin/yum-config-manager epel --setopt "epel.exclude=zeromq* salt* python-zmq*" --save || return 1

        __REPO_FILENAME="saltstack-repo.repo"

        if [ ! -s "/etc/yum.repos.d/${__REPO_FILENAME}" ]; then
          cat <<_eof > "/etc/yum.repos.d/${__REPO_FILENAME}"
[saltstack-repo]
disabled=False
name=SaltStack repo for RHEL/CentOS 6
gpgcheck=1
gpgkey=$HTTP_VAL://repo.saltstack.com/yum/redhat/6/\$basearch/$STABLE_REV/SALTSTACK-GPG-KEY.pub
baseurl=$HTTP_VAL://repo.saltstack.com/yum/redhat/6/\$basearch/$STABLE_REV/
humanname=SaltStack repo for RHEL/CentOS 6
_eof
        fi

        if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
            yum -y update || return 1
        fi
    fi

    __PACKAGES="PyYAML m2crypto python-crypto python-msgpack python-zmq python26-ordereddict python-jinja2 python-requests"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
        __PACKAGES="${__PACKAGES} python-pip"
    fi

    # shellcheck disable=SC2086
    yum -y install ${__PACKAGES} --enablerepo=${_EPEL_REPO}"" || return 1

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
        pip-python install "apache-libcloud>=$_LIBCLOUD_MIN_VERSION"
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        yum install -y ${_EXTRA_PACKAGES} --enablerepo=${_EPEL_REPO} || return 1
    fi
}

install_amazon_linux_ami_git_deps() {
    install_amazon_linux_ami_deps || return 1

    if ! __check_command_exists git; then
        yum -y install git --enablerepo=${_EPEL_REPO} || return 1
    fi

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            yum install -y python-tornado
        fi
    fi


    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_amazon_linux_ami_stable() {
    install_centos_stable || return 1
    return 0
}

install_amazon_linux_ami_stable_post() {
    install_centos_stable_post || return 1
    return 0
}

install_amazon_linux_ami_restart_daemons() {
    install_centos_restart_daemons || return 1
    return 0
}

install_amazon_linux_ami_git() {
    install_centos_git || return 1
    return 0
}

install_amazon_linux_ami_git_post() {
    install_centos_git_post || return 1
    return 0
}

install_amazon_linux_ami_testing() {
    install_centos_testing || return 1
    return 0
}

install_amazon_linux_ami_testing_post() {
    install_centos_testing_post || return 1
    return 0
}
#
#   Ended Amazon Linux AMI Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Arch Install Functions
#
install_arch_linux_stable_deps() {
    if [ ! -f /etc/pacman.d/gnupg ]; then
        pacman-key --init && pacman-key --populate archlinux || return 1
    fi

    pacman -Sy --noconfirm --needed pacman || return 1

    if __check_command_exists pacman-db-upgrade; then
        pacman-db-upgrade || return 1
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        pacman -Syyu --noconfirm --needed || return 1
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        pacman -Sy --noconfirm --needed apache-libcloud || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        pacman -Sy --noconfirm --needed ${_EXTRA_PACKAGES} || return 1
    fi
}

install_arch_linux_git_deps() {
    install_arch_linux_stable_deps

    # Don't fail if un-installing python2-distribute threw an error
    if ! __check_command_exists git; then
        pacman -Sy --noconfirm --needed git  || return 1
    fi
    pacman -R --noconfirm python2-distribute
    pacman -Sy --noconfirm --needed python2-crypto python2-setuptools python2-jinja \
        python2-m2crypto python2-markupsafe python2-msgpack python2-psutil python2-yaml \
        python2-pyzmq zeromq python2-requests python2-systemd || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            pacman -Sy --noconfirm --needed python2-tornado
        fi
    fi


    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_arch_linux_stable() {
    pacman -Sy --noconfirm --needed pacman || return 1
    # See https://mailman.archlinux.org/pipermail/arch-dev-public/2013-June/025043.html
    # to know why we're ignoring below.
    pacman -Syu --noconfirm --ignore filesystem,bash || return 1
    pacman -S --noconfirm --needed bash || return 1
    pacman -Su --noconfirm || return 1
    # We can now resume regular salt update
    pacman -Syu --noconfirm salt-zmq || return 1
    return 0
}

install_arch_linux_git() {
    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python2 setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" install || return 1
    else
        python2 setup.py install || return 1
    fi
    return 0
}

install_arch_linux_post() {
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        # Since Arch's pacman renames configuration files
        if [ "$_TEMP_CONFIG_DIR" != "null" ] && [ -f "$_SALT_ETC_DIR/$fname.pacorig" ]; then
            # Since a configuration directory was provided, it also means that any
            # configuration file copied was renamed by Arch, see:
            #   https://wiki.archlinux.org/index.php/Pacnew_and_Pacsave_Files#.pacorig
            __copyfile "$_SALT_ETC_DIR/$fname.pacorig" "$_SALT_ETC_DIR/$fname" $BS_TRUE
        fi

        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        if [ -f /usr/bin/systemctl ]; then
            # Using systemd
            /usr/bin/systemctl is-enabled salt-$fname.service > /dev/null 2>&1 || (
                /usr/bin/systemctl preset salt-$fname.service > /dev/null 2>&1 &&
                /usr/bin/systemctl enable salt-$fname.service > /dev/null 2>&1
            )
            sleep 0.1
            /usr/bin/systemctl daemon-reload
            continue
        fi

        # XXX: How do we enable old Arch init.d scripts?
    done
}

install_arch_linux_git_post() {
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /usr/bin/systemctl ]; then
            __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            /usr/bin/systemctl is-enabled salt-${fname}.service > /dev/null 2>&1 || (
                /usr/bin/systemctl preset salt-${fname}.service > /dev/null 2>&1 &&
                /usr/bin/systemctl enable salt-${fname}.service > /dev/null 2>&1
            )
            sleep 0.1
            /usr/bin/systemctl daemon-reload
            continue
        fi

        # SysV init!?
        __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-$fname" "/etc/rc.d/init.d/salt-$fname"
        chmod +x /etc/rc.d/init.d/salt-$fname
    done
}

install_arch_linux_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /usr/bin/systemctl ]; then
            /usr/bin/systemctl stop salt-$fname.service > /dev/null 2>&1
            /usr/bin/systemctl start salt-$fname.service
            continue
        fi
        /etc/rc.d/salt-$fname stop > /dev/null 2>&1
        /etc/rc.d/salt-$fname start
    done
}

install_arch_check_services() {
    if [ ! -f /usr/bin/systemctl ]; then
        # Not running systemd!? Don't check!
        return 0
    fi

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        __check_services_systemd salt-$fname || return 1
    done
    return 0
}
#
#   Ended Arch Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   FreeBSD Install Functions
#
config_freebsd_salt() {
    _SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/usr/local/etc/salt}
    config_salt
}

__freebsd_get_packagesite() {
    if [ "$CPU_ARCH_L" = "amd64" ]; then
        BSD_ARCH="x86:64"
    elif [ "$CPU_ARCH_L" = "x86_64" ]; then
        BSD_ARCH="x86:64"
    elif [ "$CPU_ARCH_L" = "i386" ]; then
        BSD_ARCH="x86:32"
    elif [ "$CPU_ARCH_L" = "i686" ]; then
        BSD_ARCH="x86:32"
    fi

    # Since the variable might not be set, don't, momentarily treat it as a
    # failure
    set +o nounset

    # ABI is a std format for identifying release / architecture combos
    ABI="freebsd:${DISTRO_MAJOR_VERSION}:${BSD_ARCH}"
    _PACKAGESITE="http://pkg.freebsd.org/${ABI}/latest"
    # Awkwardly, we want the `${ABI}` to be in conf file without escaping
    PKGCONFURL="pkg+http://pkg.freebsd.org/\${ABI}/latest"
    SALTPKGCONFURL="http://repo.saltstack.com/freebsd/\${ABI}/"

    # Treat unset variables as errors once more
    set -o nounset
}

# Using a separate conf step to head for idempotent install...
__configure_freebsd_pkg_details() {
    ## pkg.conf is deprecated.
    ## We use conf files in /usr/local or /etc instead
    mkdir -p /usr/local/etc/pkg/repos/
    mkdir -p /etc/pkg/

    ## Use new JSON-like format for pkg repo configs
    ## check if /etc/pkg/FreeBSD.conf is already in place
    if [ ! -f /etc/pkg/FreeBSD.conf ]; then
      conf_file=/usr/local/etc/pkg/repos/freebsd.conf
      {
          echo "FreeBSD:{"
          echo "    url: \"${PKGCONFURL}\","
          echo "    mirror_type: \"srv\","
          echo "    signature_type: \"fingerprints\","
          echo "    fingerprints: \"/usr/share/keys/pkg\","
          echo "    enabled: true"
          echo "}"
      } > $conf_file
      __copyfile $conf_file /etc/pkg/FreeBSD.conf
    fi
    FROM_FREEBSD="-r FreeBSD"

    ## add saltstack freebsd repo
    salt_conf_file=/usr/local/etc/pkg/repos/saltstack.conf
    {
        echo "SaltStack:{"
        echo "    url: \"${SALTPKGCONFURL}\","
        echo "    mirror_type: \"http\","
        echo "    enabled: true"
        echo "    prioroity: 10"
        echo "}"
    } > $salt_conf_file
    FROM_SALTSTACK="-r SaltStack"

    ## ensure future ports builds use pkgng
    echo "WITH_PKGNG=   yes" >> /etc/make.conf
}

install_freebsd_9_stable_deps() {

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        #make variables available even if pkg already installed
        __freebsd_get_packagesite

        if [ ! -x /usr/local/sbin/pkg ]; then

            # install new `pkg` code from its own tarball.
            fetch "${_PACKAGESITE}/Latest/pkg.txz" || return 1
            tar xf ./pkg.txz -s ",/.*/,,g" "*/pkg-static" || return 1
            ./pkg-static add ./pkg.txz || return 1
            /usr/local/sbin/pkg2ng || return 1
        fi

        # Configure the pkg repository using new approach
        __configure_freebsd_pkg_details || return 1
    fi

    # Now install swig
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_FREEBSD} -y swig || return 1

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        /usr/local/sbin/pkg install ${FROM_FREEBSD} -y ${_EXTRA_PACKAGES} || return 1
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        pkg upgrade -y || return 1
    fi

    return 0
}

install_freebsd_10_stable_deps() {
    install_freebsd_9_stable_deps
}

install_freebsd_11_stable_deps() {
    install_freebsd_9_stable_deps
}

install_freebsd_git_deps() {
    install_freebsd_9_stable_deps || return 1

    if ! __check_command_exists git; then
        /usr/local/sbin/pkg install -y git || return 1
    fi

    /usr/local/sbin/pkg install -y www/py-requests || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
             /usr/local/sbin/pkg install -y www/py-tornado || return 1
        fi
    fi

    echodebug "Adapting paths to FreeBSD"
    # The list of files was taken from Salt's BSD port Makefile
    for file in doc/man/salt-key.1 doc/man/salt-cp.1 doc/man/salt-minion.1 \
                doc/man/salt-syndic.1 doc/man/salt-master.1 doc/man/salt-run.1 \
                doc/man/salt.7 doc/man/salt.1 doc/man/salt-call.1; do
        [ ! -f $file ] && continue
        echodebug "Patching ${file}"
        sed -in -e "s|/etc/salt|${_SALT_ETC_DIR}|" \
                -e "s|/srv/salt|${_SALT_ETC_DIR}/states|" \
                -e "s|/srv/pillar|${_SALT_ETC_DIR}/pillar|" ${file}
    done
    if [ ! -f salt/syspaths.py ]; then
        # We still can't provide the system paths, salt 0.16.x
        # Let's patch salt's source and adapt paths to what's expected on FreeBSD
        echodebug "Replacing occurrences of '/etc/salt' with \'${_SALT_ETC_DIR}\'"
        # The list of files was taken from Salt's BSD port Makefile
        for file in conf/minion conf/master salt/config.py salt/client.py \
                    salt/modules/mysql.py salt/utils/parsers.py salt/modules/tls.py \
                    salt/modules/postgres.py salt/utils/migrations.py; do
            [ ! -f $file ] && continue
            echodebug "Patching ${file}"
            sed -in -e "s|/etc/salt|${_SALT_ETC_DIR}|" \
                    -e "s|/srv/salt|${_SALT_ETC_DIR}/states|" \
                    -e "s|/srv/pillar|${_SALT_ETC_DIR}/pillar|" ${file}
        done
    fi
    echodebug "Finished patching"

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"

        # Set _SALT_ETC_DIR to ports default
        _SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/usr/local/etc/salt}
        # We also need to redefine the PKI directory
        _PKI_DIR=${_SALT_ETC_DIR}/pki
    fi

    return 0
}

install_freebsd_9_stable() {
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_SALTSTACK} -y sysutils/py-salt || return 1
    return 0
}

install_freebsd_10_stable() {
    install_freebsd_9_stable
}

install_freebsd_11_stable() {
#
# installing latest version of salt from FreeBSD CURRENT ports repo
#
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_FREEBSD} -y sysutils/py-salt || return 1

#
# setting _SALT_ETC_DIR to match paths from FreeBSD ports:
#
    _SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/usr/local/etc/salt}
    if [ ! -d /etc/salt ]; then
      ln -sf "${_SALT_ETC_DIR}" /etc/salt
    fi
    return 0
}

install_freebsd_git() {
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_SALTSTACK} -y sysutils/py-salt || return 1

    # Let's keep the rc.d files before deleting the package
    mkdir /tmp/rc-scripts || return 1
    cp /usr/local/etc/rc.d/salt* /tmp/rc-scripts || return 1

    # Let's delete the package
    /usr/local/sbin/pkg delete -y sysutils/py-salt || return 1

    # Install from git
    if [ ! -f salt/syspaths.py ]; then
        # We still can't provide the system paths, salt 0.16.x
        /usr/local/bin/python2 setup.py install || return 1
    else
        /usr/local/bin/python2 setup.py \
            --salt-root-dir=/usr/local \
            --salt-config-dir="${_SALT_ETC_DIR}" \
            --salt-cache-dir="${_SALT_CACHE_DIR}" \
            --salt-sock-dir=/var/run/salt \
            --salt-srv-root-dir=/srv \
            --salt-base-file-roots-dir="${_SALT_ETC_DIR}/states" \
            --salt-base-pillar-roots-dir="${_SALT_ETC_DIR}/pillar" \
            --salt-base-master-roots-dir="${_SALT_ETC_DIR}/salt-master" \
            --salt-logs-dir=/var/log/salt \
            --salt-pidfile-dir=/var/run install \
            || return 1
    fi

    # Restore the rc.d scripts
    cp /tmp/rc-scripts/salt* /usr/local/etc/rc.d/ || return 1

    # Delete our temporary scripts directory
    rm -rf /tmp/rc-scripts || return 1

    # And we're good to go
    return 0
}

install_freebsd_9_stable_post() {
    for fname in minion master syndic api; do

        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        enable_string="salt_${fname}_enable=\"YES\""
        grep "$enable_string" /etc/rc.conf >/dev/null 2>&1
        [ $? -eq 1 ] && echo "$enable_string" >> /etc/rc.conf

        if [ $fname = "minion" ] ; then
            grep "salt_minion_paths" /etc/rc.conf >/dev/null 2>&1
            [ $? -eq 1 ] && echo "salt_minion_paths=\"/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin\"" >> /etc/rc.conf
        fi

    done
}

install_freebsd_10_stable_post() {
    install_freebsd_9_stable_post
}

install_freebsd_11_stable_post() {
    install_freebsd_9_stable_post
}

install_freebsd_git_post() {
    install_freebsd_9_stable_post || return 1
    return 0
}

install_freebsd_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        service salt_$fname stop > /dev/null 2>&1
        service salt_$fname start
    done
}
#
#   Ended FreeBSD Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   OpenBSD Install Functions
#

__choose_openbsd_mirror() {
    # FIXME: cleartext download over unsecure protocol (HTTP)
    MIRRORS_LIST_URL=http://www.openbsd.org/ftp.html
    MIRROR_LIST_FILE=/tmp/openbsd-mirrors.html
    OPENBSD_REPO=''
    MINTIME=''

    __fetch_url "$MIRROR_LIST_FILE" "$MIRRORS_LIST_URL" || return 1
    MIRRORS_LIST=$(grep href "$MIRROR_LIST_FILE" | grep http | grep pub | awk -F \" '{ print $2 }')
    [ -n "$MIRRORS_LIST" ] && rm -f "$MIRROR_LIST_FILE"

    echoinfo "Getting list of mirrors from $MIRRORS_LIST_URL"
    for MIRROR in $MIRRORS_LIST; do
        MIRROR_HOST=$(echo "$MIRROR" | awk -F / '{ print $3 }')
        TIME=$(ping -c 1 -q "$MIRROR_HOST" | grep round-trip | awk -F / '{ print $5 }')
        [ -z "$TIME" ] && continue

        echodebug "ping time for $MIRROR is $TIME"
        [ -z "$MINTIME" ] && MINTIME=$TIME

        FASTER_MIRROR=$(echo "$TIME < $MINTIME" | bc)
        if [ "$FASTER_MIRROR" -eq 1 ]; then
            MINTIME=$TIME
            OPENBSD_REPO=$MIRROR
        else
            continue
        fi
    done
}


install_openbsd_deps() {
    __choose_openbsd_mirror || return 1
    [ -n "$OPENBSD_REPO" ] || return 1
    echoinfo "setting package repository to $OPENBSD_REPO with ping time of $MINTIME"
    echo "installpath = ${OPENBSD_REPO}${OS_VERSION}/packages/${CPU_ARCH_L}/" >/etc/pkg.conf || return 1
    pkg_add -I -v lsof || return 1
    pkg_add -I -v py-pip || return 1
    __linkfile /usr/local/bin/pip2.* /usr/local/bin/pip $BS_TRUE || return 1
    __linkfile /usr/local/bin/pydoc2* /usr/local/bin/pydoc $BS_TRUE || return 1
    __linkfile /usr/local/bin/python2.[0-9] /usr/local/bin/python $BS_TRUE || return 1
    __linkfile /usr/local/bin/python2.[0-9]*to3 /usr/local/bin/2to3 $BS_TRUE || return 1
    __linkfile /usr/local/bin/python2.[0-9]*-config /usr/local/bin/python-config $BS_TRUE || return 1
    pkg_add -I -v swig || return 1
    pkg_add -I -v py-zmq || return 1
    pkg_add -I -v py-requests || return 1
    pkg_add -I -v py-M2Crypto || return 1
    pkg_add -I -v py-raet || return 1
    pkg_add -I -v py-libnacl || return 1
    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        /usr/local/bin/pip install --upgrade pip || return 1
    fi
    #
    # PIP based installs need to copy configuration files "by hand".
    # Let's trigger config_salt()
    #
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        # Let's set the configuration directory to /tmp
        _TEMP_CONFIG_DIR="/tmp"
         CONFIG_SALT_FUNC="config_salt"

        for fname in minion master syndic api; do
            # Skip if not meant to be installed
            [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
            [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
            [ $fname = "api" ] && \
                ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || __check_command_exists "salt-${fname}") && \
                    continue
            [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

            # Let's download, since they were not provided, the default configuration files
            if [ ! -f "$_SALT_ETC_DIR/$fname" ] && [ ! -f "$_TEMP_CONFIG_DIR/$fname" ]; then
                ftp -o "$_TEMP_CONFIG_DIR/$fname" \
                    "https://raw.githubusercontent.com/saltstack/salt/develop/conf/$fname" || return 1
            fi
        done
    fi
    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        pkg_add -I -v ${_EXTRA_PACKAGES} || return 1
    fi
    return 0
}

install_openbsd_git_deps() {
    install_openbsd_deps || return 1
    pkg_add -I -v git || return 1
    __git_clone_and_checkout || return 1
    #
    # Let's trigger config_salt()
    #
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi
    return 0
}

install_openbsd_stable() {

#    pkg_add -r -I -v salt || return 1
    __check_pip_allowed || return 1
    /usr/local/bin/pip install salt || return 1
    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
         /usr/local/bin/pip install --upgrade salt || return 1
    fi
    return 0
}

install_openbsd_git() {
    #
    # Install from git
    #
    if [ ! -f salt/syspaths.py ]; then
        # We still can't provide the system paths, salt 0.16.x
        /usr/local/bin/python2.7 setup.py install || return 1
    fi
    return 0
}


install_openbsd_post() {
    #
    # Install rc.d files.
    #
    ## below workaround for /etc/rc.d/rc.subr in OpenBSD >= 5.8
    ## is needed for salt services to start/stop properly from /etc/rc.d
    ## reference: http://cvsweb.openbsd.org/cgi-bin/cvsweb/src/etc/rc.d/rc.subr.diff?r1=1.98&r2=1.99
    ##
    if grep -q '\-xf' /etc/rc.d/rc.subr; then
        cp -p /etc/rc.d/rc.subr /etc/rc.d/rc.subr
        sed -i."$(date +%F)".saltinstall -e 's:-xf:-f:g' /etc/rc.d/rc.subr
    fi
    _TEMP_CONFIG_DIR="/tmp"
    for fname in minion master syndic api; do
        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] || ! __check_command_exists "salt-${fname}" && continue
        [ $fname = "syndic" ] && continue

        if [ $? -eq 1 ]; then
            if [ ! -f "$_TEMP_CONFIG_DIR/salt-$fname" ]; then
                ftp -o "$_TEMP_CONFIG_DIR/salt-$fname" \
                    "https://raw.githubusercontent.com/saltstack/salt/develop/pkg/openbsd/salt-${fname}.rc-d"
                if [ ! -f "/etc/rc.d/salt_${fname}" ] && [ "$(grep salt_${fname} /etc/rc.conf.local)" -eq "" ]; then
                    __copyfile "$_TEMP_CONFIG_DIR/salt-$fname" "/etc/rc.d/salt_${fname}" && chmod +x "/etc/rc.d/salt_${fname}" || return 1
                    echo salt_${fname}_enable="YES" >> /etc/rc.conf.local
                    echo salt_${fname}_paths=\"/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin\" >>/etc/rc.conf.local
                fi
            fi
        fi
    done
}

install_openbsd_check_services() {
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && continue
        [ $fname = "syndic" ] && continue
        if [ -f /etc/rc.d/salt_${fname} ]; then
            __check_services_openbsd salt_${fname} || return 1
        fi
    done
    return 0
}


install_openbsd_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue
        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        if [ -f "/etc/rc.d/salt_${fname}" ]; then
            /etc/rc.d/salt_${fname} stop > /dev/null 2>&1
            /etc/rc.d/salt_${fname} start
        fi
    done
}


#
#   Ended OpenBSD Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   SmartOS Install Functions
#
install_smartos_deps() {
    pkgin -y install zeromq py27-m2crypto py27-crypto py27-msgpack py27-yaml py27-jinja2 py27-zmq py27-requests || return 1

    # Set _SALT_ETC_DIR to SmartOS default if they didn't specify
    _SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/opt/local/etc/salt}
    # We also need to redefine the PKI directory
    _PKI_DIR=${_SALT_ETC_DIR}/pki

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        # Let's set the configuration directory to /tmp
        _TEMP_CONFIG_DIR="/tmp"
        CONFIG_SALT_FUNC="config_salt"

        # Let's download, since they were not provided, the default configuration files
        if [ ! -f "$_SALT_ETC_DIR/minion" ] && [ ! -f "$_TEMP_CONFIG_DIR/minion" ]; then
            # shellcheck disable=SC2086
            curl $_CURL_ARGS -s -o "$_TEMP_CONFIG_DIR/minion" -L \
                https://raw.githubusercontent.com/saltstack/salt/develop/conf/minion || return 1
        fi
        if [ ! -f "$_SALT_ETC_DIR/master" ] && [ ! -f $_TEMP_CONFIG_DIR/master ]; then
            # shellcheck disable=SC2086
            curl $_CURL_ARGS -s -o "$_TEMP_CONFIG_DIR/master" -L \
                https://raw.githubusercontent.com/saltstack/salt/develop/conf/master || return 1
        fi
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE  ]; then
        pkgin -y install py27-apache-libcloud || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        pkgin -y install ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_smartos_git_deps() {
    install_smartos_deps || return 1

    if ! __check_command_exists git; then
        pkgin -y install git || return 1
    fi

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install the python package '${__REQUIRED_TORNADO}'"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            if ! __check_command_exists pip; then
                pkgin -y install py27-pip
            fi
            pip install -U "${__REQUIRED_TORNADO}"
        fi
    fi

    __git_clone_and_checkout || return 1
    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_smartos_stable() {
    pkgin -y install salt || return 1
    return 0
}

install_smartos_git() {
    # Use setuptools in order to also install dependencies
    # lets force our config path on the setup for now, since salt/syspaths.py only  got fixed in 2015.5.0
    USE_SETUPTOOLS=1 /opt/local/bin/python setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" install || return 1
    return 0
}

install_smartos_post() {
    smf_dir="/opt/custom/smf"
    # Install manifest files if needed.
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        svcs network/salt-$fname > /dev/null 2>&1
        if [ $? -eq 1 ]; then
            if [ ! -f "$_TEMP_CONFIG_DIR/salt-$fname.xml" ]; then
                # shellcheck disable=SC2086
                curl $_CURL_ARGS -s -o "$_TEMP_CONFIG_DIR/salt-$fname.xml" -L \
                    "https://raw.githubusercontent.com/saltstack/salt/develop/pkg/smartos/salt-$fname.xml"
            fi
            svccfg import "$_TEMP_CONFIG_DIR/salt-$fname.xml"
            if [ "${VIRTUAL_TYPE}" = "global" ]; then
                if [ ! -d "$smf_dir" ]; then
                    mkdir -p "$smf_dir" || return 1
                fi
                if [ ! -f "$smf_dir/salt-$fname.xml" ]; then
                    __copyfile "$_TEMP_CONFIG_DIR/salt-$fname.xml" "$smf_dir/" || return 1
                fi
            fi
        fi
    done
}

install_smartos_git_post() {
    smf_dir="/opt/custom/smf"
    # Install manifest files if needed.
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        svcs "network/salt-$fname" > /dev/null 2>&1
        if [ $? -eq 1 ]; then
            svccfg import "${_SALT_GIT_CHECKOUT_DIR}/pkg/smartos/salt-$fname.xml"
            if [ "${VIRTUAL_TYPE}" = "global" ]; then
                if [ ! -d $smf_dir ]; then
                    mkdir -p "$smf_dir"
                fi
                if [ ! -f "$smf_dir/salt-$fname.xml" ]; then
                    __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/smartos/salt-$fname.xml" "$smf_dir/"
                fi
            fi
        fi
    done
}

install_smartos_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        # Stop if running && Start service
        svcadm disable salt-$fname > /dev/null 2>&1
        svcadm enable salt-$fname
    done
}
#
#   Ended SmartOS Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#    openSUSE Install Functions.
#
__ZYPPER_REQUIRES_REPLACE_FILES=-1

__version_lte() {
    if ! __check_command_exists python; then
        zypper zypper --non-interactive install --replacefiles --auto-agree-with-licenses python || \
             zypper zypper --non-interactive install --auto-agree-with-licenses python || return 1
    fi

    if [ "$(python -c 'import sys; V1=tuple([int(i) for i in sys.argv[1].split(".")]); V2=tuple([int(i) for i in sys.argv[2].split(".")]); print V1<=V2' "$1" "$2")" = "True" ]; then
        __ZYPPER_REQUIRES_REPLACE_FILES=${BS_TRUE}
    else
        __ZYPPER_REQUIRES_REPLACE_FILES=${BS_FALSE}
    fi
}

__zypper() {
    zypper --non-interactive "${@}"; return $?
}

__zypper_install() {
    if [ "${__ZYPPER_REQUIRES_REPLACE_FILES}" = "-1" ]; then
        __version_lte "1.10.4" "$(zypper --version | awk '{ print $2 }')"
    fi
    if [ "${__ZYPPER_REQUIRES_REPLACE_FILES}" = "${BS_TRUE}" ]; then
        # In case of file conflicts replace old files.
        # Option present in zypper 1.10.4 and newer:
        # https://github.com/openSUSE/zypper/blob/95655728d26d6d5aef7796b675f4cc69bc0c05c0/package/zypper.changes#L253
        __zypper install --auto-agree-with-licenses --replacefiles "${@}"; return $?
    else
        __zypper install --auto-agree-with-licenses "${@}"; return $?
    fi
}

install_opensuse_stable_deps() {
    if [ "${DISTRO_MAJOR_VERSION}" -gt 2015 ]; then
        DISTRO_REPO="openSUSE_Tumbleweed"
    elif [ "${DISTRO_MAJOR_VERSION}" -ge 42 ]; then
        DISTRO_REPO="openSUSE_Leap_${DISTRO_MAJOR_VERSION}.${DISTRO_MINOR_VERSION}"
    elif [ "${DISTRO_MAJOR_VERSION}" -lt 42 ]; then
        DISTRO_REPO="openSUSE_${DISTRO_MAJOR_VERSION}.${DISTRO_MINOR_VERSION}"
    fi

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Is the repository already known
        __set_suse_pkg_repo
        __zypper repos --details | grep "${SUSE_PKG_URL}" >/dev/null 2>&1
        if [ $? -eq 1 ]; then
            # zypper does not yet know anything about systemsmanagement_saltstack
            __zypper addrepo --refresh "${SUSE_PKG_URL}" || return 1
        fi
    fi

    __zypper --gpg-auto-import-keys refresh
    if [ $? -ne 0 ] && [ $? -ne 4 ]; then
        # If the exit code is not 0, and it's not 4 (failed to update a
        # repository) return a failure. Otherwise continue.
        return 1
    fi

    if [ "$DISTRO_MAJOR_VERSION" -eq 12 ] && [ "$DISTRO_MINOR_VERSION" -eq 3 ]; then
        # Because patterns-openSUSE-minimal_base-conflicts conflicts with python, lets remove the first one
        __zypper remove patterns-openSUSE-minimal_base-conflicts
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __zypper --gpg-auto-import-keys update || return 1
    fi

    # Salt needs python-zypp installed in order to use the zypper module
    __PACKAGES="python-zypp"
    __PACKAGES="${__PACKAGES} python python-Jinja2 python-M2Crypto python-PyYAML python-requests"
    __PACKAGES="${__PACKAGES} python-msgpack-python python-pycrypto python-pyzmq python-xml"

    if [ "$DISTRO_MAJOR_VERSION" -lt 13 ]; then
        __PACKAGES="${__PACKAGES} libzmq3"
    elif [ "$DISTRO_MAJOR_VERSION" -eq 13 ]; then
        __PACKAGES="${__PACKAGES} libzmq3"
    elif [ "$DISTRO_MAJOR_VERSION" -gt 13 ]; then
        __PACKAGES="${__PACKAGES} libzmq5"
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-apache-libcloud"
    fi

    # shellcheck disable=SC2086
    __zypper_install ${__PACKAGES} || return 1

    # Fix for OpenSUSE 13.2 and 2015.8 - gcc should not be required. Work around until package is fixed by SuSE
    _EXTRA_PACKAGES="${_EXTRA_PACKAGES} gcc python-devel libgit2-devel"

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __zypper_install ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_opensuse_git_deps() {
    install_opensuse_stable_deps || return 1

    if ! __check_command_exists git; then
        __zypper_install git  || return 1
    fi

    __zypper_install patch || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __zypper_install python-tornado
        fi

    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_opensuse_stable() {
    __PACKAGES=""
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi
    # shellcheck disable=SC2086
    __zypper_install $__PACKAGES || return 1
    return 0
}

install_opensuse_git() {
    python setup.py install --prefix=/usr || return 1
    return 0
}

install_opensuse_stable_post() {
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            systemctl is-enabled salt-$fname.service || (systemctl preset salt-$fname.service && systemctl enable salt-$fname.service)
            sleep 0.1
            systemctl daemon-reload
            continue
        fi

        /sbin/chkconfig --add salt-$fname
        /sbin/chkconfig salt-$fname on

    done
}

install_opensuse_git_post() {
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            if [ "${DISTRO_MAJOR_VERSION}" -gt 13 ] || ([ "${DISTRO_MAJOR_VERSION}" -eq 13 ] && [ "${DISTRO_MINOR_VERSION}" -ge 2 ]); then
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" "/usr/lib/systemd/system/salt-${fname}.service"
            else
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"
            fi
            continue
        fi

        __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-$fname" "/etc/init.d/salt-$fname"
        chmod +x /etc/init.d/salt-$fname

    done

    install_opensuse_stable_post
}

install_opensuse_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            systemctl stop salt-$fname > /dev/null 2>&1
            systemctl start salt-$fname.service
            continue
        fi

        service salt-$fname stop > /dev/null 2>&1
        service salt-$fname start

    done
}

install_opensuse_check_services() {
    if [ ! -f /bin/systemctl ]; then
        # Not running systemd!? Don't check!
        return 0
    fi

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        __check_services_systemd salt-$fname > /dev/null 2>&1 || __check_services_systemd salt-$fname.service > /dev/null 2>&1 || return 1
    done
    return 0
}
#
#   End of openSUSE Install Functions.
#
#######################################################################################################################

#######################################################################################################################
#
#   SUSE Enterprise 12
#

install_suse_12_stable_deps() {
    SUSE_PATCHLEVEL=$(awk '/PATCHLEVEL/ {print $3}' /etc/SuSE-release )

    if [ "${SUSE_PATCHLEVEL}" != "" ]; then
        DISTRO_PATCHLEVEL="_SP${SUSE_PATCHLEVEL}"
    fi
    DISTRO_REPO="SLE_${DISTRO_MAJOR_VERSION}${DISTRO_PATCHLEVEL}"

    # SLES 12 repo name does not use a patch level so PATCHLEVEL will need to be updated with SP1
    #DISTRO_REPO="SLE_${DISTRO_MAJOR_VERSION}${DISTRO_PATCHLEVEL}"

    DISTRO_REPO="SLE_${DISTRO_MAJOR_VERSION}"

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Is the repository already known
        __set_suse_pkg_repo
        __zypper repos | grep "${SUSE_PKG_URL}" >/dev/null 2>&1
        if [ $? -eq 1 ]; then
            # zypper does not yet know nothing about systemsmanagement_saltstack
            __zypper addrepo --refresh "${SUSE_PKG_URL}" || return 1
        fi
    fi

    __zypper --gpg-auto-import-keys refresh || return 1

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __zypper --gpg-auto-import-keys update || return 1
    fi

    # Salt needs python-zypp installed in order to use the zypper module
    __PACKAGES="python-zypp"
    # shellcheck disable=SC2089
    __PACKAGES="${__PACKAGES} libzmq5 python python-Jinja2 python-msgpack-python"
    __PACKAGES="${__PACKAGES} python-pycrypto python-pyzmq python-pip python-xml python-requests"

    if [ "$SUSE_PATCHLEVEL" -eq 1 ]; then
        __check_pip_allowed
        echowarn "PyYaml will be installed using pip"
    else
        __PACKAGES="${__PACKAGES} python-PyYAML"
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-apache-libcloud"
    fi

    # SLES 11 SP3 ships with both python-M2Crypto-0.22.* and python-m2crypto-0.21 and we will be asked which
    # we want to install, even with --non-interactive.
    # Let's try to install the higher version first and then the lower one in case of failure
    __zypper_install 'python-M2Crypto>=0.22' || __zypper_install 'python-M2Crypto>=0.21' || return 1
    # shellcheck disable=SC2086,SC2090
    __zypper_install ${__PACKAGES} || return 1

    if [ "$SUSE_PATCHLEVEL" -eq 1 ]; then
        # There's no python-PyYaml in SP1, let's install it using pip
        pip install PyYaml || return 1
    fi

    # PIP based installs need to copy configuration files "by hand".
    if [ "$SUSE_PATCHLEVEL" -eq 1 ]; then
        # Let's trigger config_salt()
        if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
            # Let's set the configuration directory to /tmp
            _TEMP_CONFIG_DIR="/tmp"
            CONFIG_SALT_FUNC="config_salt"

            for fname in minion master syndic api; do

                # Skip if not meant to be installed
                [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
                [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
                [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
                [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

                # Syndic uses the same configuration file as the master
                [ $fname = "syndic" ] && fname=master

                # Let's download, since they were not provided, the default configuration files
                if [ ! -f "$_SALT_ETC_DIR/$fname" ] && [ ! -f "$_TEMP_CONFIG_DIR/$fname" ]; then
                    # shellcheck disable=SC2086
                    curl $_CURL_ARGS -s -o "$_TEMP_CONFIG_DIR/$fname" -L \
                        "https://raw.githubusercontent.com/saltstack/salt/develop/conf/$fname" || return 1
                fi
            done
        fi
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __zypper_install ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_suse_12_git_deps() {
    install_suse_11_stable_deps || return 1

    if ! __check_command_exists git; then
        __zypper_install git  || return 1
    fi

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __zypper_install python-tornado
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_suse_12_stable() {
    if [ "$SUSE_PATCHLEVEL" -gt 1 ]; then
        install_opensuse_stable || return 1
    else
        # USE_SETUPTOOLS=1 To work around
        # error: option --single-version-externally-managed not recognized
        USE_SETUPTOOLS=1 pip install salt || return 1
    fi
    return 0
}

install_suse_12_git() {
    install_opensuse_git || return 1
    return 0
}

install_suse_12_stable_post() {
    if [ "$SUSE_PATCHLEVEL" -gt 1 ]; then
        install_opensuse_stable_post || return 1
    else
        for fname in minion master syndic api; do

            # Skip if not meant to be installed
            [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
            [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
            [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
            [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

            if [ -f /bin/systemctl ]; then
                # shellcheck disable=SC2086
                curl $_CURL_ARGS -L "https://github.com/saltstack/salt/raw/develop/pkg/salt-$fname.service" \
                    -o "/usr/lib/systemd/system/salt-$fname.service" || return 1
                continue
            fi

            ## shellcheck disable=SC2086
            #curl $_CURL_ARGS -L "https://github.com/saltstack/salt/raw/develop/pkg/rpm/salt-$fname" \
            #    -o "/etc/init.d/salt-$fname" || return 1
            #chmod +x "/etc/init.d/salt-$fname"

            if [ -f /bin/systemctl ]; then
                systemctl is-enabled salt-$fname.service || (systemctl preset salt-$fname.service && systemctl enable salt-$fname.service)
                sleep 0.1
                systemctl daemon-reload
                continue
            fi

        done
    fi
    return 0
}

install_suse_12_git_post() {
    install_opensuse_git_post || return 1
    return 0
}

install_suse_12_restart_daemons() {
    install_opensuse_restart_daemons || return 1
    return 0
}

#
#   End of SUSE Enterprise 12
#
#######################################################################################################################

#######################################################################################################################
#
#   SUSE Enterprise 11
#

install_suse_11_stable_deps() {
    SUSE_PATCHLEVEL=$(awk '/PATCHLEVEL/ {print $3}' /etc/SuSE-release )
    if [ "${SUSE_PATCHLEVEL}" != "" ]; then
        DISTRO_PATCHLEVEL="_SP${SUSE_PATCHLEVEL}"
    fi
    DISTRO_REPO="SLE_${DISTRO_MAJOR_VERSION}${DISTRO_PATCHLEVEL}"

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Is the repository already known
        __set_suse_pkg_repo
        __zypper repos | grep "${SUSE_PKG_URL}" >/dev/null 2>&1
        if [ $? -eq 1 ]; then
            # zypper does not yet know nothing about systemsmanagement_saltstack
            __zypper addrepo --refresh "${SUSE_PKG_URL}" || return 1
        fi
    fi

    __zypper --gpg-auto-import-keys refresh || return 1

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __zypper --gpg-auto-import-keys update || return 1
    fi

    # Salt needs python-zypp installed in order to use the zypper module
    __PACKAGES="python-zypp"
    # shellcheck disable=SC2089
    __PACKAGES="${__PACKAGES} libzmq5 python python-Jinja2 python-msgpack-python"
    __PACKAGES="${__PACKAGES} python-pycrypto python-pyzmq python-pip python-xml python-requests"

    if [ "$SUSE_PATCHLEVEL" -eq 1 ]; then
        __check_pip_allowed
        echowarn "PyYaml will be installed using pip"
    else
        __PACKAGES="${__PACKAGES} python-PyYAML"
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-apache-libcloud"
    fi

    # SLES 11 SP3 ships with both python-M2Crypto-0.22.* and python-m2crypto-0.21 and we will be asked which
    # we want to install, even with --non-interactive.
    # Let's try to install the higher version first and then the lower one in case of failure
    __zypper_install 'python-M2Crypto>=0.22' || __zypper_install 'python-M2Crypto>=0.21' || return 1
    # shellcheck disable=SC2086,SC2090
    __zypper_install ${__PACKAGES} || return 1

    if [ "$SUSE_PATCHLEVEL" -eq 1 ]; then
        # There's no python-PyYaml in SP1, let's install it using pip
        pip install PyYaml || return 1
    fi

    # PIP based installs need to copy configuration files "by hand".
    if [ "$SUSE_PATCHLEVEL" -eq 1 ]; then
        # Let's trigger config_salt()
        if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
            # Let's set the configuration directory to /tmp
            _TEMP_CONFIG_DIR="/tmp"
            CONFIG_SALT_FUNC="config_salt"

            for fname in minion master syndic api; do

                # Skip if not meant to be installed
                [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
                [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
                [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
                [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

                # Syndic uses the same configuration file as the master
                [ $fname = "syndic" ] && fname=master

                # Let's download, since they were not provided, the default configuration files
                if [ ! -f "$_SALT_ETC_DIR/$fname" ] && [ ! -f "$_TEMP_CONFIG_DIR/$fname" ]; then
                    # shellcheck disable=SC2086
                    curl $_CURL_ARGS -s -o "$_TEMP_CONFIG_DIR/$fname" -L \
                        "https://raw.githubusercontent.com/saltstack/salt/develop/conf/$fname" || return 1
                fi
            done
        fi
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __zypper_install ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_suse_11_git_deps() {
    install_suse_11_stable_deps || return 1

    if ! __check_command_exists git; then
        __zypper_install git  || return 1
    fi

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __zypper_install python-tornado
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_suse_11_stable() {
    if [ "$SUSE_PATCHLEVEL" -gt 1 ]; then
        install_opensuse_stable || return 1
    else
        # USE_SETUPTOOLS=1 To work around
        # error: option --single-version-externally-managed not recognized
        USE_SETUPTOOLS=1 pip install salt || return 1
    fi
    return 0
}

install_suse_11_git() {
    install_opensuse_git || return 1
    return 0
}

install_suse_11_stable_post() {
    if [ "$SUSE_PATCHLEVEL" -gt 1 ]; then
        install_opensuse_stable_post || return 1
    else
        for fname in minion master syndic api; do

            # Skip if not meant to be installed
            [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
            [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
            [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
            [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

            if [ -f /bin/systemctl ]; then
                # shellcheck disable=SC2086
                curl $_CURL_ARGS -L "https://github.com/saltstack/salt/raw/develop/pkg/salt-$fname.service" \
                    -o "/lib/systemd/system/salt-$fname.service" || return 1
                continue
            fi

            # shellcheck disable=SC2086
            curl $_CURL_ARGS -L "https://github.com/saltstack/salt/raw/develop/pkg/rpm/salt-$fname" \
                -o "/etc/init.d/salt-$fname" || return 1
            chmod +x "/etc/init.d/salt-$fname"

        done
    fi
    return 0
}

install_suse_11_git_post() {
    install_opensuse_git_post || return 1
    return 0
}

install_suse_11_restart_daemons() {
    install_opensuse_restart_daemons || return 1
    return 0
}


#
#   End of SUSE Enterprise 11
#
#######################################################################################################################
#
# SUSE Enterprise General Functions
#

# Used for both SLE 11 and 12
install_suse_check_services() {
    if [ ! -f /bin/systemctl ]; then
        # Not running systemd!? Don't check!
        return 0
    fi

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        __check_services_systemd salt-$fname || return 1
    done
    return 0
}

#
# SUSE Enterprise General Functions
#
#######################################################################################################################

#######################################################################################################################
#
#    Gentoo Install Functions.
#
__emerge() {
    if [ "$_GENTOO_USE_BINHOST" -eq $BS_TRUE ]; then
        emerge --autounmask-write --getbinpkg "${@}"; return $?
    fi
    emerge --autounmask-write "${@}"; return $?
}

__gentoo_config_protection() {
    # usually it's a good thing to have config files protected by portage, but
    # in this case this would require to interrupt the bootstrapping script at
    # this point, manually merge the changes using etc-update/dispatch-conf/
    # cfg-update and then restart the bootstrapping script, so instead we allow
    # at this point to modify certain config files directly
    export CONFIG_PROTECT_MASK="${CONFIG_PROTECT_MASK:-} /etc/portage/package.keywords /etc/portage/package.unmask /etc/portage/package.use /etc/portage/package.license"
}

__gentoo_pre_dep() {
    if [ "$_ECHO_DEBUG" -eq $BS_TRUE ]; then
        if __check_command_exists eix; then
            eix-sync
        else
            emerge --sync
        fi
    else
        if __check_command_exists eix; then
            eix-sync -q
        else
            emerge --sync --quiet
        fi
    fi
    if [ ! -d /etc/portage ]; then
        mkdir /etc/portage
    fi
}

__gentoo_post_dep() {
    # ensures dev-lib/crypto++ compiles happily
    __emerge --oneshot 'sys-devel/libtool'
    # the -o option asks it to emerge the deps but not the package.
    __gentoo_config_protection

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
        __emerge -v 'dev-python/pip'
        pip install -U "apache-libcloud>=$_LIBCLOUD_MIN_VERSION"
    fi

    __emerge -vo 'dev-python/requests'
    __emerge -vo 'app-admin/salt'

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __emerge -v ${_EXTRA_PACKAGES} || return 1
    fi
}

install_gentoo_deps() {
    __gentoo_pre_dep || return 1
    __gentoo_post_dep || return 1
}

install_gentoo_git_deps() {
    __gentoo_pre_dep || return 1
    __gentoo_post_dep || return 1
}

install_gentoo_stable() {
    __gentoo_config_protection
    __emerge -v 'app-admin/salt' || return 1
}

install_gentoo_git() {
    __gentoo_config_protection
    __emerge -v '=app-admin/salt-9999' || return 1
}

install_gentoo_post() {
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -d "/run/systemd/system" ]; then
            systemctl enable salt-$fname.service
            systemctl start salt-$fname.service
        else
            rc-update add salt-$fname default
            /etc/init.d/salt-$fname start
        fi
    done
}

install_gentoo_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -d "/run/systemd/system" ]; then
            systemctl stop salt-$fname > /dev/null 2>&1
            systemctl start salt-$fname.service
        else
            /etc/init.d/salt-$fname stop > /dev/null 2>&1
            /etc/init.d/salt-$fname start
        fi
    done
}

install_gentoo_check_services() {
    if [ ! -d "/run/systemd/system" ]; then
        # Not running systemd!? Don't check!
        return 0
    fi

    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        __check_services_systemd salt-$fname || return 1
    done
    return 0
}
#
#   End of Gentoo Install Functions.
#
#######################################################################################################################

#######################################################################################################################
#
#   Default minion configuration function. Matches ANY distribution as long as
#   the -c options is passed.
#
config_salt() {
    # If the configuration directory is not passed, return
    [ "$_TEMP_CONFIG_DIR" = "null" ] && return

    CONFIGURED_ANYTHING=$BS_FALSE

    # Let's create the necessary directories
    [ -d "$_SALT_ETC_DIR" ] || mkdir "$_SALT_ETC_DIR" || return 1
    [ -d "$_PKI_DIR" ] || (mkdir -p "$_PKI_DIR" && chmod 700 "$_PKI_DIR") || return 1

    # Copy the grains file if found
    if [ -f "$_TEMP_CONFIG_DIR/grains" ]; then
        echodebug "Moving provided grains file from $_TEMP_CONFIG_DIR/grains to $_SALT_ETC_DIR/grains"
        __movefile "$_TEMP_CONFIG_DIR/grains" "$_SALT_ETC_DIR/grains" || return 1
        CONFIGURED_ANYTHING=$BS_TRUE
    fi

    if [ "$_CONFIG_ONLY" -eq "$BS_TRUE" ]; then
        echowarn "Passing -C (config only) option implies -F (forced overwrite)."
        echowarn "Overwriting configs in 11 seconds!"
        sleep 11
    fi

    if [ "$_INSTALL_MINION" -eq "$BS_TRUE" ] || [ "$_CONFIG_ONLY" -eq "$BS_TRUE" ]; then
        # Create the PKI directory
        [ -d "$_PKI_DIR/minion" ] || (mkdir -p "$_PKI_DIR/minion" && chmod 700 "$_PKI_DIR/minion") || return 1

        # Copy the minions configuration if found
        if [ -f "$_TEMP_CONFIG_DIR/minion" ]; then
            __movefile "$_TEMP_CONFIG_DIR/minion" "$_SALT_ETC_DIR" "$_CONFIG_ONLY" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi

        # Copy the minion's keys if found
        if [ -f "$_TEMP_CONFIG_DIR/minion.pem" ]; then
            __movefile "$_TEMP_CONFIG_DIR/minion.pem" "$_PKI_DIR/minion/" "$_CONFIG_ONLY" || return 1
            chmod 400 "$_PKI_DIR/minion/minion.pem" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
        if [ -f "$_TEMP_CONFIG_DIR/minion.pub" ]; then
            __movefile "$_TEMP_CONFIG_DIR/minion.pub" "$_PKI_DIR/minion/" "$_CONFIG_ONLY" || return 1
            chmod 664 "$_PKI_DIR/minion/minion.pub" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
        # For multi-master-pki, copy the master_sign public key if found
        if [ -f "$_TEMP_CONFIG_DIR/master_sign.pub" ]; then
            __movefile "$_TEMP_CONFIG_DIR/master_sign.pub" "$_PKI_DIR/minion/" || return 1
            chmod 664 "$_PKI_DIR/minion/master_sign.pub" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
    fi

    # only (re)place master or syndic configs if -M (install master) or -S
    # (install syndic) specified
    OVERWRITE_MASTER_CONFIGS=$BS_FALSE
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ] && [ "$_CONFIG_ONLY" -eq $BS_TRUE ]; then
        OVERWRITE_MASTER_CONFIGS=$BS_TRUE
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ] && [ "$_CONFIG_ONLY" -eq $BS_TRUE ]; then
        OVERWRITE_MASTER_CONFIGS=$BS_TRUE
    fi

    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ] || [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ] || [ "$OVERWRITE_MASTER_CONFIGS" -eq $BS_TRUE ]; then
        # Create the PKI directory
        [ -d "$_PKI_DIR/master" ] || (mkdir -p "$_PKI_DIR/master" && chmod 700 "$_PKI_DIR/master") || return 1

        # Copy the masters configuration if found
        if [ -f "$_TEMP_CONFIG_DIR/master" ]; then
            __movefile "$_TEMP_CONFIG_DIR/master" "$_SALT_ETC_DIR" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi

        # Copy the master's keys if found
        if [ -f "$_TEMP_CONFIG_DIR/master.pem" ]; then
            __movefile "$_TEMP_CONFIG_DIR/master.pem" "$_PKI_DIR/master/" || return 1
            chmod 400 "$_PKI_DIR/master/master.pem" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
        if [ -f "$_TEMP_CONFIG_DIR/master.pub" ]; then
            __movefile "$_TEMP_CONFIG_DIR/master.pub" "$_PKI_DIR/master/" || return 1
            chmod 664 "$_PKI_DIR/master/master.pub" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
    fi

    if [ "$_CONFIG_ONLY" -eq $BS_TRUE ] && [ $CONFIGURED_ANYTHING -eq $BS_FALSE ]; then
        echowarn "No configuration or keys were copied over. No configuration was done!"
        exit 0
    fi
    return 0
}
#
#  Ended Default Configuration function
#
#######################################################################################################################

#######################################################################################################################
#
#   Default salt master minion keys pre-seed function. Matches ANY distribution
#   as long as the -k option is passed.
#
preseed_master() {
    # Create the PKI directory

    if [ "$(find "$_TEMP_KEYS_DIR" -maxdepth 1 -type f | wc -l)" -lt 1 ]; then
        echoerror "No minion keys were uploaded. Unable to pre-seed master"
        return 1
    fi

    SEED_DEST="$_PKI_DIR/master/minions"
    [ -d "$SEED_DEST" ] || (mkdir -p "$SEED_DEST" && chmod 700 "$SEED_DEST") || return 1

    for keyfile in $_TEMP_KEYS_DIR/*; do
        keyfile=$(basename "${keyfile}")
        src_keyfile="${_TEMP_KEYS_DIR}/${keyfile}"
        dst_keyfile="${SEED_DEST}/${keyfile}"

        # If it's not a file, skip to the next
        [ ! -f "$src_keyfile" ] && continue

        __movefile "$src_keyfile" "$dst_keyfile" || return 1
        chmod 664 "$dst_keyfile" || return 1
    done

    return 0
}
#
#  Ended Default Salt Master Pre-Seed minion keys function
#
#######################################################################################################################

#######################################################################################################################
#
#   This function checks if all of the installed daemons are running or not.
#
daemons_running() {
    [ "$_START_DAEMONS" -eq $BS_FALSE ] && return

    FAILED_DAEMONS=0
    for fname in minion master syndic api; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        # shellcheck disable=SC2009
        if [ "${DISTRO_NAME}" = "SmartOS" ]; then
            if [ "$(svcs -Ho STA salt-$fname)" != "ON" ]; then
                echoerror "salt-$fname was not found running"
                FAILED_DAEMONS=$((FAILED_DAEMONS + 1))
            fi
        elif [ "$(ps wwwaux | grep -v grep | grep salt-$fname)" = "" ]; then
            echoerror "salt-$fname was not found running"
            FAILED_DAEMONS=$((FAILED_DAEMONS + 1))
        fi
    done
    return $FAILED_DAEMONS
}
#
#  Ended daemons running check function
#
#######################################################################################################################

#======================================================================================================================
# LET'S PROCEED WITH OUR INSTALLATION
#======================================================================================================================
# Let's get the dependencies install function

if [ "$_NO_DEPS" -eq $BS_FALSE ]; then
    DEP_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}_deps"
elif [ "${ITYPE}" = "git" ]; then
    DEP_FUNC_NAMES="__git_clone_and_checkout"
else
    DEP_FUNC_NAMES=""
fi

DEPS_INSTALL_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$DEP_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        DEPS_INSTALL_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "DEPS_INSTALL_FUNC=${DEPS_INSTALL_FUNC}"

# Let's get the minion config function
CONFIG_SALT_FUNC="null"
if [ "$_TEMP_CONFIG_DIR" != "null" ]; then

    CONFIG_FUNC_NAMES="config_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_salt"
    CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_salt"
    CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_salt"
    CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_salt"
    CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}_${ITYPE}_salt"
    CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}_salt"
    CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_salt"

    for FUNC_NAME in $(__strip_duplicates "$CONFIG_FUNC_NAMES"); do
        if __function_defined "$FUNC_NAME"; then
            CONFIG_SALT_FUNC="$FUNC_NAME"
            break
        fi
    done
fi
echodebug "CONFIG_SALT_FUNC=${CONFIG_SALT_FUNC}"

# Let's get the pre-seed master function
PRESEED_MASTER_FUNC="null"
if [ "$_TEMP_KEYS_DIR" != "null" ]; then

    PRESEED_FUNC_NAMES="preseed_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_master"
    PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_master"
    PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_master"
    PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_master"
    PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}_${ITYPE}_master"
    PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}_master"
    PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_master"

    for FUNC_NAME in $(__strip_duplicates "$PRESEED_FUNC_NAMES"); do
        if __function_defined "$FUNC_NAME"; then
            PRESEED_MASTER_FUNC="$FUNC_NAME"
            break
        fi
    done
fi
echodebug "PRESEED_MASTER_FUNC=${PRESEED_MASTER_FUNC}"

# Let's get the install function
INSTALL_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}"
INSTALL_FUNC_NAMES="$INSTALL_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}"
INSTALL_FUNC_NAMES="$INSTALL_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}"

INSTALL_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$INSTALL_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        INSTALL_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "INSTALL_FUNC=${INSTALL_FUNC}"

# Let's get the post install function
POST_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}_post"

POST_INSTALL_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$POST_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        POST_INSTALL_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "POST_INSTALL_FUNC=${POST_INSTALL_FUNC}"


# Let's get the start daemons install function
STARTDAEMONS_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}_restart_daemons"

STARTDAEMONS_INSTALL_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$STARTDAEMONS_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        STARTDAEMONS_INSTALL_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "STARTDAEMONS_INSTALL_FUNC=${STARTDAEMONS_INSTALL_FUNC}"


# Let's get the daemons running check function.
DAEMONS_RUNNING_FUNC="null"
DAEMONS_RUNNING_FUNC_NAMES="daemons_running_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}_${ITYPE}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running"

for FUNC_NAME in $(__strip_duplicates "$DAEMONS_RUNNING_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        DAEMONS_RUNNING_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "DAEMONS_RUNNING_FUNC=${DAEMONS_RUNNING_FUNC}"

# Let's get the check services function
if [ ${_DISABLE_SALT_CHECKS} -eq $BS_FALSE ]; then
    CHECK_SERVICES_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}_check_services"
else
    CHECK_SERVICES_FUNC_NAMES=False
    echowarn "DISABLE_SALT_CHECKS set, not setting \$CHECK_SERVICES_FUNC_NAMES"
fi

CHECK_SERVICES_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$CHECK_SERVICES_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        CHECK_SERVICES_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "CHECK_SERVICES_FUNC=${CHECK_SERVICES_FUNC}"


if [ "$DEPS_INSTALL_FUNC" = "null" ]; then
    echoerror "No dependencies installation function found. Exiting..."
    exit 1
fi

if [ "$INSTALL_FUNC" = "null" ]; then
    echoerror "No installation function found. Exiting..."
    exit 1
fi


# Install dependencies
if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    # Only execute function is not in config mode only
    echoinfo "Running ${DEPS_INSTALL_FUNC}()"
    $DEPS_INSTALL_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${DEPS_INSTALL_FUNC}()!!!"
        exit 1
    fi
fi


# Configure Salt
if [ "$_TEMP_CONFIG_DIR" != "null" ] && [ "$CONFIG_SALT_FUNC" != "null" ]; then
    echoinfo "Running ${CONFIG_SALT_FUNC}()"
    $CONFIG_SALT_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${CONFIG_SALT_FUNC}()!!!"
        exit 1
    fi
fi


# Pre-Seed master keys
if [ "$_TEMP_KEYS_DIR" != "null" ] && [ "$PRESEED_MASTER_FUNC" != "null" ]; then
    echoinfo "Running ${PRESEED_MASTER_FUNC}()"
    $PRESEED_MASTER_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${PRESEED_MASTER_FUNC}()!!!"
        exit 1
    fi
fi


# Install Salt
if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    # Only execute function is not in config mode only
    echoinfo "Running ${INSTALL_FUNC}()"
    $INSTALL_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${INSTALL_FUNC}()!!!"
        exit 1
    fi
fi

# Ensure that the cachedir exists
# (Workaround for https://github.com/saltstack/salt/issues/6502)
if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
    if [ ! -d "${_SALT_CACHE_DIR}/minion/proc" ]; then
        echodebug "Creating salt's cachedir"
        mkdir -p "${_SALT_CACHE_DIR}/minion/proc"
    fi
fi

# Drop the master address if passed
if [ "$_SALT_MASTER_ADDRESS" != "null" ]; then
    [ ! -d "$_SALT_ETC_DIR/minion.d" ] && mkdir -p "$_SALT_ETC_DIR/minion.d"
    cat <<_eof > $_SALT_ETC_DIR/minion.d/99-master-address.conf
master: $_SALT_MASTER_ADDRESS
_eof
fi

# Drop the minion id if passed
if [ "$_SALT_MINION_ID" != "null" ]; then
    [ ! -d "$_SALT_ETC_DIR" ] && mkdir -p "$_SALT_ETC_DIR"
    echo "$_SALT_MINION_ID" > "$_SALT_ETC_DIR/minion_id"
fi

# Run any post install function. Only execute function if not in config mode only
if [ "$_CONFIG_ONLY" -eq $BS_FALSE ] && [ "$POST_INSTALL_FUNC" != "null" ]; then
    echoinfo "Running ${POST_INSTALL_FUNC}()"
    $POST_INSTALL_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${POST_INSTALL_FUNC}()!!!"
        exit 1
    fi
fi

# Run any check services function, Only execute function if not in config mode only
if [ "$_CONFIG_ONLY" -eq $BS_FALSE ] && [ "$CHECK_SERVICES_FUNC" != "null" ]; then
    echoinfo "Running ${CHECK_SERVICES_FUNC}()"
    $CHECK_SERVICES_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${CHECK_SERVICES_FUNC}()!!!"
        exit 1
    fi
fi


# Run any start daemons function
if [ "$STARTDAEMONS_INSTALL_FUNC" != "null" ]; then
    echoinfo "Running ${STARTDAEMONS_INSTALL_FUNC}()"
    echodebug "Waiting ${_SLEEP} seconds for processes to settle before checking for them"
    sleep ${_SLEEP}
    $STARTDAEMONS_INSTALL_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${STARTDAEMONS_INSTALL_FUNC}()!!!"
        exit 1
    fi
fi

# Check if the installed daemons are running or not
if [ "$DAEMONS_RUNNING_FUNC" != "null" ] && [ $_START_DAEMONS -eq $BS_TRUE ]; then
    echoinfo "Running ${DAEMONS_RUNNING_FUNC}()"
    echodebug "Waiting ${_SLEEP} seconds for processes to settle before checking for them"
    sleep ${_SLEEP}  # Sleep a little bit to let daemons start
    $DAEMONS_RUNNING_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${DAEMONS_RUNNING_FUNC}()!!!"

        for fname in minion master syndic api; do
            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            # Skip if not meant to be installed
            [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
            [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
            #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
            [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

            if [ "$_ECHO_DEBUG" -eq $BS_FALSE ]; then
                echoerror "salt-$fname was not found running. Pass '-D' to $__ScriptName when bootstrapping for additional debugging information..."
                continue
            fi


            [ ! -f "$_SALT_ETC_DIR/$fname" ] && [ $fname != "syndic" ] && echodebug "$_SALT_ETC_DIR/$fname does not exist"

            echodebug "Running salt-$fname by hand outputs: $(nohup salt-$fname -l debug)"

            [ ! -f /var/log/salt/$fname ] && echodebug "/var/log/salt/$fname does not exist. Can't cat its contents!" && continue

            echodebug "DAEMON LOGS for $fname:"
            echodebug "$(cat /var/log/salt/$fname)"
            echo
        done

        echodebug "Running Processes:"
        echodebug "$(ps auxwww)"

        exit 1
    fi
fi


# Done!
if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    echoinfo "Salt installed!"
else
    echoinfo "Salt configured"
fi
exit 0
