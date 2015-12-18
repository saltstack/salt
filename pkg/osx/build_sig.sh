if [ "$1" == "" ]; then
    echo "Must supply an input package"
else
    INPUT=$1
fi

if [ "$2" == "" ]; then
    echo "Must supply an output package name"
else
    OUTPUT=$2
fi
security import "Developer ID Installer.p12" -k ~/Library/Keychains/login.keychain
productsign --sign "Developer ID Installer: Salt Stack, Inc. (VK797BMMY4)" $INPUT $OUTPUT
