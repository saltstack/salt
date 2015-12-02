#!/bin/sh -
#======================================================================================================================
# vim: softtabstop=4 shiftwidth=4 expandtab fenc=utf-8 spell spelllang=en cc=120
#======================================================================================================================
#
#          FILE: bootstrap-salt.sh
#
#   DESCRIPTION: Bootstrap salt installation for various systems/distributions
#
#          BUGS: https://github.com/saltstack/salt-bootstrap/issues
#
#     COPYRIGHT: (c) 2012-2015 by the SaltStack Team, see AUTHORS.rst for more
#                details.
#
#       LICENSE: Apache 2.0
#  ORGANIZATION: SaltStack (saltstack.com)
#       CREATED: 10/15/2012 09:49:37 PM WEST
#======================================================================================================================
set -o nounset                              # Treat unset variables as an error
__ScriptVersion="2015.11.09"
__ScriptName="bootstrap-salt.sh"

#======================================================================================================================
#  Environment variables taken into account.
#----------------------------------------------------------------------------------------------------------------------
#   * BS_COLORS:                If 0 disables colour support
#   * BS_PIP_ALLOWED:           If 1 enable pip based installations(if needed)
#   * BS_ECHO_DEBUG:            If 1 enable debug echo which can also be set by -D
#   * BS_SALT_ETC_DIR:          Defaults to /etc/salt (Only tweak'able on git based installations)
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
__DEFAULT_SLEEP_ORIGINAL="${__DEFAULT_SLEEP}"

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
#          NAME:  check_pip_allowed
#   DESCRIPTION:  Simple function to let the users know that -P needs to be
#                 used.
#----------------------------------------------------------------------------------------------------------------------
check_pip_allowed() {
    if [ $# -eq 1 ]; then
        _PIP_ALLOWED_ERROR_MSG=$1
    else
        _PIP_ALLOWED_ERROR_MSG="pip based installations were not allowed. Retry using '-P'"
    fi

    if [ "$_PIP_ALLOWED" -eq $BS_FALSE ]; then
        echoerror "$_PIP_ALLOWED_ERROR_MSG"
        usage
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
_TEMP_KEYS_DIR="null"
_INSTALL_MASTER=$BS_FALSE
_INSTALL_SYNDIC=$BS_FALSE
_INSTALL_MINION=$BS_TRUE
_INSTALL_CLOUD=$BS_FALSE
_START_DAEMONS=$BS_TRUE
_ECHO_DEBUG=${BS_ECHO_DEBUG:-$BS_FALSE}
_CONFIG_ONLY=$BS_FALSE
_PIP_ALLOWED=${BS_PIP_ALLOWED:-$BS_FALSE}
_SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/etc/salt}
_PKI_DIR=${_SALT_ETC_DIR}/pki
_FORCE_OVERWRITE=${BS_FORCE_OVERWRITE:-$BS_FALSE}
_GENTOO_USE_BINHOST=${BS_GENTOO_USE_BINHOST:-$BS_FALSE}
_EPEL_REPO=${BS_EPEL_REPO:-epel}
__EPEL_REPOS_INSTALLED=${BS_FALSE}
_UPGRADE_SYS=${BS_UPGRADE_SYS:-$BS_FALSE}
_INSECURE_DL=${BS_INSECURE_DL:-$BS_FALSE}
_WGET_ARGS=${BS_WGET_ARGS:-}
_CURL_ARGS=${BS_CURL_ARGS:-}
_FETCH_ARGS=${BS_FETCH_ARGS:-}
_ENABLE_EXTERNAL_ZMQ_REPOS=${BS_ENABLE_EXTERNAL_ZMQ_REPOS:-$BS_FALSE}
_SALT_MASTER_ADDRESS=${BS_SALT_MASTER_ADDRESS:-null}
_SALT_MINION_ID="null"
# __SIMPLIFY_VERSION is mostly used in Solaris based distributions
__SIMPLIFY_VERSION=$BS_TRUE
_LIBCLOUD_MIN_VERSION="0.14.0"
_PY_REQUESTS_MIN_VERSION="2.0"
_EXTRA_PACKAGES=""
_HTTP_PROXY=""
_DISABLE_SALT_CHECKS=$BS_FALSE
__SALT_GIT_CHECKOUT_DIR=${BS_SALT_GIT_CHECKOUT_DIR:-/tmp/git/salt}
_NO_DEPS=$BS_FALSE


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  usage
#  DESCRIPTION:  Display usage information.
#----------------------------------------------------------------------------------------------------------------------
usage() {
    cat << EOT

  Usage :  ${__ScriptName} [options] <install-type> <install-type-args>

  Installation types:
    - stable (default)
    - stable [version] (ubuntu specific)
    - daily  (ubuntu specific)
    - testing (redhat specific)
    - git

  Examples:
    - ${__ScriptName}
    - ${__ScriptName} stable
    - ${__ScriptName} stable 2014.7
    - ${__ScriptName} daily
    - ${__ScriptName} testing
    - ${__ScriptName} git
    - ${__ScriptName} git develop
    - ${__ScriptName} git v0.17.0
    - ${__ScriptName} git 8c3fadf15ec183e5ce8c63739850d543617e4357

  Options:
  -h  Display this message
  -v  Display script version
  -n  No colours.
  -D  Show debug output.
  -c  Temporary configuration directory
  -g  Salt repository URL. (default: git://github.com/saltstack/salt.git)
  -G  Instead of cloning from git://github.com/saltstack/salt.git, clone from https://github.com/saltstack/salt.git (Usually necessary on systems which have the regular git protocol port blocked, where https usually is not)
  -k  Temporary directory holding the minion keys which will pre-seed
      the master.
  -s  Sleep time used when waiting for daemons to start, restart and when checking
      for the services running. Default: ${__DEFAULT_SLEEP}
  -M  Also install salt-master
  -S  Also install salt-syndic
  -N  Do not install salt-minion
  -X  Do not start daemons after installation
  -C  Only run the configuration function. This option automatically
      bypasses any installation.
  -P  Allow pip based installations. On some distributions the required salt
      packages or its dependencies are not available as a package for that
      distribution. Using this flag allows the script to use pip as a last
      resort method. NOTE: This only works for functions which actually
      implement pip based installations.
  -F  Allow copied files to overwrite existing(config, init.d, etc)
  -U  If set, fully upgrade the system prior to bootstrapping salt
  -K  If set, keep the temporary files in the temporary directories specified
      with -c and -k.
  -I  If set, allow insecure connections while downloading any files. For
      example, pass '--no-check-certificate' to 'wget' or '--insecure' to 'curl'
  -A  Pass the salt-master DNS name or IP. This will be stored under
      \${BS_SALT_ETC_DIR}/minion.d/99-master-address.conf
  -i  Pass the salt-minion id. This will be stored under
      \${BS_SALT_ETC_DIR}/minion_id
  -L  Install the Apache Libcloud package if possible(required for salt-cloud)
  -p  Extra-package to install while installing salt dependencies. One package
      per -p flag. You're responsible for providing the proper package name.
  -d  Disable check_service functions. Setting this flag disables the
      'install_<distro>_check_services' checks. You can also do this by
      touching /tmp/disable_salt_checks on the target host. Defaults \${BS_FALSE}
  -H  Use the specified http proxy for the installation
  -Z  Enable external software source for newer ZeroMQ(Only available for RHEL/CentOS/Fedora/Ubuntu based distributions)
  -b  Assume that dependencies are already installed and software sources are set up.
      If git is selected, git tree is still checked out as dependency step.

EOT
}   # ----------  end of function usage  ----------


while getopts ":hvnDc:Gg:k:MSNXCPFUKIA:i:Lp:dH:Zb" opt
do
  case "${opt}" in

    h )  usage; exit 0                                  ;;

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
    g ) _SALT_REPO_URL=$OPTARG                          ;;
    G ) if [ "${_SALT_REPO_URL}" = "${_SALTSTACK_REPO_URL}" ]; then
            _SALTSTACK_REPO_URL="https://github.com/saltstack/salt.git"
            _SALT_REPO_URL=${_SALTSTACK_REPO_URL}
        else
            _SALTSTACK_REPO_URL="https://github.com/saltstack/salt.git"
        fi
         ;;
    k )  _TEMP_KEYS_DIR="$OPTARG"
         # If the configuration directory does not exist, error out
         if [ ! -d "$_TEMP_KEYS_DIR" ]; then
             echoerror "The pre-seed keys directory ${_TEMP_KEYS_DIR} does not exist."
             exit 1
         fi
         ;;
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


    \?)  echo
         echoerror "Option does not exist : $OPTARG"
         usage
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
        usage
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

if [ "$_CONFIG_ONLY" -eq $BS_TRUE ] && [ "$_TEMP_CONFIG_DIR" = "null" ]; then
    echoerror "In order to run the script in configuration only mode you also need to provide the configuration directory."
    exit 1
fi

# Check that we're installing a minion if we're being passed a master address
if [ "$_INSTALL_MINION" -eq $BS_FALSE ] && [ "$_SALT_MASTER_ADDRESS" != "null" ]; then
    echoerror "Don't pass a master address (-A) if no minion is going to be bootstrapped."
    exit 1
fi

# Check that we're installing a minion if we're being passed a master address
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
        if [ "$(echo "$1" | egrep '^(latest|1\.6|1\.7|2014\.1|2014\.7|2015\.5|2015\.8)$')" = "" ]; then
          echo "Unknown stable version: $1 (valid: 1.6, 1.7, 2014.1, 2014.7, 2015.5, 2015.8, latest)"
          exit 1
        else
          STABLE_REV="$1"
          shift
        fi
    fi
fi

# Check for any unparsed arguments. Should be an error.
if [ "$#" -gt 0 ]; then
    __check_unparsed_options "$*"
    usage
    echo
    echoerror "Too many arguments."
    exit 1
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

    if [ "$ITYPE" = "git" ] && [ -d "${__SALT_GIT_CHECKOUT_DIR}" ]; then
        if [ $_KEEP_TEMP_FILES -eq $BS_FALSE ]; then
            # Clean up the checked out repository
            echodebug "Cleaning up the Salt Temporary Git Repository"
            cd "${__SALT_GIT_CHECKOUT_PARENT_DIR}"
            rm -rf "${__SALT_GIT_CHECKOUT_DIR}"
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
    trap "__trap_errors" INT QUIT ABRT KILL QUIT TERM

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
    curl $_CURL_ARGS -s -o "$1" "$2" >/dev/null 2>&1 ||
        wget $_WGET_ARGS -q -O "$1" "$2" >/dev/null 2>&1 ||
            fetch $_FETCH_ARGS -q -o "$1" "$2" >/dev/null 2>&1 ||
                fetch -q -o "$1" "$2" >/dev/null 2>&1           # Pre FreeBSD 10
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
                        # Amazon AMI's after 2014.9 match here
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
        DISTRO_VERSION=$(/sbin/uname -X | awk '/[kK][eE][rR][nN][eE][lL][iI][dD]/ { print $3}')
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
                    __SIMPLIFY_VERSION=$BS_FALSE
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
if [ "${DISTRO_VERSION}" = "" ] || [ $__SIMPLIFY_VERSION -eq $BS_FALSE ]; then
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
elif ([ "${DISTRO_NAME_L}" != "ubuntu" ] && [ "$ITYPE" = "stable" ] && [ "$STABLE_REV" != "latest" ]); then
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

    __SALT_GIT_CHECKOUT_PARENT_DIR=$(dirname "${__SALT_GIT_CHECKOUT_DIR}" 2>/dev/null)
    __SALT_GIT_CHECKOUT_PARENT_DIR="${__SALT_GIT_CHECKOUT_PARENT_DIR:-/tmp/git}"
    __SALT_CHECKOUT_REPONAME="$(basename "${__SALT_GIT_CHECKOUT_DIR}" 2>/dev/null)"
    __SALT_CHECKOUT_REPONAME="${__SALT_CHECKOUT_REPONAME:-salt}"
    [ -d "${__SALT_GIT_CHECKOUT_PARENT_DIR}" ] || mkdir "${__SALT_GIT_CHECKOUT_PARENT_DIR}"
    cd "${__SALT_GIT_CHECKOUT_PARENT_DIR}"
    if [ -d "${__SALT_GIT_CHECKOUT_DIR}" ]; then
        echodebug "Found a checked out Salt repository"
        cd "${__SALT_GIT_CHECKOUT_DIR}"
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
        __SHALLOW_CLONE="${BS_FALSE}"
        if [ "$(echo "$GIT_REV" | sed 's/^.*\(v[[:digit:]]\{1,4\}\.[[:digit:]]\{1,2\}\)\(\.[[:digit:]]\{1,2\}\)\?.*$/MATCH/')" = "MATCH" ]; then
            echoinfo "Git revision matches a Salt version tag"
            # Let's try shallow cloning to speed up.
            # Test for "--single-branch" option introduced in git 1.7.10, the minimal version of git where the shallow
            # cloning we need actually works
            if [ "$(git clone --help | grep 'single-branch')" != "" ]; then
                # The "--single-branch" option is supported, attempt shallow cloning
                echoinfo "Attempting to shallow clone $GIT_REV from Salt's repository ${_SALT_REPO_URL}"
                git clone --depth 1 --branch "$GIT_REV" "$_SALT_REPO_URL" "$__SALT_CHECKOUT_REPONAME"
                if [ $? -eq 0 ]; then
                    cd "${__SALT_GIT_CHECKOUT_DIR}"
                    __SHALLOW_CLONE="${BS_TRUE}"
                else
                    # Shallow clone above failed(missing upstream tags???), let's resume the old behaviour.
                    echowarn "Failed to shallow clone."
                    echoinfo "Resuming regular git clone and remote SaltStack repository addition procedure"
                    git clone "$_SALT_REPO_URL" "$__SALT_CHECKOUT_REPONAME" || return 1
                    cd "${__SALT_GIT_CHECKOUT_DIR}"
                fi
            else
                echodebug "Shallow cloning not possible. Required git version not met."
                git clone "$_SALT_REPO_URL" "$__SALT_CHECKOUT_REPONAME" || return 1
                cd "${__SALT_GIT_CHECKOUT_DIR}"
            fi
        else
            echowarn "The git revision being installed does not match a Salt version tag. Shallow cloning disabled"
            git clone "$_SALT_REPO_URL" "$__SALT_CHECKOUT_REPONAME" || return 1
            cd "${__SALT_GIT_CHECKOUT_DIR}"
        fi

        if [ "$(echo "$_SALT_REPO_URL" | grep -c -e '\(\(git\|https\)://github\.com/\|git@github\.com:\)saltstack/salt\.git')" -eq 0 ]; then
            # We need to add the saltstack repository as a remote and fetch tags for proper versioning
            echoinfo "Adding SaltStack's Salt repository as a remote"
            git remote add upstream "$_SALTSTACK_REPO_URL" || return 1
            echodebug "Fetching upstream(SaltStack's Salt repository) git tags"
            git fetch --tags upstream || return 1
        fi

        if [ "$__SHALLOW_CLONE" -eq "${BS_FALSE}" ]; then
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
#          NAME:  copyfile
#   DESCRIPTION:  Simple function to copy files. Overrides if asked.
#----------------------------------------------------------------------------------------------------------------------
copyfile() {
    overwrite=$_FORCE_OVERWRITE
    if [ $# -eq 2 ]; then
        sfile=$1
        dfile=$2
    elif [ $# -eq 3 ]; then
        sfile=$1
        dfile=$2
        overwrite=$3
    else
        echoerror "Wrong number of arguments for copyfile()"
        echoinfo "USAGE: copyfile <source> <dest>  OR  copyfile <source> <dest> <overwrite>"
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
#          NAME:  movefile
#   DESCRIPTION:  Simple function to move files. Overrides if asked.
#----------------------------------------------------------------------------------------------------------------------
movefile() {
    overwrite=$_FORCE_OVERWRITE
    if [ $# -eq 2 ]; then
        sfile=$1
        dfile=$2
    elif [ $# -eq 3 ]; then
        sfile=$1
        dfile=$2
        overwrite=$3
    else
        echoerror "Wrong number of arguments for movefile()"
        echoinfo "USAGE: movefile <source> <dest>  OR  movefile <source> <dest> <overwrite>"
        exit 1
    fi

    if [ $_KEEP_TEMP_FILES -eq $BS_TRUE ]; then
        # We're being told not to move files, instead copy them so we can keep
        # them around
        echodebug "Since BS_KEEP_TEMP_FILES=1 we're copying files instead of moving them"
        copyfile "$sfile" "$dfile" "$overwrite"
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
        # The destination file does not exist, copy
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
    fi

    add-apt-repository -y "deb http://old-releases.ubuntu.com/ubuntu $(lsb_release -sc) universe" || return 1

    return 0
}

install_ubuntu_deps() {
    if ([ "${__DEFAULT_SLEEP}" -eq "${__DEFAULT_SLEEP_ORIGINAL}" ] && [ "$DISTRO_MAJOR_VERSION" -lt 15 ]); then
        # The user did not pass a custom sleep value as an argument, let's increase the default value
        echodebug "On Ubuntu systems we increase the default sleep value to 10."
        echodebug "See https://github.com/saltstack/salt/issues/12248 for more info."
        __DEFAULT_SLEEP=10
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

    __enable_universe_repository || return 1

    # the latest version of 2015.5 and all versions of 2015.8 and beyond are hosted on repo.saltstack.com
    if [ "$(echo "$STABLE_REV" | egrep '^(2015\.5|2015\.8|latest)$')" = "" ]; then
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

    __PIP_PACKAGES=""

    # Minimal systems might not have upstart installed, install it
    __PACKAGES="upstart"

    # Need python-apt for managing packages via Salt
    __PACKAGES="${__PACKAGES} python-apt"

    # requests is still used by many salt modules
    __PACKAGES="${__PACKAGES} python-requests"

    # Additionally install procps and pciutils which allows for Docker boostraps. See 366#issuecomment-39666813
    __PACKAGES="${__PACKAGES} procps pciutils"


    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        check_pip_allowed "You need to allow pip based installations (-P) in order to install 'apache-libcloud'"
        if [ "$(which pip)" = "" ]; then
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
        pip install -U ${__PIP_PACKAGES}
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
    install_ubuntu_deps || return 1

    # the latest version of 2015.5 and all versions of 2015.8 and beyond are hosted on repo.saltstack.com
    if [ "$(echo "$STABLE_REV" | egrep '^(2015\.5|2015\.8|latest)$')" != "" ]; then

        # Saltstack's Stable Ubuntu repository
        if [ "$(grep -ER 'latest .+ main' /etc/apt)" = "" ]; then
            echo "deb http://repo.saltstack.com/apt/ubuntu/ubuntu$DISTRO_MAJOR_VERSION/$STABLE_REV $DISTRO_CODENAME main" >> \
                /etc/apt/sources.list.d/saltstack.list
        fi


        # Make sure wget is available
        __apt_get_install_noinput wget

        # shellcheck disable=SC2086
        wget $_WGET_ARGS -q http://repo.saltstack.com/apt/ubuntu/ubuntu$DISTRO_MAJOR_VERSION/$STABLE_REV/SALTSTACK-GPG-KEY.pub -O - | apt-key add - || return 1

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

    __enable_universe_repository || return 1

    # for anything up to and including 11.04 do not use the -y option
    if [ "$DISTRO_MAJOR_VERSION" -gt 11 ] || ([ "$DISTRO_MAJOR_VERSION" -eq 11 ] && [ "$DISTRO_MINOR_VERSION" -gt 04 ]); then
        # Above Ubuntu 11.04 add a -y flag
        add-apt-repository -y ppa:saltstack/salt-daily || return 1
    else
        add-apt-repository ppa:saltstack/salt-daily || return 1
    fi

    apt-get update

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    return 0
}

install_ubuntu_git_deps() {
    install_ubuntu_deps || return 1
    __apt_get_install_noinput git-core python-yaml python-m2crypto python-crypto \
        msgpack-python python-zmq python-jinja2 || return 1

    __git_clone_and_checkout || return 1

    __PACKAGES=""
    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __PACKAGES="${__PACKAGES} python-dev"
            check_pip_allowed "You need to allow pip based installations (-P) in order to install the python package '${__REQUIRED_TORNADO}'"
            if [ "$(which pip)" = "" ]; then
                __PACKAGES="${__PACKAGES} python-setuptools python-pip"
            fi
            # shellcheck disable=SC2086
            __apt_get_install_noinput $__PACKAGES
            pip install -U "${__REQUIRED_TORNADO}"
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
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
    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python setup.py install --install-layout=deb --salt-config-dir="$_SALT_ETC_DIR" || \
            python setup.py --salt-config-dir="$_SALT_ETC_DIR" install --install-layout=deb || return 1
    else
        python setup.py install --install-layout=deb || return 1
    fi
    return 0
}

install_ubuntu_git_post() {
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ] && [ "$DISTRO_MAJOR_VERSION" -ge 15 ]; then
            copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"

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
                echodebug "Copying ${__SALT_GIT_CHECKOUT_DIR}/pkg/salt-$fname.upstart to $_upstart_conf"
                copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.upstart" $_upstart_conf
                /sbin/initctl reload-configuration || return 1
            fi
        # No upstart support in Ubuntu!?
        elif [ -f "${__SALT_GIT_CHECKOUT_DIR}/debian/salt-${fname}.init" ]; then
            echodebug "There's NO upstart support!?"
            echodebug "Copying ${__SALT_GIT_CHECKOUT_DIR}/debian/salt-${fname}.init to /etc/init.d/salt-$fname"
            copyfile "${__SALT_GIT_CHECKOUT_DIR}/debian/salt-${fname}.init" "/etc/init.d/salt-$fname"
            chmod +x /etc/init.d/salt-$fname

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            update-rc.d salt-$fname defaults
        else
            echoerror "Neither upstart not init.d was setup for salt-$fname"
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        check_pip_allowed "You need to allow pip based installations (-P) in order to install the python 'requests' package"
        # Additionally install procps and pciutils which allows for Docker boostraps. See 366#issuecomment-39666813
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
    wget $_WGET_ARGS -q http://debian.saltstack.com/debian-salt-team-joehealy.gpg.key -O - | apt-key add - || return 1

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

        # Saltstack's Unstable Debian repository
        if [ "$(grep -R 'debian.saltstack.com' /etc/apt)" = "" ]; then
            echo "deb http://debian.saltstack.com/debian unstable main" >> \
                /etc/apt/sources.list.d/saltstack.list
        fi
        return 0
    fi

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

    # Python requests is available through Squeeze backports
    # Additionally install procps and pciutils which allows for Docker boostraps. See 366#issuecomment-39666813
    __apt_get_install_noinput python-pip procps pciutils python-requests

    # Need python-apt for managing packages via Salt
    __apt_get_install_noinput python-apt

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud/requests"
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

    # shellcheck disable=SC2086
    wget $_WGET_ARGS -q http://debian.saltstack.com/debian-salt-team-joehealy.gpg.key -O - | apt-key add - || return 1

    apt-get update || return 1
    __apt_get_install_noinput -t wheezy-backports libzmq3 libzmq3-dev python-zmq python-apt || return 1
    # Additionally install procps and pciutils which allows for Docker boostraps. See 366#issuecomment-39666813
    __PACKAGES="procps pciutils"
    # Also install python-requests
    __PACKAGES="${__PACKAGES} python-requests"
    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1


    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="build-essential python-dev python-pip"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${__PACKAGES} || return 1
        check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
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

    # Saltstack's Stable Debian repository
    if [ "$(grep -R 'latest jessie main' /etc/apt)" = "" ]; then
        echo "deb http://repo.saltstack.com/apt/debian/latest jessie main" >> \
            /etc/apt/sources.list.d/saltstack.list
    fi

    # shellcheck disable=SC2086
    wget $_WGET_ARGS -q https://repo.saltstack.com/apt/debian/latest/SALTSTACK-GPG-KEY.pub -O - | apt-key add - || return 1

    apt-get update || return 1
    __PACKAGES="libzmq3 libzmq3-dev python-zmq python-requests python-apt"

    # Additionally install procps and pciutils which allows for Docker boostraps. See 366#issuecomment-39666813
    __PACKAGES="procps pciutils"
    # Also install python-requests
    __PACKAGES="${__PACKAGES} python-requests"

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

    if [ "$(which git)" = "" ]; then
        __apt_get_install_noinput git || return 1
    fi

    __apt_get_install_noinput lsb-release python python-pkg-resources python-crypto \
        python-jinja2 python-m2crypto python-yaml msgpack-python python-pip || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            check_pip_allowed "You need to allow pip based installations (-P) in order to install the python package '${__REQUIRED_TORNADO}'"
            __apt_get_install_noinput python-dev
            pip install -U "${__REQUIRED_TORNADO}" || return 1
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
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

        if [ "$(which git)" = "" ]; then
            __PACKAGES="${__PACKAGES} git"
        fi

        # shellcheck disable=SC2086
        __apt_get_install_noinput ${__PACKAGES} || return 1

        easy_install -U pyzmq Jinja2 || return 1

        __git_clone_and_checkout || return 1

        # Let's trigger config_salt()
        if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
            _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
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

    if [ "$(which git)" = "" ]; then
        __apt_get_install_noinput git || return 1
    fi

    __apt_get_install_noinput lsb-release python python-pkg-resources python-crypto \
        python-jinja2 python-m2crypto python-yaml msgpack-python python-pip || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install tornado
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __apt_get_install_noinput python-tornado
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
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

__install_debian_stable() {
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
    __install_debian_stable || return 1
    return 0
}

install_debian_7_stable() {
    __install_debian_stable || return 1
    return 0
}

install_debian_8_stable() {
    __install_debian_stable || return 1
    return 0
}

install_debian_git() {
    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python setup.py install --install-layout=deb --salt-config-dir="$_SALT_ETC_DIR" || \
            python setup.py --salt-config-dir="$_SALT_ETC_DIR" install --install-layout=deb || return 1
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
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            if [ ! -f /etc/systemd/system/salt-${fname}.service ] || ([ -f /etc/systemd/system/salt-${fname}.service ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
                copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" /etc/systemd/system
            fi

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            /bin/systemctl enable salt-${fname}.service
            SYSTEMD_RELOAD=$BS_TRUE

        elif [ ! -f /etc/init.d/salt-$fname ] || ([ -f /etc/init.d/salt-$fname ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
            if [ -f "${__SALT_GIT_CHECKOUT_DIR}/debian/salt-$fname.init" ]; then
                copyfile "${__SALT_GIT_CHECKOUT_DIR}/debian/salt-$fname.init" "/etc/init.d/salt-$fname"
            else
                __fetch_url "/etc/init.d/salt-$fname" "http://anonscm.debian.org/cgit/pkg-salt/salt.git/plain/debian/salt-${fname}.init"
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
  if [ "$DISTRO_MAJOR_VERSION" -ge 22 ] || [ "$(which dnf)" != "" ]; then
    FEDORA_PACKAGE_MANAGER="dnf"
  fi
}

install_fedora_deps() {
    __fedora_get_package_manager
    if [ "$_ENABLE_EXTERNAL_ZMQ_REPOS" -eq $BS_TRUE ]; then
        __install_saltstack_copr_zeromq_repository || return 1
    fi

    __install_saltstack_copr_salt_repository || return 1

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
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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

    if [ "$(which git)" = "" ]; then
        $FEDORA_PACKAGE_MANAGER install -y git || return 1
    fi

    $FEDORA_PACKAGE_MANAGER install -y systemd-python || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            $FEDORA_PACKAGE_MANAGER install -y python-tornado
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_fedora_git() {
    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python setup.py install --salt-config-dir="$_SALT_ETC_DIR" || \
            python setup.py --salt-config-dir="$_SALT_ETC_DIR" install || return 1
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
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"

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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
    if [ ${__EPEL_REPOS_INSTALLED} -eq $BS_TRUE ]; then
        return 0
    fi

    # Check if epel repo is already enabled and flag it accordingly
    yum repolist | grep -i "epel" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        __EPEL_REPOS_INSTALLED=${BS_TRUE}
        return 0
    fi

    # Check if epel-release is already installed and flag it accordingly
    rpm --nodigest --nosignature -q epel-release > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        __EPEL_REPOS_INSTALLED=${BS_TRUE}
        return 0
    fi

    if [ "$CPU_ARCH_L" = "i686" ]; then
        EPEL_ARCH="i386"
    else
        EPEL_ARCH=$CPU_ARCH_L
    fi
    if [ "$DISTRO_MAJOR_VERSION" -eq 5 ]; then
        # Use dl.fedoraproject.org to avoid redirect breakage:
        # https://lists.fedoraproject.org/pipermail/users/2012-February/414558.html
        rpm -Uvh --force "http://dl.fedoraproject.org/pub/epel/5/${EPEL_ARCH}/epel-release-5-4.noarch.rpm" || return 1
    elif [ "$DISTRO_MAJOR_VERSION" -eq 6 ]; then
        rpm -Uvh --force "http://download.fedoraproject.org/pub/epel/6/${EPEL_ARCH}/epel-release-6-8.noarch.rpm" || return 1
    elif [ "$DISTRO_MAJOR_VERSION" -eq 7 ]; then
        rpm -Uvh --force "http://download.fedoraproject.org/pub/epel/7/${EPEL_ARCH}/e/epel-release-7-5.noarch.rpm" || return 1
    else
        echoerror "Failed add EPEL repository support."
        return 1
    fi
    __EPEL_REPOS_INSTALLED=${BS_TRUE}
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
            "http://copr.fedoraproject.org/coprs/saltstack/zeromq4/repo/${__REPOTYPE}-${DISTRO_MAJOR_VERSION}/saltstack-zeromq4-${__REPOTYPE}-${DISTRO_MAJOR_VERSION}.repo" || return 1
    fi
    return 0
}

__install_saltstack_copr_salt_el5_repository() {
    if [ ! -s /etc/yum.repos.d/saltstack-salt-el5-epel-5.repo ]; then
        __fetch_url /etc/yum.repos.d/saltstack-salt-el5-epel-5.repo \
            "http://copr.fedoraproject.org/coprs/saltstack/salt-el5/repo/epel-5/saltstack-salt-el5-epel-5.repo" || return 1
    fi
    return 0
}

__install_saltstack_rhel5_repository() {
    if [ ! -s /etc/yum.repos.d/repo-saltstack-el5.repo ]; then
        cat <<_eof > /etc/yum.repos.d/repo-saltstack-el5.repo
[repo-saltstack-el5]
name=SaltStack EL5 Repo
baseurl=https://repo.saltstack.com/yum/rhel5/
skip_if_unavailable=True
gpgcheck=1
gpgkey=https://repo.saltstack.com/yum/rhel5/SALTSTACK-EL5-GPG-KEY.pub
enabled=1
enabled_metadata=1
_eof

        __fetch_url /tmp/repo-saltstack-el5.pub "https://repo.saltstack.com/yum/rhel5/SALTSTACK-EL5-GPG-KEY.pub" || return 1
        rpm --import /tmp/repo-saltstack-el5.pub || return 1
        rm -f /tmp/repo-saltstack-el5.pub
    fi
    return 0
}

__install_saltstack_rhel_repository() {
    if [ ! -s "/etc/yum.repos.d/repo-saltstack-el${DISTRO_MAJOR_VERSION}.repo" ]; then
        cat <<_eof > "/etc/yum.repos.d/repo-saltstack-el${DISTRO_MAJOR_VERSION}.repo"
[repo-saltstack-el${DISTRO_MAJOR_VERSION}]
name=SaltStack EL${DISTRO_MAJOR_VERSION} Repo
baseurl=https://repo.saltstack.com/yum/rhel${DISTRO_MAJOR_VERSION}/
skip_if_unavailable=True
gpgcheck=1
gpgkey=https://repo.saltstack.com/yum/rhel${DISTRO_MAJOR_VERSION}/SALTSTACK-GPG-KEY.pub
enabled=1
enabled_metadata=1
_eof

        __fetch_url /tmp/repo-saltstack.pub "https://repo.saltstack.com/yum/rhel${DISTRO_MAJOR_VERSION}/SALTSTACK-GPG-KEY.pub" || return 1
        rpm --import /tmp/repo-saltstack.pub || return 1
        rm -f /tmp/repo-saltstack.pub
    fi
    return 0
}

__install_saltstack_copr_salt_repository() {
    echoinfo "Adding SaltStack's COPR repository"

    if [ "${DISTRO_NAME_L}" = "fedora" ]; then
        __REPOTYPE="${DISTRO_NAME_L}"
    else
        __REPOTYPE="epel"
    fi

    __REPO_FILENAME="saltstack-salt-${__REPOTYPE}-${DISTRO_MAJOR_VERSION}.repo"

    if [ ! -s "/etc/yum.repos.d/${__REPO_FILENAME}" ]; then
        __fetch_url "/etc/yum.repos.d/${__REPO_FILENAME}" \
            "http://copr.fedoraproject.org/coprs/saltstack/salt/repo/${__REPOTYPE}-${DISTRO_MAJOR_VERSION}/${__REPO_FILENAME}" || return 1
    fi
    return 0
}

install_centos_stable_deps() {
    __install_epel_repository || return 1
    if [ "$DISTRO_MAJOR_VERSION" -eq 5 ]; then
        __install_saltstack_rhel5_repository || return 1
    elif [ "$DISTRO_MAJOR_VERSION" -gt 5 ]; then
        __install_saltstack_rhel_repository || return 1
    fi

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
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
            check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
            __PACKAGES="${__PACKAGES} python26-setuptools"
        fi
    else
        __PACKAGES="${__PACKAGES} PyYAML m2crypto python-crypto python-msgpack python-zmq python-jinja2 python-requests"
        if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
            check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
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
        check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
    if [ "$(which git)" = "" ]; then
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

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
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
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
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
    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        $_PYEXE setup.py install --prefix=/usr --salt-config-dir="$_SALT_ETC_DIR" || \
            $_PYEXE setup.py --prefix=/usr --salt-config-dir="$_SALT_ETC_DIR" install || return 1
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
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            if [ ! -f /usr/lib/systemd/system/salt-${fname}.service ] || ([ -f /usr/lib/systemd/system/salt-${fname}.service ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
                copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" /usr/lib/systemd/system/
            fi

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            /bin/systemctl enable salt-${fname}.service
            SYSTEMD_RELOAD=$BS_TRUE

        elif [ ! -f /etc/init.d/salt-$fname ] || ([ -f /etc/init.d/salt-$fname ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
            copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}" /etc/init.d/
            chmod +x /etc/init.d/salt-${fname}

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            /sbin/chkconfig salt-${fname} on
        fi

        #if [ -f /sbin/initctl ]; then
        #    # We have upstart support
        #    /sbin/initctl status salt-$fname > /dev/null 2>&1
        #    if [ $? -eq 1 ]; then
        #        # upstart does not know about our service, let's copy the proper file
        #        copyfile ${__SALT_GIT_CHECKOUT_DIR}/pkg/salt-$fname.upstart /etc/init/salt-$fname.conf
        #    fi
        ## Still in SysV init?!
        #elif [ ! -f /etc/init.d/salt-$fname ] || ([ -f /etc/init.d/salt-$fname ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
        #    copyfile ${__SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname} /etc/init.d/
        #    chmod +x /etc/init.d/salt-${fname}
        #    /sbin/chkconfig salt-${fname} on
        #fi
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
__test_rhel_optionals_packages() {
    __install_epel_repository || return 1

    # Make sure yum-utils is installed
    yum list installed yum-utils > /dev/null 2>&1 || yum -y install yum-utils --enablerepo=${_EPEL_REPO} || return 1

    if [ "$DISTRO_MAJOR_VERSION" -ge 7 ]; then
        yum-config-manager --enable \*server-optional-rpms || return 1
    fi

    if [ "$DISTRO_MAJOR_VERSION" -ge 6 ]; then
        #python-jinja2 is in repo server-releases-optional in EC2/RHEL6
        yum-config-manager --enable rhui-\*-server-releases-optional || return 1

        # Let's enable package installation testing, kind of, --dry-run
        echoinfo "Testing if packages usually on the optionals repository are available:"
        __YUM_CONF_DIR="$(mktemp -d)"
        __YUM_CONF_FILE="${__YUM_CONF_DIR}/yum.conf"
        cp /etc/yum.conf "${__YUM_CONF_FILE}"
        echo 'tsflags=test' >> "${__YUM_CONF_FILE}"

        # Let's try installing the packages that usually require the optional repository
        # shellcheck disable=SC2043
        for package in python-jinja2; do
            echoinfo "  - ${package}"
            if [ "$DISTRO_NAME_L" = "oracle_linux" ]; then
                yum --config "${__YUM_CONF_FILE}" install -y ${package} >/dev/null 2>&1 || \
                    yum --config "${__YUM_CONF_FILE}" install -y ${package} --enablerepo=${_EPEL_REPO} >/dev/null 2>&1
            else
                yum --config "${__YUM_CONF_FILE}" install -y ${package} --enablerepo=${_EPEL_REPO} >/dev/null 2>&1
            fi
            if [ $? -ne 0 ]; then
                echoerror "Failed to find an installable '${package}' package. The optional repository or its subscription might be missing."
                rm -rf "${__YUM_CONF_DIR}"
                return 1
            fi
        done
        rm -rf "${__YUM_CONF_DIR}"
    fi
    return 0
}

install_red_hat_linux_stable_deps() {
    if [ "${DISTRO_MAJOR_VERSION}" -ge 6 ]; then
        # Wait at most 60 seconds for the repository subscriptions to register
        __ATTEMPTS=6
        while [ "${__ATTEMPTS}" -gt 0 ]; do
            __test_rhel_optionals_packages
            if [ $? -eq 1 ]; then
                __ATTEMPTS=$(( __ATTEMPTS -1 ))
                if [ ${__ATTEMPTS} -lt 1 ]; then
                    return 1
                fi
                echoinfo "Sleeping 10 seconds while waiting for the optional repository subscription to be externally configured"
                sleep 10
                continue
            else
                break
            fi
        done
    else
         __test_rhel_optionals_packages || return 1
    fi

    install_centos_stable_deps || return 1
    return 0
}

install_red_hat_linux_git_deps() {
    if [ "${DISTRO_MAJOR_VERSION}" -ge 6 ]; then
        # Wait at most 60 seconds for the repository subscriptions to register
        __ATTEMPTS=6
        while [ "${__ATTEMPTS}" -gt 0 ]; do
            __test_rhel_optionals_packages
            if [ $? -eq 1 ]; then
                __ATTEMPTS=$(( __ATTEMPTS -1 ))
                if [ ${__ATTEMPTS} -lt 1 ]; then
                    return 1
                fi
                echoinfo "Sleeping 10 seconds while waiting for the optional repository subscription to be externally configured"
                sleep 10
                continue
            else
                break
            fi
        done
    else
         __test_rhel_optionals_packages || return 1
    fi
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
    __test_rhel_optionals_packages || return 1
    install_centos_stable_deps || return 1
    return 0
}

install_oracle_linux_git_deps() {
    __test_rhel_optionals_packages || return 1
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

install_amazon_linux_ami_2010_deps() {
    # Linux Amazon AMI 2010.xx seems to use EPEL5 but the system is based on CentOS6.
    # Supporting this would be quite troublesome and we need to workaround some serious package conflicts
    echoerror "Amazon Linux AMI 2010 is not supported. Please use a more recent image (Amazon Linux AMI >= 2011.xx)"
    exit 1
}

install_amazon_linux_ami_2010_git_deps() {
    # Linux Amazon AMI 2010.xx seems to use EPEL5 but the system is based on CentOS6.
    # Supporting this would be quite troublesome and we need to workaround some serious package conflicts
    echoerror "Amazon Linux AMI 2010 is not supported. Please use a more recent image (Amazon Linux AMI >= 2011.xx)"
    exit 1
}

install_amazon_linux_ami_deps() {
    # According to http://aws.amazon.com/amazon-linux-ami/faqs/#epel we should

    # enable the EPEL 6 repo
    if [ "$CPU_ARCH_L" = "i686" ]; then
        EPEL_ARCH="i386"
    else
        EPEL_ARCH=$CPU_ARCH_L
    fi
    rpm -Uvh --force "http://mirrors.kernel.org/fedora-epel/6/${EPEL_ARCH}/epel-release-6-8.noarch.rpm" || return 1

    __REPO_FILENAME="saltstack-salt-epel-6.repo"

    if [ ! -s "/etc/yum.repos.d/${__REPO_FILENAME}" ]; then
        echoinfo "Adding SaltStack's COPR repository"
        __fetch_url /etc/yum.repos.d/${__REPO_FILENAME} \
            "http://copr.fedoraproject.org/coprs/saltstack/salt/repo/epel-6/${__REPO_FILENAME}" || return 1
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        yum -y update || return 1
    fi

    __PACKAGES="PyYAML m2crypto python-crypto python-msgpack python-zmq python-ordereddict python-jinja2 python-requests"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
        __PACKAGES="${__PACKAGES} python-pip"
    fi

    # shellcheck disable=SC2086
    yum -y install ${__PACKAGES} --enablerepo=${_EPEL_REPO}"" || return 1

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
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

    if [ "$(which git)" = "" ]; then
        yum -y install git --enablerepo=${_EPEL_REPO} || return 1
    fi

    __git_clone_and_checkout || return 1

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            yum install -y python-tornado
        fi
    fi


    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
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

    if [ "$(which pacman-db-upgrade)" != "" ]; then
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
    if [ "$(which git)" = "" ]; then
        pacman -Sy --noconfirm --needed git  || return 1
    fi
    pacman -R --noconfirm python2-distribute
    pacman -Sy --noconfirm --needed python2-crypto python2-setuptools python2-jinja \
        python2-m2crypto python2-markupsafe python2-msgpack python2-psutil python2-yaml \
        python2-pyzmq zeromq python2-requests python2-systemd || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            pacman -Sy --noconfirm --needed python2-tornado
        fi
    fi


    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
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
    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python2 setup.py install --salt-config-dir="$_SALT_ETC_DIR" || \
            python2 setup.py --salt-config-dir="$_SALT_ETC_DIR" install || return 1
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
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        # Since Arch's pacman renames configuration files
        if [ "$_TEMP_CONFIG_DIR" != "null" ] && [ -f "$_SALT_ETC_DIR/$fname.pacorig" ]; then
            # Since a configuration directory was provided, it also means that any
            # configuration file copied was renamed by Arch, see:
            #   https://wiki.archlinux.org/index.php/Pacnew_and_Pacsave_Files#.pacorig
            copyfile "$_SALT_ETC_DIR/$fname.pacorig" "$_SALT_ETC_DIR/$fname" $BS_TRUE
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
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /usr/bin/systemctl ]; then
            copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"

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
        copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-$fname" "/etc/rc.d/init.d/salt-$fname"
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
    conf_file=/usr/local/etc/pkg/repos/freebsd.conf
    {
        echo "FreeBSD:{"
        echo "    url: \"${PKGCONFURL}\","
        echo "    mirror_type: \"SRV\","
        echo "    enabled: true"
        echo "}"
    } > $conf_file
    copyfile $conf_file /etc/pkg/FreeBSD.conf
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

config_freebsd_salt() {
    # Set _SALT_ETC_DIR to ports default
    _SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/usr/local/etc/salt}
    # We also need to redefine the PKI directory
    _PKI_DIR=${_SALT_ETC_DIR}/pki

    config_salt || return 1

    return 0
}

install_freebsd_git_deps() {
    install_freebsd_9_stable_deps || return 1

    if [ "$(which git)" = "" ]; then
        /usr/local/sbin/pkg install -y git || return 1
    fi

    /usr/local/sbin/pkg install -y www/py-requests || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
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
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_freebsd_salt"
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
    install_freebsd_9_stable
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
        /usr/local/bin/python2 setup.py install \
            --salt-root-dir=/usr/local \
            --salt-config-dir="${_SALT_ETC_DIR}" \
            --salt-cache-dir=/var/cache/salt \
            --salt-sock-dir=/var/run/salt \
            --salt-srv-root-dir=/srv \
            --salt-base-file-roots-dir="${_SALT_ETC_DIR}/states" \
            --salt-base-pillar-roots-dir="${_SALT_ETC_DIR}/pillar" \
            --salt-base-master-roots-dir="${_SALT_ETC_DIR}/salt-master" \
            --salt-logs-dir=/var/log/salt \
            --salt-pidfile-dir=/var/run \
            || /usr/local/bin/python2 setup.py \
            --salt-root-dir=/usr/local \
            --salt-config-dir="${_SALT_ETC_DIR}" \
            --salt-cache-dir=/var/cache/salt \
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
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        enable_string="salt_${fname}_enable=\"YES\""
        grep "$enable_string" /etc/rc.conf >/dev/null 2>&1
        [ $? -eq 1 ] && echo "$enable_string" >> /etc/rc.conf

        [ -f "${_SALT_ETC_DIR}/${fname}.sample" ] && copyfile "${_SALT_ETC_DIR}/${fname}.sample" "${_SALT_ETC_DIR}/${fname}"

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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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

    which git > /dev/null 2>&1
    if [ $? -eq 1 ]; then
        pkgin -y install git || return 1
    fi

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        check_pip_allowed "You need to allow pip based installations (-P) in order to install the python package '${__REQUIRED_TORNADO}'"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            if [ "$(which pip)" = "" ]; then
                pkgin -y install py27-pip
            fi
            pip install -U "${__REQUIRED_TORNADO}"
        fi
    fi

    __git_clone_and_checkout || return 1
    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
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
    USE_SETUPTOOLS=1 /opt/local/bin/python setup.py install --salt-config-dir="$_SALT_ETC_DIR" || \
        USE_SETUPTOOLS=1 /opt/local/bin/python setup.py --salt-config-dir="$_SALT_ETC_DIR" install || return 1
    return 0
}

install_smartos_post() {
    smf_dir="/opt/custom/smf"
    # Install manifest files if needed.
    for fname in minion master syndic api; do

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
                    copyfile "$_TEMP_CONFIG_DIR/salt-$fname.xml" "$smf_dir/" || return 1
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
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        svcs "network/salt-$fname" > /dev/null 2>&1
        if [ $? -eq 1 ]; then
            svccfg import "${__SALT_GIT_CHECKOUT_DIR}/pkg/smartos/salt-$fname.xml"
            if [ "${VIRTUAL_TYPE}" = "global" ]; then
                if [ ! -d $smf_dir ]; then
                    mkdir -p "$smf_dir"
                fi
                if [ ! -f "$smf_dir/salt-$fname.xml" ]; then
                    copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/smartos/salt-$fname.xml" "$smf_dir/"
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
    if [ "$(which python)" = "" ]; then
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
    DISTRO_REPO="openSUSE_${DISTRO_MAJOR_VERSION}.${DISTRO_MINOR_VERSION}"

    # Is the repository already known
    __zypper repos | grep devel_languages_python >/dev/null 2>&1
    if [ $? -eq 1 ]; then
        # zypper does not yet know nothing about devel_languages_python
        __zypper addrepo --refresh \
            "http://download.opensuse.org/repositories/devel:/languages:/python/${DISTRO_REPO}/devel:languages:python.repo" || return 1
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
    __PACKAGES="${__PACKAGES} libzmq3 python python-Jinja2 python-M2Crypto python-PyYAML python-requests"
    __PACKAGES="${__PACKAGES} python-msgpack-python python-pycrypto python-pyzmq python-xml"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-apache-libcloud"
    fi

    # shellcheck disable=SC2086
    __zypper_install ${__PACKAGES} || return 1

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __zypper_install ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_opensuse_git_deps() {
    install_opensuse_stable_deps || return 1

    if [ "$(which git)" = "" ]; then
        __zypper_install git  || return 1
    fi

    __zypper_install patch || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/pkg/suse/use-forking-daemon.patch" ]; then
        cd "${__SALT_GIT_CHECKOUT_DIR}"
        echowarn "Applying patch to systemd service unit file"
        patch -p1 < pkg/suse/use-forking-daemon.patch || return 1
    fi

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __zypper_install python-tornado
        fi

    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            if [ "${DISTRO_MAJOR_VERSION}" -gt 13 ] || ([ "${DISTRO_MAJOR_VERSION}" -eq 13 ] && [ "${DISTRO_MINOR_VERSION}" -ge 2 ]); then
                copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" "/usr/lib/systemd/system/salt-${fname}.service"
            else
                copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"
            fi
            continue
        fi

        copyfile "${__SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-$fname" "/etc/init.d/salt-$fname"
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
#    SuSE Install Functions.
#
install_suse_11_stable_deps() {
    SUSE_PATCHLEVEL=$(awk '/PATCHLEVEL/ {print $3}' /etc/SuSE-release )
    if [ "${SUSE_PATCHLEVEL}" != "" ]; then
        DISTRO_PATCHLEVEL="_SP${SUSE_PATCHLEVEL}"
    fi
    DISTRO_REPO="SLE_${DISTRO_MAJOR_VERSION}${DISTRO_PATCHLEVEL}"

    # Is the repository already known
    __zypper repos | grep devel_languages_python >/dev/null 2>&1
    if [ $? -eq 1 ]; then
        # zypper does not yet know nothing about devel_languages_python
        __zypper addrepo --refresh \
            "http://download.opensuse.org/repositories/devel:/languages:/python/${DISTRO_REPO}/devel:languages:python.repo" || return 1
    fi

    __zypper --gpg-auto-import-keys refresh || return 1

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __zypper --gpg-auto-import-keys update || return 1
    fi

    # Salt needs python-zypp installed in order to use the zypper module
    __PACKAGES="python-zypp"
    # shellcheck disable=SC2089
    __PACKAGES="${__PACKAGES} libzmq3 python python-Jinja2 python-msgpack-python"
    __PACKAGES="${__PACKAGES} python-pycrypto python-pyzmq python-pip python-xml python-requests"

    if [ "$SUSE_PATCHLEVEL" -eq 1 ]; then
        check_pip_allowed
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
                [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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

    if [ "$(which git)" = "" ]; then
        __zypper_install git  || return 1
    fi

    __git_clone_and_checkout || return 1

    if [ -f "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${__SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __zypper_install python-tornado
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${__SALT_GIT_CHECKOUT_DIR}/conf/"
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
            [ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue
        __check_services_systemd salt-$fname || return 1
    done
    return 0
}
#
#   End of SuSE Install Functions.
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
        if [ "$(which eix)" != "" ]; then
            eix-sync
        else
            emerge --sync
        fi
    else
        if [ "$(which eix)" != "" ]; then
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
        check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
        movefile "$_TEMP_CONFIG_DIR/grains" "$_SALT_ETC_DIR/grains" || return 1
        CONFIGURED_ANYTHING=$BS_TRUE
    fi

    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        # Create the PKI directory
        [ -d "$_PKI_DIR/minion" ] || (mkdir -p "$_PKI_DIR/minion" && chmod 700 "$_PKI_DIR/minion") || return 1

        # Copy the minions configuration if found
        if [ -f "$_TEMP_CONFIG_DIR/minion" ]; then
            movefile "$_TEMP_CONFIG_DIR/minion" "$_SALT_ETC_DIR" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi

        # Copy the minion's keys if found
        if [ -f "$_TEMP_CONFIG_DIR/minion.pem" ]; then
            movefile "$_TEMP_CONFIG_DIR/minion.pem" "$_PKI_DIR/minion/" || return 1
            chmod 400 "$_PKI_DIR/minion/minion.pem" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
        if [ -f "$_TEMP_CONFIG_DIR/minion.pub" ]; then
            movefile "$_TEMP_CONFIG_DIR/minion.pub" "$_PKI_DIR/minion/" || return 1
            chmod 664 "$_PKI_DIR/minion/minion.pub" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
        # For multi-master-pki, copy the master_sign public key if found
        if [ -f "$_TEMP_CONFIG_DIR/master_sign.pub" ]; then
            movefile "$_TEMP_CONFIG_DIR/master_sign.pub" "$_PKI_DIR/minion/" || return 1
            chmod 664 "$_PKI_DIR/minion/master_sign.pub" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
    fi


    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ] || [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        # Create the PKI directory
        [ -d "$_PKI_DIR/master" ] || (mkdir -p "$_PKI_DIR/master" && chmod 700 "$_PKI_DIR/master") || return 1

        # Copy the masters configuration if found
        if [ -f "$_TEMP_CONFIG_DIR/master" ]; then
            movefile "$_TEMP_CONFIG_DIR/master" "$_SALT_ETC_DIR" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi

        # Copy the master's keys if found
        if [ -f "$_TEMP_CONFIG_DIR/master.pem" ]; then
            movefile "$_TEMP_CONFIG_DIR/master.pem" "$_PKI_DIR/master/" || return 1
            chmod 400 "$_PKI_DIR/master/master.pem" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
        if [ -f "$_TEMP_CONFIG_DIR/master.pub" ]; then
            movefile "$_TEMP_CONFIG_DIR/master.pub" "$_PKI_DIR/master/" || return 1
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

        movefile "$src_keyfile" "$dst_keyfile" || return 1
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
        #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
    if [ ! -d /var/cache/salt/minion/proc ]; then
        echodebug "Creating salt's cachedir"
        mkdir -p /var/cache/salt/minion/proc
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
    echodebug "Waiting ${__DEFAULT_SLEEP} seconds for processes to settle before checking for them"
    sleep ${__DEFAULT_SLEEP}
    $STARTDAEMONS_INSTALL_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${STARTDAEMONS_INSTALL_FUNC}()!!!"
        exit 1
    fi
fi

# Check if the installed daemons are running or not
if [ "$DAEMONS_RUNNING_FUNC" != "null" ] && [ $_START_DAEMONS -eq $BS_TRUE ]; then
    echoinfo "Running ${DAEMONS_RUNNING_FUNC}()"
    echodebug "Waiting ${__DEFAULT_SLEEP} seconds for processes to settle before checking for them"
    sleep ${__DEFAULT_SLEEP}  # Sleep a little bit to let daemons start
    $DAEMONS_RUNNING_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${DAEMONS_RUNNING_FUNC}()!!!"

        for fname in minion master syndic api; do
            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            # Skip if not meant to be installed
            [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
            [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
            #[ $fname = "api" ] && ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || [ "$(which salt-${fname} 2>/dev/null)" = "" ]) && continue
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
