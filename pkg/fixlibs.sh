#!/bin/bash
#
# For each shared object (.so) file under the given directory, find all shared
# libraries needed and copy them into the the directory. Then modify the rpath
# of the shared object to look for the library in the target directory.
SEENSLIBS=()
LIBSDIR=$1
LIBCLIBS=("librt.so.1" "libc.so.6" "libpthread.so.0" "libm.so.6", "libutil.so.1" "libcrypt.so.1")
UNAME=$(uname -s)

if [ "$UNAME" == "Darwin" ];then
  realpath() {
    OURPWD=$PWD
    cd "$(dirname "$1")"
    LINK=$(readlink "$(basename "$1")")
    while [ "$LINK" ]; do
      cd "$(dirname "$LINK")"
      LINK=$(readlink "$(basename "$1")")
    done
    REALPATH="$PWD/$(basename "$1")"
    cd "$OURPWD"
    echo "$REALPATH"
  }
fi

DONE=false

fixlibs_linux() {
  while [ "$DONE" = false ]; do
    DONE=true
    for shlib in $(find $LIBSDIR -name '*so*' -type f -perm /a+x); do
      if [[ ! " ${SEENLIBS[*]} " =~ " ${shlib} " ]]; then
          echo "Found shared library, $shlib"
          for lib in $(ldd $shlib  | awk '{print $3}' | sed '/^$/d'); do
            if [ -e $lib ]; then
              base=$(basename $lib)
              if [[ ! " ${LIBCLIBS[*]} " =~ " ${base} " ]]; then
                TARGET=$LIBSDIR/$(basename $lib)
                if [ ! -e $TARGET ]; then
                  DONE=false
                  echo "Creating depenency $($LIBSDIR)/$(basename $lib)";
                  cp $(realpath $lib) $LIBSDIR/$(basename $lib);
                else
                  echo "$TARGET exits"
                fi
              else
                echo "Skipping glibc $lib"
              fi
            fi
          done
          ORIG_RPATH=$(readelf -a "$shlib" | grep "PATH"| sed -e 's/^.*\[\(.*\)]$/\1/g')
          RELLIBSDIR=$(realpath --relative-to=$(dirname $shlib) $LIBSDIR)
          if [ -z "$ORIG_RPATH" ]; then
            RPATH="\$ORIGIN:\$ORIGIN/$RELLIBSDIR"
          else
            echo "Preserving existing rpath.."
            RPATH="$ORIG_RPATH:\$ORIGIN:\$ORIGIN/$RELLIBSDIR"
          fi
          patchelf --set-rpath $RPATH $shlib
          SEENLIBS+=($shlib)
      else
          echo "Already processed $shlib"
      fi
    done
  done
}

fixlibs_darwin() {
  while [ "$DONE" = false ]; do
    DONE=true
    for shlib in $(find $LIBSDIR -name '*so*' -type f -perm "755"); do
      if [[ ! " ${SEENLIBS[*]} " =~ " ${shlib} " ]]; then
          echo "Found shared library, $shlib"
          for lib in $(otool -l $shlib 2>&1 | sed -e '1d; s/^[[:blank:]]\(.*\) (.*/\1/g'); do
            if [ -e $lib ]; then
              base=$(basename $lib)
              if [[ ! " ${LIBCLIBS[*]} " =~ " ${base} " ]]; then
                TARGET=$LIBSDIR/$(basename $lib)
                if [ ! -e $TARGET ]; then
                  DONE=false
                  echo "Creating depenency $($LIBSDIR)/$(basename $lib)";
                  cp $(realpath $lib) $LIBSDIR/$(basename $lib);
                else
                  echo "$TARGET exits"
                fi
              else
                echo "Skipping glibc $lib"
              fi
            fi
          done
          RELLIBSDIR=$(realpath --relative-to=$(dirname $shlib) $LIBSDIR)
          install_name_tool -add_rpath "@loader_path/$RELLIBSDIR" $shlib
          SEENLIBS+=($shlib)
      else
          echo "Already processed $shlib"
      fi
    done
  done
}

if [[ "$UNAME" == "Darwin" ]]; then
  fixlibs_darwin
elif [[ "$UNAME" == "Linux" ]]; then
  fixlibs_linux
else
  echo "This script doesn't handle $UNAME"
fi
