# salt-key completion for fish shell
# See salt_common.fish in the same folder for the information

# hack to load functions from salt_common completion
complete --do-complete='salt_common --' >/dev/null


# salt-key general options (from --help)
complete -c salt-key         -f -s A -l accept-all           -d "Accept all pending keys"
complete -c salt-key         -f -s a -l accept               -d "Accept the specified public key (use --include-all to match rejected keys in addition to pending keys).  Globs are supported."
complete -c salt-key         -f      -l auto-create          -d "Auto-create a signing key-pair if it does not yet exist"
complete -c salt-key         -f -s D -l delete-all           -d "Delete all keys"
complete -c salt-key         -f -s d -l delete               -d "Delete the specified key. Globs are supported."
complete -c salt-key         -f -s F -l finger-all           -d "Print all keys' fingerprints"
complete -c salt-key         -f -s f -l finger               -d "Print the specified key's fingerprint"
complete -c salt-key         -r      -l gen-keys-dir         -d "Set the directory to save the generated keypair, only works with \"gen_keys_dir\" option; default=."
complete -c salt-key         -f      -l gen-keys             -d "Set a name to generate a keypair for use with salt"
complete -c salt-key         -f      -l gen-signature        -d "Create a signature file of the masters public-key named master_pubkey_signature. The signature can be send to a minion in the masters auth-reply and enables the minion to verify the masters public-key cryptographically. This requires a new signing-key- pair which can be auto-created with the --auto-create parameter"
complete -c salt-key         -f      -l include-all          -d "Include non-pending keys when accepting/rejecting"
complete -c salt-key         -x      -l keysize              -d "Set the keysize for the generated key, only works with the \"--gen-keys\" option, the key size must be 2048 or higher, otherwise it will be rounded up to 2048; ; default=2048"
complete -c salt-key         -f -s L -l list-all             -d "List all public keys. (Deprecated: use \"--list all\")"
complete -c salt-key         -x -s l -l list                 -d "List the public keys" -a "pre un unaccepted acc accepted rej rejected all"
complete -c salt-key         -f -s P -l print-all            -d "Print all public keys"
complete -c salt-key         -f -s p -l print                -d "Print the specified public key"
complete -c salt-key         -r      -l priv                 -d "The private-key file to create a signature with"
complete -c salt-key         -r      -l pub                  -d "The public-key file to create a signature for"
complete -c salt-key         -f -s R -l reject-all           -d "Reject all pending keys"
complete -c salt-key         -f -s r -l reject               -d "Reject the specified public key (use --include-all to match accepted keys in addition to pending keys).  Globs are supported."
complete -c salt-key         -r      -l signature-path       -d "The path where the signature file should be written"

# minions
complete -c salt-key     -f -n '__fish_contains_opt -s a accept; and not __fish_salt_extract_minion' -a '(__fish_salt_list_minion unaccepted) (__fish_salt_list_minion rejected)'
complete -c salt-key     -f -n '__fish_contains_opt -s d delete; and not __fish_salt_extract_minion' -a '(__fish_salt_list_minion all)'
complete -c salt-key     -f -n '__fish_contains_opt -s f finger; and not __fish_salt_extract_minion' -a '(__fish_salt_list_minion all)'
complete -c salt-key     -f -n '__fish_contains_opt -s p print; and not __fish_salt_extract_minion' -a '(__fish_salt_list_minion all)'
complete -c salt-key     -f -n '__fish_contains_opt -s r reject; and not __fish_salt_extract_minion' -a '(__fish_salt_list_minion unaccepted) (__fish_salt_list_minion accepted)'
