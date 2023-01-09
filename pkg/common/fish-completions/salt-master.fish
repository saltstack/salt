# salt-master completion for fish shell
# See salt_common.fish in the same folder for the information

# hack to load functions from salt_common completion
complete --do-complete='salt_common --' >/dev/null

