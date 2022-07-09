#!/bin/bash
#
# For each shared object (.so) file under the given directory, find all shared
# libraries needed and copy them into the the directory. Then modify the rpath
# of the shared object to look for the library in the target directory.
LIBS=()
LIBSDIR=$1
DONE=false
while [ "$DONE" = false ]; do
  DONE=true
  for shlib in $(find $LIBSDIR -name '*so*' -type f -perm /a+x); do
    echo "Found shared library, $shlib"
    for lib in $(ldd $shlib  | awk '{print $3}' | sed '/^$/d'); do
      if [ -e $lib ]; then
        TARGET=$LIBSDIR/$(basename $lib)
        if [ ! -e $TARGET ]; then
          DONE=false
  	  echo "Creating depenency $($LIBSDIR)/$(basename $lib)";
  	  cp $(realpath $lib) $LIBSDIR/$(basename $lib);
        else
  	  echo "$TARGET exits"
        fi
        RELLIBSDIR=$(realpath --relative-to=$(dirname $shlib) $LIBSDIR)
        RPATH="\$ORIGIN/$RELLIBSDIR"
        patchelf --set-rpath $RPATH $shlib
      fi
    done
  done
done
