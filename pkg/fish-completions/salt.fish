# salt completion for fish shell
# Written by Roman Inflianskas (infroma@gmail.com)
#
# LICENSE:
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# README:
# Completion lines are structured as a table to make it easier edit them with
# vim or similar editors. Long lines (that are longer than the completion line
# until "-d 'help message'" are splitted.
# Completion lines are sorted by groups, in groups they are sorted by long
# option name (by alphabet).
# If you want to add some completions for arguments value you probably want to
# add line into __fish_salt_args_types variable. First column is the name of
# argument (_ is for unnamed arguments), second is the name of the function,
# last one is the type of the completion (you can use any types that have
# corresponding function __fish_salt_list_TYPE).
#
# VERSION:
# Generated from the help of salt programs on commit ad89a752f807d5ea00d3a9b3257d283ef6b69c10
#
# ISSUES:
# TODO: add: salt-api salt-cloud salt-ssh salt-syndic
# TODO: write tests
# TODO: add completion for builtin states
#  BUG: salt-call autocompletion and salt packages not works; it hangs. Ask
#       fish devs?

# common general options (from --help)
set -l salt_programs salt salt-call salt-cp salt-key \
                     salt-master salt-minion salt-run
for program in $salt_programs
	complete -c $program     -f      -l version              -d "show program's version number and exit"
	complete -c $program     -f      -l versions-report      -d "show program's dependencies version number and exit"
	complete -c $program     -f -s h -l help                 -d "show help message and exit"
	complete -c $program     -r -s c -l config-dir           -d "Pass in an alternative configuration directory. Default: /etc/salt"
	# FIX: (log file is different for different programs)
	complete -c $program     -r      -l log-file             -d "Log file path. Default: /var/log/salt/master."
	complete -c $program     -x      -l log-file-level       -d "Logfile logging log level. Default: \"warning\"." -a "all garbage trace debug info warning error critical quiet"
	complete -c $program     -x -s l -l log-level            -d "logging log level. Default: \"warning\"." -a "all garbage trace debug info warning error critical quiet"
end
set -l salt_programs_crash salt salt-call salt-cp \
                           salt-key salt-run
for program in $salt_programs_crash
	complete -c $program     -f      -l hard-crash           -d "Raise any original exception rather than exiting gracefully. Default: False"
end
set -l salt_programs_output_color salt salt-call \
                                  salt-key salt-run
for program in $salt_programs_output_color
	for color in color colour
		complete -c $program -f      -l force-$color         -d "Force colored output"
		complete -c $program -f      -l no-$color            -d "Disable all colored output"
	end
end
set -l salt_programs_output salt salt-call salt-key
for program in $salt_programs_output
	for out in out output
		complete -c $program -x      -l $out                 -d "Print the output from the \"$program\" command using the specified outputter" -a "raw compact no_return grains overstatestage pprint json nested yaml highstate quiet key txt virt_query newline_values_only"
		complete -c $program -r      -l $out-file            -d "Write the output to the specified file"
		complete -c $program -x      -l $out-file-append     -d "Append the output to the specified file"
		complete -c $program -x      -l $out-indent          -d "Print the output indented by the provided value in spaces. Negative values disables indentation. Only applicable in outputters that support indentation."
	end
end
set -l salt_programs_doc salt salt-call salt-run
for program in $salt_programs_doc
	for doc in doc documentation
		complete -c $program -f -s d -l $doc                 -d "Display documentation for runners, pass a runner or runner.function to see documentation on only that runner or function."
	end
end
set -l salt_programs_select salt salt-cp
for program in $salt_programs_select
	complete -c $program     -f -s G -l grain                -d "Instead of using shell globs to evaluate the target use a grain value to identify targets, the syntax for the target is the grain key followed by a globexpression: \"os:Arch*\""
	complete -c $program     -f      -l grain-pcre           -d "Instead of using shell globs to evaluate the target use a grain value to identify targets, the syntax for the target is the grain key followed by a pcre regular expression: \"os:Arch.*\""
	complete -c $program     -f -s L -l list                 -d "Instead of using shell globs to evaluate the target servers, take a comma or space delimited list of servers."
	complete -c $program     -f -s N -l nodegroup            -d "Instead of using shell globs to evaluate the target use one of the predefined nodegroups to identify a list of targets."
	complete -c $program     -f -s E -l pcre                 -d "Instead of using shell globs to evaluate the target servers, use pcre regular expressions"
	complete -c $program     -f -s R -l range                -d "Instead of using shell globs to evaluate the target use a range expression to identify targets. Range expressions look like %cluster"
end
set -l salt_programs_master_minion salt-master \
                                   salt-minion
for program in $salt_programs_master_minion
	complete -c $program     -x -s u -l user                 -d "Specify user to run $program"
	complete -c $program     -f -s d -l daemon               -d "Run the $program as a daemon"
	complete -c $program             -l pid-file             -d "Specify the location of the pidfile. Default: /var/run/$program.pid."
end
function __fish_salt_default_timeout
	echo (echo $argv[1] | sed '
	s/^salt$/5/g;
	s/^salt-call$/60/g;
	s/^salt-cp$/5/g;
	s/^salt-run$/1/g
	')
end
set -l salt_programs_timeout salt salt-call salt-cp \
                             salt-run
for program in $salt_programs_timeout
	complete -c $program     -x -s t -l timeout              -d "Change the timeout, if applicable, for the running command; default="(__fish_salt_default_timeout $program)
end
set -l salt_programs_return salt salt-cp
for program in $salt_programs_return
	complete -c $program     -x      -l return               -d "Set an alternative return method. By default salt will send the return data from the command back to the master, but the return data can be redirected into any number of systems, databases or applications."
end

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
complete -c salt             -f -s T -l make-token           -d "Generate and save an authentication token for re-use. Thetoken is generated and made available for the period defined in the Salt Master."
complete -c salt             -x      -l password             -d "Password for external authentication"
complete -c salt             -f -s I -l pillar               -d "Instead of using shell globs to evaluate the target use a pillar value to identify targets, the syntax for the target is the pillar key followed by a globexpression: "role:production*""
complete -c salt             -f      -l show-timeout         -d "Display minions that timeout without the additional output of --verbose"
complete -c salt             -f      -l show-jid             -d "Display jid without the additional output of --verbose"
complete -c salt             -x      -l state-output         -d "Override the configured state_output value for minion output. Default: full"
complete -c salt             -f -s s -l static               -d "Return the data from minions as a group after they all return."
complete -c salt             -x      -l subset               -d "Execute the routine on a random subset of the targeted minions. The minions will be verified that they have the named function before executing"
complete -c salt             -f      -l summary              -d "Display summary information about a salt command"
complete -c salt             -x      -l username             -d "Username for external authentication"
complete -c salt             -f -s v -l verbose              -d "Turn on command verbosity, display jid and active job queries"

# convinience functions
function __fish_salt_log
	echo $argv >&2
end

function __fish_salt_join
	# remove empty elements
	set a (echo $argv[2..-1] | sed 's/ /\n/g' | grep -Ev '^$')
	set delimiter $argv[1]
	printf "$delimiter%s" $a | cut -c 2-
end

function __fish_salt_clean_prefix
	set prefix '^'$argv[1]
	grep -E $prefix | sed "s/$prefix//g"
end
function __fish_salt_clean
	if [ $argv[1] = yaml ]
		__fish_salt_clean_prefix ' *- '
	else if [ $argv[1] = nested ]
		__fish_salt_clean_prefix '  *'
	end
end

# information extraction from commandline
function __fish_salt_program
	set result (commandline -pco)
	if [ (count $result) -gt 0 ]
		set result $result[1]
	else
		set result salt
	end
	echo $result
end

function __fish_salt_ignore_args
	set -l cli (commandline -pco) 
	for i in $cli
		if echo "$i" | grep -Ev (__fish_salt_join '|' $argv)
			set -g $argv[1] $i
			return 0
		end
	end
	return 1
end

set __fish_salt_base_ignores (__fish_salt_join '|' $salt_programs '^-.*')
function __fish_salt_ignores_minion
	echo $__fish_salt_base_ignores
end
function __fish_salt_extract_minion
	__fish_salt_ignore_args __fish_salt_extracted_minion (__fish_salt_ignores_minion)
end
function __fish_salt_minion
	__fish_salt_extract_minion > /dev/null
	echo $__fish_salt_extracted_minion
end

function __fish_salt_ignores_function
	__fish_salt_join '|' $__fish_salt_base_ignores (__fish_salt_minion)
end
function __fish_salt_extract_function
	__fish_salt_ignore_args __fish_salt_extracted_function (__fish_salt_ignores_function)
end
function __fish_salt_function
	__fish_salt_extract_function > /dev/null
	echo $__fish_salt_extracted_function
end

set __fish_salt_arg_name_re '\w*='
function __fish_salt_arg_name
	set result (echo (commandline -ct) | grep -E --only-matching $__fish_salt_arg_name_re)
	if test -z $result
		set result '_='
	end
	echo $result | sed 's/=$//g'
end
function __fish_salt_arg_value
	echo (commandline -ct) | sed "s/$__fish_salt_arg_name_re//g"
end

# getting info from salt
set -g __fish_salt_format_options --no-color

function __fish_salt_exec
	set -l program (__fish_salt_program)
	set -l exe $program $__fish_salt_format_options $__fish_salt_format_options_temp  
	if [ $program = salt ]
		set exe $exe (__fish_salt_minion)
	end
	eval $exe $argv
end
function __fish_salt_exec_output
	set -g __fish_salt_format_options_temp "--output=$argv[1]"
	__fish_salt_exec $argv[2..-1]
	set -e __fish_salt_format_options_temp
end

function __fish_salt_list
	begin
		for arg_type in $argv
			set f_list '__fish_salt_list_'$arg_type
			eval $f_list
		end
	end
end

set -g __fish_salt_args_types '
_                             cp.get_dir                      : master_file
_                             cp.get_dir                      : minion_file
path                          cp.get_dir                      : master_file
dest                          cp.get_dir                      : minion_file
_                             cp.get_file                     : master_file
_                             cp.get_file                     : minion_file
path                          cp.get_file                     : master_file
dest                          cp.get_file                     : minion_file
_                             file.copy                       : minion_file
src                           file.copy                       : minion_file
dst                           file.copy                       : minion_file
_                             grains.append                   : grain
key                           grains.append                   : grain
_                             grains.delval                   : grain
key                           grains.delval                   : grain
_                             grains.get                      : grain
key                           grains.get                      : grain
_                             grains.get_or_set_hash          : grain
name                          grains.get_or_set_hash          : grain
_                             grains.has_value                : grain
key                           grains.has_value                : grain
_                             grains.item                     : grain
_                             grains.items                    : grain
_                             grains.remove                   : grain
key                           grains.remove                   : grain
_                             grains.setval                   : grain
key                           grains.setval                   : grain
exclude                       state.highstate                 : state
_                             state.sls                       : state
_                             state.show_sls                  : state
_                             state.sls                       : state
exclude                       state.sls                       : state
_                             sys.argspec                     : function
_                             sys.argspec                     : module
module                        sys.argspec                     : module
_                             sys.doc                         : function
_                             sys.doc                         : module
'
#_                             pkg.remove                      : package

function __fish_salt_list_arg_name
	__fish_salt_exec_output yaml sys.argspec (__fish_salt_function) | grep -A1024 '^ *args:' | grep -B1024 '^ *defaults:' | grep -v ':' | __fish_salt_clean yaml | sed 's/$/=/g'
end
function __fish_salt_list_arg_value
	set arg_path (__fish_salt_arg_name)' *'(__fish_salt_function)' *: *'
	set arg_types (echo $__fish_salt_args_types | __fish_salt_clean_prefix $arg_path)
	__fish_salt_list $arg_types
end
function __fish_salt_list_function
	 __fish_salt_exec_output yaml sys.list_functions $argv | __fish_salt_clean yaml
end
function __fish_salt_list_grain
	 __fish_salt_exec_output yaml grains.ls $argv | __fish_salt_clean yaml
end
function __fish_salt_list_master_file_abs
	__fish_salt_exec_output yaml cp.list_master | __fish_salt_clean yaml
end
function __fish_salt_list_master_file
	__fish_salt_list_master_file_abs | sed 's/^/salt:\/\//g'
end
function __fish_salt_list_minion
	salt-key --no-color --list=$argv[1] | grep -Ev '^(Accepted|Unaccepted|Rejected) Keys:$'
end
function __fish_salt_list_minion_file
	if [ (count $argv) -eq 0 ]
		set file (__fish_salt_arg_value)
	else
		set file $argv[1]
	end
	set exe '"ls --directory --file-type '$file'* 2> /dev/null"'
	__fish_salt_exec_output nested cmd.run $exe | __fish_salt_clean nested
end
function __fish_salt_list_module
	__fish_salt_exec_output yaml sys.list_modules $argv | __fish_salt_clean yaml
end
function __fish_salt_list_package
	__fish_salt_exec_output yaml pkg.list_pkgs $argv | __fish_salt_clean yaml | sed 's/:.*//g'
end
function __fish_salt_list_state
	__fish_salt_list_master_file_abs | grep '.sls' | sed 's/\//./g;s/\.init\.sls/.sls/g;s/\.sls//g'
end

function __fish_salt_prefix_with_arg_name
	set arg_name (__fish_salt_arg_name)
	if [ $arg_name != '_' ]
		sed "p;s/^/$arg_name=/g"
	else
		# leave stdout as is; don't remove this line, because if construction 
		# clears stdout if condition fails
		tee
	end
end


# salt
# minions
complete -c salt         -f -n                                   'not __fish_salt_extract_minion'   -a '(__fish_salt_list_minion accepted)'
# functions
complete -c salt         -f -n '__fish_salt_extract_minion;   and not __fish_salt_extract_function' -a '(__fish_salt_list_function)'
# arguments and name values
complete -c salt         -f -n '__fish_salt_extract_function'                                       -a '(__fish_salt_list_arg_name) (__fish_salt_list_arg_value | __fish_salt_prefix_with_arg_name)'
