# salt completion for fish shell
# See salt_common.fish in the same folder for the information

# hack to load functions from salt_common completion
complete --do-complete='salt_common --' >/dev/null

# salt general options (from --help)
for auth in auth eauth external-auth
	complete -c salt         -f -s a -l $auth                -d "Specify an external authentication system to use."
end
for batch in batch batch-size
	complete -c salt         -f -s b -l $batch               -d "Execute the salt job in batch mode, pass either the number of minions to batch at a time, or the percentage of minions to have runnin"
end
complete -c salt             -x      -l args-separator       -d "Set the special argument used as a delimiter between command arguments of compound commands. This is useful when one wants to pass commas as arguments to some of the commands in a compound command."
complete -c salt             -f      -l async                -d "Run the salt command but don't wait for a reply"
complete -c salt             -f -s C -l compound             -d "The compound target option allows for multiple target types to be evaluated, allowing for greater granularity in target matching. The compound target is space delimited, targets other than globs are preceded with an identifier matching the specific targets argument type: salt \"G@os:RedHat and webser* or E@database.*\""
complete -c salt             -f -s S -l ipcidr               -d "Match based on Subnet (CIDR notation) or IPv4 address."
complete -c salt             -f -s T -l make-token           -d "Generate and save an authentication token for re-use. The token is generated and made available for the period defined in the Salt Master."
complete -c salt             -x      -l password             -d "Password for external authentication"
complete -c salt             -f -s I -l pillar               -d "Instead of using shell globs to evaluate the target use a pillar value to identify targets, the syntax for the target is the pillar key followed by a globexpression: \"role:production*\""
complete -c salt             -f      -l show-timeout         -d "Display minions that timeout without the additional output of --verbose"
complete -c salt             -f      -l show-jid             -d "Display jid without the additional output of --verbose"
complete -c salt             -x      -l state-output         -d "Override the configured state_output value for minion output. Default: full"
complete -c salt             -f -s s -l static               -d "Return the data from minions as a group after they all return."
complete -c salt             -x      -l subset               -d "Execute the routine on a random subset of the targeted minions. The minions will be verified that they have the named function before executing"
complete -c salt             -f      -l summary              -d "Display summary information about a salt command"
complete -c salt             -x      -l username             -d "Username for external authentication"
complete -c salt             -f -s v -l verbose              -d "Turn on command verbosity, display jid and active job queries"

# salt arguments
# minions
complete -c salt         -f -n                                   'not __fish_salt_extract_minion'   -a '(__fish_salt_list_minion accepted)'                              -d 'Minion'
# functions
complete -c salt         -f -n '__fish_salt_extract_minion;   and not __fish_salt_extract_function' -a '(__fish_salt_list_function)'                                     -d 'Function'
# arguments names
complete -c salt         -f -n '__fish_salt_extract_function'                                       -a '(__fish_salt_list_arg_name)'                                     -d 'Argument'
# arguments values
complete -c salt         -f -n '__fish_salt_extract_function'                                       -a '(__fish_salt_list_arg_value | __fish_salt_prefix_with_arg_name)'
