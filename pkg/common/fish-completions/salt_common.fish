# salt-call completion for fish shell
# This file contains common options and helper functions.

# README:
# Completion lines are structured as a table to make it easier edit them with
# vim or similar editors. Long lines (that are longer than the completion line
# until "-d 'help message'") are splitted. Descriptions are not splitted.
# TAB width is set to 4 chars!
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
# TODO: #1 add: salt-api salt-cloud salt-ssh
# TODO: #2 write tests (use https://github.com/terlar/fish-tank)
# TODO: #3 add completion for builtin states
# TODO: #4 use caching (see https://github.com/saltstack/salt/issues/15321)
# TODO: #5 add help to the positional arguments (like '(Minion)', '(Grain)')
# using __fish_salt_list function everythere)
# TODO: #6 add minion selection by grains (call "salt '*' grains.ls", use #4)
#  BUG: #7 salt-call autocompletion and salt packages not works; it hangs. Ask
#       fish devs?
# TODO: #8 sort with `sort` or leave as is?

# common general options (from --help)
set -l salt_programs \
salt salt-call salt-cp salt-key salt-master salt-minion \
salt-run salt-syndic
for program in $salt_programs
	complete -c $program     -f      -l version              -d "show program's version number and exit"
	complete -c $program     -f      -l versions-report      -d "show program's dependencies version number and exit"
	complete -c $program     -f -s h -l help                 -d "show help message and exit"
	complete -c $program     -r -s c -l config-dir           -d "Pass in an alternative configuration directory. Default: /etc/salt"
	# BUG: (log file is different for different programs)
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
	complete -c $program     -f -s L -l list                 -d "Instead of using shell globs to evaluate the target servers, take a comma or whitespace delimited list of servers."
	complete -c $program     -f -s N -l nodegroup            -d "Instead of using shell globs to evaluate the target use one of the predefined nodegroups to identify a list of targets."
	complete -c $program     -f -s E -l pcre                 -d "Instead of using shell globs to evaluate the target servers, use pcre regular expressions"
	complete -c $program     -f -s R -l range                -d "Instead of using shell globs to evaluate the target use a range expression to identify targets. Range expressions look like %cluster"
end
set -l salt_programs_user_daemon_pidfile \
salt-master salt-minion salt-syndic
for program in $salt_programs_user_daemon_pidfile
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

set -g __fish_salt_max_line_count_in_yaml_block 1024

function __fish_salt_lines_between
	set max $__fish_salt_max_line_count_in_yaml_block
	grep -A$max $argv[1] | grep -B$max $argv[2]
end

function __fish_salt_extract_first_yaml_block
	set max $__fish_salt_max_line_count_in_yaml_block
	sed '1d' | sed '$a\  stop' | grep -m 1 -B$max '^  \w' | sed '$d'
end

function __fish_salt_add_help
	sed "s/\$/\t$argv/"
end

function __fish_salt_underscore_to_space
	sed 's/^\w/\u&/g; s/_/ /g'
end

# information extraction from commandline

set -g __fish_salt_default_program 'salt'

# BUG: Completion doesn't work with correct commandline like
# salt --out raw server test.ping
# Consider rewriting using __fish_complete_subcommand
function __fish_salt_program
	if status --is-interactive
		set result (commandline -pco)
		if test -n "$result"
			if [ $result[1] = 'salt-call' ]; and contains -- '--local' $result
				set options '--local'
			end
			set result $result[1] $options
		end
	end
	set result $__fish_salt_default_program
	echo $result
end

function __fish_salt_save_first_commandline_token_not_matching_args_to
	if status --is-interactive
		set -l cli (commandline -pco)
		for i in $cli
			if echo "$i" | grep -Ev (__fish_salt_join '|' $argv)
				set -g $argv[1] $i
				return 0
			end
		end
	end
	return 1
end

function __fish_salt_commandline_tokens_not_matching_args
	if status --is-interactive
		set tokens (commandline -pco)
		set result 1
		for token in $tokens
			if echo "$token" | grep -Ev (__fish_salt_join '|' $argv)
				set result 0
			end
		end
	end
	return $result
end

set __fish_salt_base_ignores (__fish_salt_join '|' $salt_programs '^-.*')

function __fish_salt_ignores_minion
	echo $__fish_salt_base_ignores
end

function __fish_salt_extract_minion
	__fish_salt_save_first_commandline_token_not_matching_args_to __fish_salt_extracted_minion (__fish_salt_ignores_minion)
end

function __fish_salt_minion
	__fish_salt_extract_minion > /dev/null
	echo $__fish_salt_extracted_minion
end

function __fish_salt_ignores_function
	__fish_salt_join '|' $__fish_salt_base_ignores (__fish_salt_minion)
end

function __fish_salt_extract_function
	__fish_salt_save_first_commandline_token_not_matching_args_to __fish_salt_extracted_function (__fish_salt_ignores_function)
end

function __fish_salt_function
	__fish_salt_extract_function > /dev/null
	echo $__fish_salt_extracted_function
end

function __fish_salt_ignores_args
	__fish_salt_join '|' (__fish_salt_ignores_function) (__fish_salt_function)
end

function __fish_salt_args
	__fish_salt_commandline_tokens_not_matching_args (__fish_salt_ignores_args)
end

set __fish_salt_arg_name_re '\w*='

function __fish_salt_arg_name
	set result (commandline -ct | grep -E --only-matching $__fish_salt_arg_name_re)
	if test -z $result
		set result '_='
	end
	echo $result | sed 's/=$//g'
end

function __fish_salt_arg_value
	commandline -ct | sed "s/$__fish_salt_arg_name_re//g"
end

function __fish_salt_arg_value_by_name
	set arg_name "$argv="
	__fish_salt_args | __fish_salt_clean_prefix $arg_name
end

# getting info from salt
set -g __fish_salt_format_options --no-color --log-level=quiet

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

function __fish_salt_exec_and_clean
	__fish_salt_exec_output $argv | __fish_salt_clean $argv[1]
end

function __fish_salt_list
	begin
		for arg_type in $argv
			set f_list '__fish_salt_list_'$arg_type
			eval $f_list | __fish_salt_add_help (echo $arg_type | __fish_salt_underscore_to_space)
		end
	end
end

set -g __fish_salt_args_types '
_                             cmd.retcode                     : minion_cmd
cmd                           cmd.retcode                     : minion_cmd
shell                         cmd.retcode                     : minion_file
_                             cmd.run                         : minion_cmd
cmd                           cmd.run                         : minion_cmd
shell                         cmd.run                         : minion_file
_                             cmd.run_all                     : minion_cmd
cmd                           cmd.run_all                     : minion_cmd
shell                         cmd.run_all                     : minion_file
_                             cmd.run_stderr                  : minion_cmd
cmd                           cmd.run_stderr                  : minion_cmd
shell                         cmd.run_stderr                  : minion_file
_                             cmd.run_stdout                  : minion_cmd
cmd                           cmd.run_stdout                  : minion_cmd
shell                         cmd.run_stdout                  : minion_file
shell                         cmd.script                      : minion_file
shell                         cmd.script_retcode              : minion_file
_                             cmd.which                       : minion_cmd
cmd                           cmd.which                       : minion_cmd
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

function __fish_salt_argspec_function
	set function_line '^\s*'$argv[1]:
	set max $__fish_salt_max_line_count_in_yaml_block
	grep -A$max $function_line | __fish_salt_extract_first_yaml_block
end

function __fish_salt_argspec_args
	__fish_salt_lines_between '^\s*args:' '^\s*defaults:' | grep -v ':'
end

function __fish_salt_list_arg_name
	__fish_salt_exec_output yaml sys.argspec (__fish_salt_function) | __fish_salt_argspec_function (__fish_salt_function) | __fish_salt_argspec_args | __fish_salt_clean yaml | sed 's/$/=/g'
end

function __fish_salt_list_arg_value
	set arg_path_re (__fish_salt_arg_name)'\s*'(__fish_salt_function)'\s*:\s*'
	set arg_types (echo $__fish_salt_args_types | __fish_salt_clean_prefix $arg_path_re)
	__fish_salt_list $arg_types
end

function __fish_salt_list_function
	__fish_salt_exec_and_clean yaml sys.list_functions $argv
end

function __fish_salt_list_grain
	 __fish_salt_exec_and_clean yaml grains.ls $argv
end

function __fish_salt_list_master_file_abs
	__fish_salt_exec_and_clean yaml cp.list_master
end

function __fish_salt_list_master_file
	__fish_salt_list_master_file_abs | sed 's/^/salt:\/\//g'
end

function __fish_salt_list_minion
	salt-key --no-color --list=$argv[1] | grep -Ev '^(Accepted|Unaccepted|Rejected) Keys:$'
end

function __fish_salt_list_minion_cmd
	set cmd (__fish_salt_arg_value | sed 's/^[\'"]//')
	set complete_cmd_exe '"complete --do-complete=\''$cmd'\'"'
	set cmd_without_last_word (echo $cmd | sed -E 's/\S*$//')
	# BUG: Static paths. Do we need to use which?
	set bash_shell '/bin/bash'
	set fish_shell '/usr/bin/fish'
	set sh_shell '/bin/sh'
	set zsh_shell '/usr/bin/zsh'
	set shell (__fish_salt_arg_value_by_name shell); and test -z $shell; and set shell $sh_shell
	switch $shell
		case $fish_shell
			__fish_salt_exec_and_clean nested cmd.run shell=$fish_shell cmd=$complete_cmd_exe | awk -v prefix="$cmd_without_last_word" '{print prefix $0}'
		case $bash_shell $zsh_shell
			# Not implemented; See
			# https://github.com/fish-shell/fish-shell/issues/1679#issuecomment-55487388
		case $sh_shell
			# sh doesn't have completions
	end
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
	__fish_salt_exec_and_clean yaml sys.list_modules $argv
end

function __fish_salt_list_package
	__fish_salt_exec_and_clean yaml pkg.list_pkgs $argv | sed 's/:.*//g'
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
