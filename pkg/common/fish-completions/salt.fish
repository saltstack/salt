# salt.fish - Fish shell completions for salt
# Source common helper functions
source (dirname (status filename))"/salt_common.fish"

complete -c salt -s 'h' -l 'help' -d 'Show help message'
complete -c salt -s 'c' -l 'config-dir' -d 'Configuration directory' -r -f
complete -c salt -s 't' -l 'timeout' -d 'Timeout in seconds' -r -f
complete -c salt -s 'v' -l 'version' -d 'Show version'
complete -c salt -s 'V' -l 'versions-report' -d 'Show versions report'
complete -c salt -l 'log-level' -d 'Logging level' -r -f -a "all garbage trace debug info warning error critical quiet"
complete -c salt -l 'log-file' -d 'Log file path' -r -f
complete -c salt -l 'return' -d 'Returner module' -r -f -a "(salt-run -h 2>/dev/null | grep -oP '(?<=return: )[^ ]+' | tr ',' '\n')"
complete -c salt -l 'out' -d 'Outputter' -r -f -a "(salt-run -h 2>/dev/null | grep -oP '(?<=out: )[^ ]+' | tr ',' '\n')"
# Minion completion
complete -c salt -n '__fish_is_nth_token 1' -xa '(__fish_salt_extract_minion)' -d 'Minion ID'
# Function completion
complete -c salt -n '__fish_is_nth_token 2' -xa '(__fish_salt_extract_function)' -d 'Salt function'
