.. option:: -C, --compound

    Utilize many target definitions to make the call very granular. This option
    takes a group of targets separated by ``and`` or ``or``. The default matcher is a
    glob as usual. If something other than a glob is used, preface it with the
    letter denoting the type; example: 'webserv* and G@os:Debian or E@db*'
    Make sure that the compound target is encapsulated in quotes.

.. option:: -I, --pillar

    Instead of using shell globs to evaluate the target, use a pillar value to
    identify targets. The syntax for the target is the pillar key followed by
    a glob expression: "role:production*"

.. option:: -S, --ipcidr

    Match based on Subnet (CIDR notation) or IPv4 address.
