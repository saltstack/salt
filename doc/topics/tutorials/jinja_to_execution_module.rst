.. _tutorial-jinja_to_execution-module:

=================================================
How to Convert Jinja Logic to an Execution Module
=================================================

.. versionadded: 2016.???

.. note::
    This tutorial assumes a basic knowledge of Salt states and specifically
    experience using the `maps.jinja` idiom.

    This tutorial was written by a salt user who was told "if your maps.jinja
    is too complicated, write an execution module!". If you are experiencing
    over-complicated jinja, read on.

The Problem: Jinja Gone Wild
----------------------------

It is often said in the Salt community that "Jinja is not a Programming Language".
There's an even older saying known as Maslow's hammer.
It goes something like
"if all you have is a hammer, everything looks like a nail".
Jinja is a reliable hammer, and so is the `maps.jinja` idiom.
Unfortunately, it can lead to code that looks like the following.

.. code-block:: jinja

    # storage/maps.yaml

    {% import_yaml 'storage/defaults.yaml' as default_settings %}
    {% set storage = default_settings.storage %}
    {% do storage.update(salt['grains.filter_by']({
        'Debian': {
        },
        'RedHat': {
        }
    }, merge=salt['pillar.get']('storage:lookup'))) %}

    {% if 'VirtualBox' == grains.get('virtual', None) or 'oracle' == grains.get('virtual', None) %}
    {%   do storage.update({'depot_ip': '192.168.33.81', 'server_ip':  '192.168.33.51'}) %}
    {% else %}
    {%   set colo = pillar.get('inventory', {}).get('colo', 'Unknown') %}
    {%   set servers_list = pillar.get('storage_servers', {}).get(colo, [storage.depot_ip, ]) %}
    {%   if opts.id.startswith('foo') %}
    {%     set modulus = servers_list | count %}
    {%     set integer_id = opts.id | replace('foo', '') | int %}
    {%     set server_index = integer_id % modulus %}
    {%   else %}
    {%     set server_index = 0 %}
    {%   endif %}
    {%   do storage.update({'server_ip': servers_list[server_index]}) %}
    {% endif %}

    {% for network, _ in salt.pillar.get('inventory:networks', {}) | dictsort %}
    {%   do storage.ipsets.hash_net.foo_networks.append(network) %}
    {% endfor %}

This is an example from the author's salt formulae demonstrating misuse of jinja.
Aside from being difficult to read and maintain,
accessing the logic it contains from a non-jinja renderer
while probably possible is a significant barrier!

Refactor
--------

The first step is to reduce the maps.jinja file to something reasonable.
This gives us an idea of what the module we are writing needs to do.
There is a lot of logic around selecting a storage server ip.
Let's move that to an execution module.

.. code-block:: jinja

    # storage/maps.yaml

    {% import_yaml 'storage/defaults.yaml' as default_settings %}
    {% set storage = default_settings.storage %}
    {% do storage.update(salt['grains.filter_by']({
        'Debian': {
        },
        'RedHat': {
        }
    }, merge=salt['pillar.get']('storage:lookup'))) %}

    {% if 'VirtualBox' == grains.get('virtual', None) or 'oracle' == grains.get('virtual', None) %}
    {%   do storage.update({'depot_ip': '192.168.33.81'}) %}
    {% endif %}

    {% do storage.update({'server_ip': salt['storage.ip']()}) %}

    {% for network, _ in salt.pillar.get('inventory:networks', {}) | dictsort %}
    {%   do storage.ipsets.hash_net.af_networks.append(network) %}
    {% endfor %}

And then, write the module.
Note how the module encapsulates all of the logic around finding the storage server IP.

.. code-block:: python

    # _modules/storage.py
    #!python

    """
    Functions related to storage servers.
    """

    import re


    def ips():
        """
        Provide a list of all local storage server IPs.

        CLI Example::

            salt \* storage.ips
        """

        if __grains__.get("virtual", None) in ["VirtualBox", "oracle"]:
            return [
                "192.168.33.51",
            ]

        colo = __pillar__.get("inventory", {}).get("colo", "Unknown")
        return __pillar__.get("storage_servers", {}).get(colo, ["unknown"])


    def ip():
        """
        Select and return a local storage server IP.

        This loadbalances across storage servers by using the modulus of the client's id number.

        :maintainer:    Andrew Hammond <ahammond@anchorfree.com>
        :maturity:      new
        :depends:       None
        :platform:      all

        CLI Example::

            salt \* storage.ip

        """

        numerical_suffix = re.compile(r"^.*(\d+)$")
        servers_list = ips()

        m = numerical_suffix.match(__grains__["id"])
        if m:
            modulus = len(servers_list)
            server_number = int(m.group(1))
            server_index = server_number % modulus
        else:
            server_index = 0

        return servers_list[server_index]

Conclusion
----------

That was... surprisingly straight-forward.
Now the logic is available in every renderer, instead of just Jinja.
Best of all, it can be maintained in Python,
which is a whole lot easier than Jinja.
