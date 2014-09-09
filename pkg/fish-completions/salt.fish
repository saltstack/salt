# salt completion for fish shell
# See salt_common.fish in the same folder for the information

# hack to load functions from salt_common completion
complete --do-complete='salt_common --' >/dev/null

# salt
# minions
complete -c salt         -f -n                                   'not __fish_salt_extract_minion'   -a '(__fish_salt_list_minion accepted)'
# functions
complete -c salt         -f -n '__fish_salt_extract_minion;   and not __fish_salt_extract_function' -a '(__fish_salt_list_function)'
# arguments and name values
complete -c salt         -f -n '__fish_salt_extract_function'                                       -a '(__fish_salt_list_arg_name) (__fish_salt_list_arg_value | __fish_salt_prefix_with_arg_name)'
