#!/usr/bin/env bash
#
# Name:     build_shar.sh
# Requires: python-virtualenv, gcc, gcc-c++, swig, sharutils, and the
#           develepment headers for both python and openssl
#
# This script will use GNU sharutils to build an installable shar archive, with
# an install prefix of "/opt" (unless overridden with the '-p' option). This
# has a couple uses:
#
#   1. Installing salt (by su'ing to root and running "sh /path/to/sharfile")
#   2. To be used as a basis for creating your own salt rpm/deb.
#
# It will fetch libzmq and build it as a pyzmq extension.
#
# IMPORTANT: Unpacking the shar requires uudecode, which is distributed along
# with sharutils. Thus, you should have sharutils installed on any host which
# will need to unpack the shar archive.
#
# The script is capable of building a shar archive using several methods:
#
#   1. Using a custom pip requirements file
#   2. Using an existing salt tarball (downloaded from PyPI)
#   3. Specifying a version number (the script will fetch the requested version
#      from PyPI)
#
# Additionally, it is possible to specify a build_id which will be added to the
# shar filename, useful for telling apart individual shars.
#
# By default, the script will download dependencies using pip, but the '-d'
# option can be used to specify directory from which dependencies will be
# sourced. Any missing dependencies will be retrieved with pip.
#
# It is strongly recommended to run this script on a machine which does not
# have any of the Salt dependencies already installed, because if the script
# detects that ZeroMQ is already installed, then pyzmq's setup.py will not
# build a bundled ZeroMQ.
#
# Run the script with -h for usage details.
#

################################# FUNCTIONS ##################################

function _timestamp {
    date "+%Y-%m-%d %H:%M:%S:"
}

function _log {
    timestamp=$(_timestamp)
    echo "$1" | sed "s/^/$(_timestamp) /" >>"$logfile"
}

# Both echo and log
function _display {
    echo "$1"
    _log "$1"
}

function _error {
    msg="ERROR: $1"
    echo "$msg" 1>&2
    echo "$(_timestamp) $msg" >>"$logfile"
    echo "One or more errors found. See $logfile for details." 1>&2
    exit 1
}

function _tolower {
    echo "$1" | tr '[:upper:]' '[:lower:]'
}

function _find_tarball {
    target=$1
    location=$2
    _log "Looking for $target tarball in $location"

    # We're looking for a tarball starting with "$target-"
    len_target=`expr length "$target"`
    let len_target=${len_target}+1

    matches=()
    for filename in `ls "${location}"`
    do
        case "$filename" in
            *tar.*)
                filename_lower=$(_tolower "$filename")
                target_lower=$(_tolower "$target")
                if test ${filename_lower:0:${len_target}} == "${target_lower}-"; then
                    matches=("${matches[@]}" "$filename")
                    test ${#matches[@]} -gt 1 && _error "Ambiguous target \"${target}\""
                fi
                ;;
            *) continue;;
        esac
    done
    match=${matches[0]}
    if test -n "$match"; then
        _log "$target tarball is ${matches[0]}"
        echo ${matches[0]}
    else
        _error "$target tarball was not found in $location"
    fi
}

function _requirements_str {
    test -n "$1" && echo "${srcdir}/${1}/requirements.txt" || _error 'Missing release string for _requirements_str'
}

function _get_requirements {
    if test -z "$requirements"; then
        if test -n "${salt_release}"; then
            # salt_release is only set at this point if -s was passed, in which
            # case the tarball has been unpacked already and we want to grab
            # the tarballs from its requirements.txt.
            requirements=$(_requirements_str "$salt_release")
        fi
    else
        # Custom requirements were passed via -r
        _display "Using custom requirements from $requirements"
    fi

    _display 'Grabbing source tarballs'
    if test -n "$requirements"; then
        # Either custom requirements were passed, or a salt tarball was
        # provided. Either way, we're going to be telling pip to download
        # tarballs using the instructions in the requirements.txt.
        output=`pip install $PIP_OPTS --download "$srcdir" --requirement "$requirements"`; return_code=$?
    else
        # Neither -r nor -s was specified. We are just downloading the current
        # version of salt from pip, and letting pip resolve dependencies rather
        # than providing them in a requirements.txt.
        #
        # If -v was provided, then pip will download the specified version,
        # otherwise this variable will be blank.
        output=`pip install $PIP_OPTS --download "$srcdir" "salt${version}"`; return_code=$?
    fi
    _log "$output"
    test "$return_code" -eq 0 || _error 'Failed to download tarballs. Aborting.'
}

function _unpack_salt_tarball {
    _display "Unpacking Salt tarball"
    if test -z "$salt_tarball"; then
        salt_tarball=$(_find_tarball salt "$srcdir")
        salt_release=${salt_tarball%%.tar*}
    fi
    cd "$srcdir"
    rm -rf "$salt_release"
    tar xf "$salt_tarball"
    test -z "$requirements" && requirements=$(_requirements_str "$salt_release")
}

function _usage {
    printf "USAGE: build_shar.sh [-i <build_id>] [-d <dependency_dir>] [-p <prefix>] [-r <requirements file> | -s <alternate salt tarball> | -v <version from pypi>]\n\n" 1>&2
    exit 2
}

#################################### MAIN ####################################

# Set up logging
orig_cwd="`pwd`"
logfile="${orig_cwd}/install.`date +%Y%m%d%H%M%S`.log"
echo "Install log location: $logfile"

prefix='/opt'
while getopts d:hi:p:r:s:v: opt; do
    case "$opt" in
        d)
            deps_dir=$OPTARG
            test -d "$deps_dir" || _error "Dependencies dir $deps_dir does not exist"
            ;;
        i)
            build_id=$OPTARG;;
        p)
            prefix=$OPTARG;;
        r)
            requirements=$OPTARG
            test -f "$requirements" || _error "Requirements file $requirements does not exist"
            ;;
        s)
            salt_tarball=$OPTARG
            test -f "$salt_tarball" || _error "Salt tarball $salt_tarball does not exist"
            ;;
        v)
            version=$OPTARG
            ;;
        *) _usage;;
    esac
done

case "$prefix" in
    /*) ;;
    *) _error "Prefix path must be absolute" ;;
esac

# Make sure that only one of -r/-s/-v was specified
opt_count=0
for opt in "$requirements" "$salt_tarball" "$version"; do
    test -n "$opt" && let opt_count=$opt_count+1
done
test $opt_count -ge 2 && _usage

# If version was provided, prepend with "==" for later use in pip command
test -n "$version" && version="==${version}"

# Make needed directories
srcdir="${orig_cwd}/src"
pkgdir="${orig_cwd}/pkg"
test -d "$srcdir" || mkdir "$srcdir"
_log "Source directory: $srcdir"
if test -d "$pkgdir"; then
    _log "Removing existing package directory $pkgdir"
    rm -rf "$pkgdir"
fi
_log "Creating package directory $pkgdir"
mkdir "$pkgdir"

# Make sure virtualenv is available
test -z "$VIRTUALENV" && VIRTUALENV=`command -v virtualenv`
test -z "$VIRTUALENV" && _error 'virtualenv not present'
_display "virtualenv == $VIRTUALENV"
if ! test -x "`command -v $VIRTUALENV`"; then
    _error "$VIRTUALENV is not executable"
fi

# Make sure we're using an up-to-date version of pip in the virtualenv, as
# older pip versions have issues with pip install --download, silently not
# downloading some tarballs.
cd "$orig_cwd"
venv_name=`mktemp -d venv.XXXXXX`
venv_path="${orig_cwd}/${venv_name}"
_display "Creating temp virtualenv at $venv_path"
output=`"$VIRTUALENV" $venv_name`
_log "$output"
_display "Activating temp virtualenv"
source "${venv_path}/bin/activate"
_display "Updating pip in temp virtualenv"
output=`pip install --upgrade pip`
_log "$output"

# Check if wheel is supported in current version of pip
pip help install 2>/dev/null | egrep --quiet '(--)no-use-wheel' && PIP_OPTS='--no-use-wheel' || PIP_OPTS=''

# Make sure swig is available
test -z "$SWIG" && SWIG=`command -v swig`
test -z "$SWIG" && _error 'swig not present'
_display "swig == $SWIG"
if ! test -x "`command -v $SWIG`"; then
    _error "$SWIG is not executable"
fi

# Make sure gcc, g++, and sharutils are available
test -n "`command -v gcc`" && _display 'gcc found' || _error 'gcc not installed'
test -n "`command -v g++`" && _display 'g++ found' || _error 'g++ not installed'
test -n "`command -v shar`" && _display 'sharutils found' || _error 'sharutils not installed'

INSTALL="python setup.py install --root=${pkgdir} --prefix=${prefix}"

if test -n "$salt_tarball"; then
    cp "$salt_tarball" "$srcdir" || _error "Unable to copy salt tarball to $srcdir"
    salt_tarball=`basename "$salt_tarball"`
    salt_release=${salt_tarball%%.tar*}
    _unpack_salt_tarball
    _get_requirements
else
    _get_requirements
    _unpack_salt_tarball
fi

_display "Deactivating temp virtualenv"
deactivate
_display "Destroying temp virtualenv at $venv_path"
rm -rf "$venv_path"

_display "Reading requirements from $requirements"
deps=()
for dep in `cat "$requirements" | awk '{print $1}'`; do
    test "$dep" == 'salt' && continue
    deps=("${deps[@]}" "$dep")
done

for dep in "${deps[@]}"; do
    _display "Dependency found: $dep"
done

# Install the deps
for dep in "${deps[@]}"; do
    tarball=$(_find_tarball "$dep" "$srcdir")
    if test -n "$deps_dir"; then
        deps_dir_tarball=$(_find_tarball "$dep" "$deps_dir")
        if test -n "$deps_dir_tarball"; then
            _display "Using dependency tarball from $deps_dir for $dep"
            rm -f "$tarball"
            cp "${deps_dir}/${deps_dir_tarball}" "$srcdir"
            tarball="${deps_dir_tarball}"
        fi
    fi
    cd "$srcdir"
    src=${tarball%%.tar*}
    _display "Unpacking $src"
    rm -rf $src
    tar xf $tarball
    cd "$src"
    # Fetch libzmq so bundled build works on CentOS 5
    if test "${src:0:5}" == 'pyzmq'; then
        zeromq_spec="bundled/zeromq/zeromq.spec"
        if ! test -f "$zeromq_spec"; then
            _display "Fetching libzmq"
            output=`python setup.py fetch_libzmq 2>&1`; return_code=$?
            test "$return_code" -eq 0 || _error 'Failed to fetch libzmq. Aborting.'
        else
            _display "Bundled ZeroMQ detected"
        fi
        zeromq_version=`egrep '^Version' "$zeromq_spec" | awk '{print $2}'`
        _display "ZeroMQ version: $zeromq_version"
    fi
    _display "Installing $src"
    if test "${src:0:8}" == 'M2Crypto'; then
        arch=`uname -m`
        output=`env SWIG_FEATURES="-cpperraswarn -includeall -D__${arch}__ -I/usr/include/openssl" $INSTALL 2>&1`; return_code=$?
    else
        output=`$INSTALL 2>&1`; return_code=$?
    fi
    _log "$output"
    test "$return_code" -eq 0 || _error "Failed to install $src. Aborting."
done

# Install salt
cd "${srcdir}/${salt_release}"
_display "Installing $salt_release"
output=`$INSTALL 2>&1`; return_code=$?
_log "$output"
test "$return_code" -eq 0 || _error "Failed to install $salt_release. Aborting."
_log 'Compressing man pages'
output=`find "${pkgdir}${prefix}/share/man" -type f -not -name '*.gz' -exec gzip {} \;`
_log "$output"

# Everything worked, make the shar
test -n "$build_id" && build_id="-${build_id}"
pkg="${orig_cwd}/${salt_release}${build_id}.shar"
sharlog="${pkg}.log"
_display "Packaging Salt... Destination: $pkg"
_display "shar log will be written to $sharlog"
cd "$pkgdir"
shar ${prefix#/} >"$pkg" 2>"$sharlog"
test "$?" -eq 0 || _error 'shar file build failed'

# Done!
_display "Build of $pkg complete! Nice!"
