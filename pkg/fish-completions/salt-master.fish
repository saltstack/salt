# salt-master completion for fish shell
# See salt.fish in the same folder for the information

# hack to load functions from salt.fish completion
complete --do-complete='salt --' > /dev/null

