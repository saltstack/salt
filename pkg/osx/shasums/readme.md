ShaSums
=======

This directory contains shasums for files that are downloaded by the `build_env.sh` script.

The SHA's have been created using the following command:


Bash:
```
shasum -a 512 ./<filename> > ./<filename>.sha512
```

Powershell:
```
$hash = get-filehash .\<filename> -Algorithm SHA512
($hash.Hash.ToLower(), $hash.Path.Split("\")[-1]) -join "  " > <filename>.sha512
```