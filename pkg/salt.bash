# written by David Pravec
#   - feel free to /msg alekibango on IRC if you want to talk about this file

# TODO: check if --config|-c was used and use configured config file for queries
# TODO: solve somehow completion for  salt -G pythonversion:[tab]
#       (not sure what to do with lists)
# TODO: --range[tab] --   how?
# TODO: --compound[tab] -- how?
# TODO: use history to extract some words, esp. if ${cur} is empty
# TODO: TEST EVERYTHING a lot
# TODO: cache results of some functions?  where? how long?
# TODO: is it ok to use '--timeout 2' ?


_salt_get_grains(){
    if [ "$1" = 'local' ] ; then
        salt-call --out=txt -- grains.ls | sed  's/^.*\[//' | tr -d ",']" |sed 's:\([a-z0-9]\) :\1\: :g'
    else
      salt '*' --timeout 2 --out=txt -- grains.ls | sed  's/^.*\[//' | tr -d ",']" |sed 's:\([a-z0-9]\) :\1\: :g'
    fi
}

_salt_get_grain_values(){
    if [ "$1" = 'local' ] ; then
        salt-call --out=txt -- grains.item $1 |sed 's/^\S*:\s//' |grep -v '^\s*$'
    else
        salt '*' --timeout 2 --out=txt -- grains.item $1 |sed 's/^\S*:\s//' |grep -v '^\s*$'
    fi
}


_salt(){
    local cur prev opts _salt_grains _salt_coms pprev ppprev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    if [ ${COMP_CWORD} -gt 2 ]; then
	pprev="${COMP_WORDS[COMP_CWORD-2]}"
    fi
    if [ ${COMP_CWORD} -gt 3 ]; then
	ppprev="${COMP_WORDS[COMP_CWORD-3]}"
    fi

    opts="-h --help -d --doc --documentation --version --versions-report -c \
          --config-dir= -v --verbose -t --timeout= -s --static -b --batch= \
          --batch-size= -E --pcre -L --list -G --grain --grain-pcre -N \
          --nodegroup -R --range -C --compound -I --pillar \
          --return= -a --auth= --eauth= --extended-auth= -T --make-token -S \
          --ipcidr --out=pprint --out=yaml --out=overstatestage --out=json \
          --out=raw --out=highstate --out=key --out=txt --no-color --out-indent= "

    if [[ "${cur}" == -* ]] ; then
        COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
        return 0
    fi

    # 2 special cases for filling up grain values
    case "${pprev}" in
    -G|--grain|--grain-pcre)
    if [ "${cur}" = ":" ]; then
        COMPREPLY=($(compgen -W "`_salt_get_grain_values ${prev}`"  ))	
        return 0
    fi
    ;;
    esac
    case "${ppprev}" in
    -G|--grain|--grain-pcre)
        if [ "${prev}" = ":" ]; then
        COMPREPLY=( $(compgen -W "`_salt_get_grain_values ${pprev}`" -- ${cur}) )
        return 0
        fi
    ;;
    esac

    if [ "${cur}" = "=" ] && [[ "${prev}" == --* ]]; then
       cur=""
    fi
    if [ "${prev}" = "=" ] && [[ "${pprev}" == --* ]]; then
       prev="${pprev}"
    fi

   case "${prev}" in

     -c|--config)
        COMPREPLY=($(compgen -f -- ${cur}))
        return 0
        ;;
     salt)
        COMPREPLY=($(compgen -W "\'*\' ${opts} `salt-key --no-color -l acc`" -- ${cur}))
        return 0
        ;;
     -E|--pcre)
        COMPREPLY=($(compgen -W "`salt-key --no-color -l acc`" -- ${cur}))
        return 0
        ;;
     -G|--grain|--grain-pcre)
        COMPREPLY=($(compgen -W "$(_salt_get_grains)" -- ${cur}))
        return 0
	;;
     -C|--compound)
        COMPREPLY=() # TODO: finish this one? how?
        return 0
        ;;
     -t|--timeout)
        COMPREPLY=($( compgen -W "1 2 3 4 5 6 7 8 9 10 15 20 30 40 60 90 120 180" -- ${cur}))
        return 0
        ;;
     -b|--batch|--batch-size)
        COMPREPLY=($(compgen -W "1 2 3 4 5 6 7 8 9 10 15 20 30 40 50 60 70 80 90 100 120 150 200"))
        return 0
        ;;
     -N|--nodegroup)
	    MASTER_CONFIG='/etc/salt/master'
        COMPREPLY=($(compgen -W "`awk -F ':'  'BEGIN {print_line = 0};  /^nodegroups/ {print_line = 1;getline } print_line && /^  */ {print $1} /^[^ ]/ {print_line = 0}' <${MASTER_CONFIG}`" -- ${cur}))
        return 0
     ;;
    esac

    _salt_coms="$(salt '*' --timeout 2 --out=txt -- sys.list_functions | sed 's/^.*\[//' | tr -d ",']" )"
    all="${opts} ${_salt_coms}"
    COMPREPLY=( $(compgen -W "${all}" -- ${cur}) )

  return 0
}

complete -F _salt salt


_saltkey(){
    local cur prev opts prev pprev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="-c --config-dir= -h --help --version --versions-report -q --quiet \
          -y --yes --gen-keys= --gen-keys-dir= --keysize= --key-logfile= \
          -l --list= -L --list-all -a --accept= -A --accept-all \
          -r --reject= -R --reject-all -p --print= -P --print-all \
          -d --delete= -D --delete-all -f --finger= -F --finger-all \
          --out=pprint --out=yaml --out=overstatestage --out=json --out=raw \
          --out=highstate --out=key --out=txt --no-color --out-indent= "
    if [ ${COMP_CWORD} -gt 2 ]; then
        pprev="${COMP_WORDS[COMP_CWORD-2]}"
    fi
    if [ ${COMP_CWORD} -gt 3 ]; then
        ppprev="${COMP_WORDS[COMP_CWORD-3]}"
    fi
    if [[ "${cur}" == -* ]] ; then
        COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
        return 0
    fi

    if [ "${cur}" = "=" ] && [[ "${prev}" == --* ]]; then
       cur=""
    fi
    if [ "${prev}" = "=" ] && [[ "${pprev}" == --* ]]; then
       prev="${pprev}"
    fi

    case "${prev}" in
     -a|--accept)
        COMPREPLY=($(compgen -W "$(salt-key -l un --no-color; salt-key -l rej --no-color)" -- ${cur}))
        return 0
      ;;
     -r|--reject)
        COMPREPLY=($(compgen -W "$(salt-key -l acc --no-color)" -- ${cur}))
        return 0
        ;;
     -d|--delete)
        COMPREPLY=($(compgen -W "$(salt-key -l acc --no-color; salt-key -l un --no-color; salt-key -l rej --no-color)" -- ${cur}))
        return 0
        ;;
     -c|--config)
        COMPREPLY=($(compgen -f -- ${cur}))
        return 0
        ;;
     --keysize)
        COMPREPLY=($(compgen -W "2048 3072 4096 5120 6144" -- ${cur}))
        return 0
        ;;
     --gen-keys)
        return 0
        ;;
     --gen-keys-dir)
        COMPREPLY=($(compgen -d -- ${cur}))
        return 0
        ;;
     -p|--print)
        COMPREPLY=($(compgen -W "$(salt-key -l acc --no-color; salt-key -l un --no-color; salt-key -l rej --no-color)" -- ${cur}))
        return 0
     ;;
     -l|--list)
        COMPREPLY=($(compgen -W "pre un acc accepted unaccepted rej rejected all" -- ${cur}))
        return 0
     ;;
     --accept-all)
	return 0
     ;;
    esac
    COMPREPLY=($(compgen -W "${opts} " -- ${cur}))
    return 0
}

complete -F _saltkey salt-key

_saltcall(){
    local cur prev opts _salt_coms pprev ppprev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="-h --help -d --doc --documentation --version --versions-report \
          -m --module-dirs= -g --grains --return= --local -c --config-dir= -l --log-level= \
          --out=pprint --out=yaml --out=overstatestage --out=json --out=raw \
          --out=highstate --out=key --out=txt --no-color --out-indent= "
    if [ ${COMP_CWORD} -gt 2 ]; then
        pprev="${COMP_WORDS[COMP_CWORD-2]}"
    fi
    if [ ${COMP_CWORD} -gt 3 ]; then
        ppprev="${COMP_WORDS[COMP_CWORD-3]}"
    fi
    if [[ "${cur}" == -* ]] ; then
        COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
        return 0
    fi

    if [ "${cur}" = "=" ] && [[ ${prev} == --* ]]; then
       cur=""
    fi
    if [ "${prev}" = "=" ] && [[ ${pprev} == --* ]]; then
       prev="${pprev}"
    fi

    case ${prev} in
        -m|--module-dirs)
                COMPREPLY=( $(compgen -d ${cur} ))
		return 0
 	 	;;
	-l|--log-level)
		COMPREPLY=( $(compgen -W "info none garbage trace warning error debug" -- ${cur}))
		return 0
		;;
	-g|grains)
                return 0
		;;
	salt-call)
                COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
	        return 0
		;;
    esac

    _salt_coms="$(salt-call --out=txt -- sys.list_functions|sed 's/^.*\[//' | tr -d ",']"  )"
    COMPREPLY=( $(compgen -W "${opts} ${_salt_coms}" -- ${cur} ))
    return 0
}

complete -F _saltcall salt-call


_saltcp(){
    local cur prev opts target prefpart postpart helper filt pprev ppprev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="-t --timeout= -s --static -b --batch= --batch-size= \
          -h --help --version --versions-report -c --config-dir= \
          -E --pcre -L --list -G --grain --grain-pcre -N --nodegroup \
          -R --range -C --compound -I --pillar \
          --out=pprint --out=yaml --out=overstatestage --out=json --out=raw \
          --out=highstate --out=key --out=txt --no-color --out-indent= "
    if [[ "${cur}" == -* ]] ; then
        COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
        return 0
    fi

    if [ "${cur}" = "=" ] && [[ "${prev}" == --* ]]; then
       cur=""
    fi
    if [ "${prev}" = "=" ] && [[ "${pprev}" == --* ]]; then
       prev=${pprev}
    fi

    case ${prev} in
 	salt-cp)
	    COMPREPLY=($(compgen -W "${opts} `salt-key -l acc --no-color`" -- ${cur}))
	    return 0
	;;
        -t|--timeout)
	    # those numbers are just a hint
            COMPREPLY=($(compgen -W "2 3 4 8 10 15 20 25 30 40 60 90 120 180 240 300" -- ${cur} ))
	    return 0
        ;;
	-E|--pcre)
            COMPREPLY=($(compgen -W "`salt-key -l acc --no-color`" -- ${cur}))
            return 0
	;;
	-L|--list)
	    # IMPROVEMENTS ARE WELCOME
	    prefpart="${cur%,*},"
	    postpart=${cur##*,}
	    filt="^\($(echo ${cur}| sed 's:,:\\|:g')\)$"
            helper=($(salt-key -l acc --no-color | grep -v "${filt}" | sed "s/^/${prefpart}/"))
	    COMPREPLY=($(compgen -W "${helper[*]}" -- ${cur}))

	    return 0
	;;
	-G|--grain|--grain-pcre)
            COMPREPLY=($(compgen -W "$(_salt_get_grains)" -- ${cur}))
            return 0
	    ;;
	    # FIXME
	-R|--range)
	    # FIXME ??
	    return 0
	;;
	-C|--compound)
	    # FIXME ??
	    return 0
	;;
	-c|--config)
	    COMPREPLY=($(compgen -f -- ${cur}))
	    return 0
	;;
    esac

   # default is using opts:
   COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
}

complete -F _saltcp salt-cp
