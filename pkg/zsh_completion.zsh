#compdef salt salt-call salt-cp
# The use-cache style is checked in a few places to allow caching minions, modules,
# or the directory salt is installed in.
# you can cache those three with:
# zstyle ':completion:*:salt(|-cp|-call):*' use-cache true
# or selectively:
# zstyle ':completion::complete:salt(|-cp|-call):minions:'  use-cache true
# zstyle ':completion::complete:salt(|-cp|-call):modules:'  use-cache true
# zstyle ':completion::complete:salt(|-cp|-call):salt_dir:' use-cache true


local state line curcontext="$curcontext" salt_dir cachefn

_modules(){
    local _funcs cachefn expl curcontext=${curcontext%:*}:modules

    zstyle -s ":completion:$curcontext:" cache-policy cachefn
    if [[ -z $cachefn ]]; then
        zstyle ":completion:$curcontext:" cache-policy _salt_caching_policy
    fi

    if _cache_invalid salt/modules || ! _retrieve_cache salt/modules; then
        _funcs=( ${(M)${(f)"$(command salt-call --local -d 2>/dev/null)"}##[[:alnum:]._]##} )
        _store_cache salt/modules _funcs
    fi

    _wanted modules expl modules _multi_parts "$@" . _funcs
}

_minions(){
    local _peons cachefn expl curcontext=${curcontext%:*}:minions

    zstyle -s ":completion:$curcontext:" cache-policy cachefn
    if [[ -z $cachefn ]]; then
        zstyle ":completion:$curcontext:" cache-policy _salt_caching_policy
    fi

    if _cache_invalid salt/minions || ! _retrieve_cache salt/minions; then
        _peons=( ${(f)"$(command salt-key -l acc 2>/dev/null)"} )
        _peons[(I)Accepted[[:space:]]Keys:]=()
        _store_cache salt/minions _peons
    fi

    _wanted minions expl minions compadd "$@" -a _peons
}

(( $+functions[_salt_caching_policy] )) ||
_salt_caching_policy() {
    local -a oldp
    oldp=( "$1"(Nm+7) )
    (( $#oldp ))
}

local -a _{target,master,logging,minion}_options _{common,out}_opts _target_opt_pat
_target_opt_pat=(
  '(-[ELGNRCIS]|--(pcre|list|grain(|-pcre)|nodegroup|range|compound|pillar|ipcidr))'
  '(-E --pcre -L --list -G --grain --grain-pcre -N --nodegroup -R --range -C --compound -I --pillar -S --ipcidr)'
)

_target_options=(
    "$_target_opt_pat[2]"{-E,--pcre}'[use pcre regular expressions]:pcre:'
    "$_target_opt_pat[2]"{-L,--list}'[take a comma or space delimited list of servers.]:list:'
    "$_target_opt_pat[2]"{-G,--grain}'[use a grain value to identify targets]:Grains:'
    "$_target_opt_pat[2]--grain-pcre[use a grain value to identify targets.]:pcre:"
    "$_target_opt_pat[2]"{-N,--nodegroup}'[use one of the predefined nodegroups to identify a list of targets.]:Nodegroup:'
    "$_target_opt_pat[2]"{-R,--range}'[use a range expression to identify targets.]:Range:'
    "$_target_opt_pat[2]"{-C,--compound}'[Use multiple targeting options.]:Compound:'
    "$_target_opt_pat[2]"{-I,--pillar}'[use a pillar value to identify targets.]:Pillar:'
    "$_target_opt_pat[2]"{-S,--ipcidr}'[Match based on Subnet (CIDR notation) or IPv4 address.]:Cidr:'
)

_common_opts=(
    "--version[show program's version number and exit]"
    "--versions-report[show program's dependencies version number and exit]"
    '(-h --help)'{-h,--help}'[show this help message and exit]'
    '(-c --config-dir)'{-c,--config-dir}'[Pass in an alternative configuration directory.(default: /etc/salt/)]:Config Directory:_files -/'
    '(-t --timeout)'{-t,--timeout}'[Change the timeout for the running command; default=5]:Timeout (seconds):'
)

_master_options=(
    '(-s --static)'{-s,--static}'[Return the data from minions as a group after they all return.]'
    "--async[Run the salt command but don't wait for a reply]"
    '(--state-output --state_output)'{--state-output,--state_output}'[Override the configured state_output value for minion output. Default: full]:Outputs:(full terse mixed changes)'
    '--subset[Execute the routine on a random subset of the targeted minions]:Subset:'
    '(-v --verbose)'{-v,--verbose}'[Turn on command verbosity, display jid and active job queries]'
    '--hide-timeout[Hide minions that timeout]'
    '(-b --batch --batch-size)'{-b,--batch,--batch-size}'[Execute the salt job in batch mode, pass number or percentage to batch.]:Batch Size:'
    '(-a --auth --eauth --extrenal-auth)'{-a,--auth,--eauth,--external-auth}'[Specify an external authentication system to use.]:eauth:'
    '(-T --make-token)'{-T,--make-token}'[Generate and save an authentication token for re-use.]'
    '--return[Set an alternative return method.]:Returners:_path_files -W "$salt_dir/returners" -g "[^_]*.py(\:r)"'
    '(-d --doc --documentation)'{-d,--doc,--documentation}'[Return the documentation for the specified module]:Module:_path_files -W "$salt_dir/modules" -g "[^_]*.py(\:r)"'
    '--args-separator[Set the special argument used as a delimiter between command arguments of compound commands.]:Arg separator:'
)

_minion_options=(
    '--return[Set an alternative return method.]:Returners:_path_files -W "$salt_dir"/returners" -g "[^_]*.py(\:r)"'
    '(-d --doc --documentation)'{-d,--doc,--documentation}'[Return the documentation for the specified module]:Module:_path_files -W "$salt_dir/modules" -g "[^_]*.py(\:r)"'
    '(-g --grains)'{-g,--grains}'[Return the information generated by the salt grains]'
    {*-m,*--module-dirs}'[Specify an additional directory to pull modules from.]:Module Dirs:_files -/'
    '--master[Specify the master to use.]:Master:'
    '--local[Run salt-call locally, as if there was no master running.]'
    '--file-root[Set this directory as the base file root.]:File Root:_files -/'
    '--pillar-root[Set this directory as the base pillar root.]:Pillar Root:_files -/'
    '--retcode-passthrough[Exit with the salt call retcode and not the salt binary retcode]'
    '--id[Specify the minion id to use.]:Minion ID:'
    '--skip-grains[Do not load grains.]'
    '--refresh-grains-cache[Force a refresh of the grains cache]'
)

_logging_options=(
    '(-l --log-level)'{-l,--log-level}'[Console logging log level.(default: warning)]:Log Level:(all garbage trace debug info warning error critical quiet)'
    '--log-file[Log file path. Default: /var/log/salt/master.]:Log File:_files'
    '--log-file-level=[Logfile logging log level.Default: warning]:Log Level:(all garbage trace debug info warning error critical quiet)'
)

_out_opts=(
    '(--out --output)'{--out,--output}'[Print the output using the specified outputter.]:Outputters:_path_files -W "$salt_dir/output" -g "[^_]*.py(\:r)"'
    '(--out-indent --output-indent)'{--out-indent,--output-indent}'[Print the output indented by the provided value in spaces.]:Number:'
    '(--out-file --output-file)'{--out-file,--output-file}'[Write the output to the specified file]:Output File:_files'
    '(--no-color --no-colour)'{--no-color,--no-colour}'[Disable all colored output]'
    '(--force-color --force-colour)'{--force-color,--force-colour}'[Force colored output]'
)

_salt_comp(){
    case "$service" in
        salt)
            _arguments -C \
                "${words[(r)$_target_opt_pat[1]]+!}:minions:_minions" \
                ':modules:_modules' \
                "$_target_options[@]" \
                "$_common_opts[@]" \
                "$_master_options[@]" \
                "$_logging_options[@]" \
                "$_out_opts[@]"
            ;;
        salt-call)
            _arguments -C \
                ':modules:_modules' \
                "$_minion_options[@]" \
                "$_common_opts[@]" \
                "$_logging_options[@]" \
                "$_out_opts[@]"
            ;;
        salt-cp)
            _arguments -C \
                "${words[(r)$_target_opt_pat[1]]+!}:minions:_minions" \
                "$_target_options[@]" \
                "$_common_opts[@]" \
                "$_logging_options[@]" \
                ':Source File:_files' \
                ':Destination File:_files'
            ;;
    esac
}

() {
    local curcontext=${curcontext%:*}:salt_dir
    zstyle -s ":completion:$curcontext:" cache-policy cachefn
    if [[ -z $cachefn ]]; then
        zstyle ":completion:${curcontext%:*}:salt_dir:" cache-policy _salt_caching_policy
    fi

    if _cache_invalid salt/salt_dir || ! _retrieve_cache salt/salt_dir; then
        salt_dir="${$(python2 -c 'import salt; print(salt.__file__);')%__init__*}"
        _store_cache salt/salt_dir salt_dir
    fi
}

_salt_comp "$@"
