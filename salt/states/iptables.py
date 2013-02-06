'''
Management of iptables.
=======================

Insert any arbitrary iptables rule with the insert function:

.. code-block:: yaml

    tcp-22:
        iptables.insert:
            - table: filter
            - rule: INPUT -p tcp -m state --state NEW -m tcp --dport 22 -j ACCEPT
'''

def insert(
        name,
        table="filter",
        chain="INPUT",
        rule=None,
        ):
    '''
    Verify that a rule is inserted
    
    name
        The rule comment. Used for checking if the rule is already loaded
    
    table
        The table to load the rule in
    
    rule
        The IPTables rule to load
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not rule:
        ret['result'] = False
        ret['comment'] = 'Rule needs to be specified'
        return ret
    
    iptables_data = __salt__['iptables.get_saved_rules']()
    if not name in iptables_data[table][chain]['rules_comment']:
        run_rule='{0} {1} -m comment --comment {2}'.format(chain,rule,name)
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'State iptables inserted rule -t {0} -I {1}'.format(table,run_rule)
            return ret
        __salt__['iptables.insert'](table,run_rule)
        ret['comment'] = 'Inserted rule -t {0} -I {1}'.format(table,run_rule)
        ret['changes']['insert'] = name
    else:
      ret['comment'] = '{0} already installed'.format(name)
    return ret

def append(
        name,
        table="filter",
        chain="INPUT",
        rule=None,
        ):
    '''
    Verify that a rule is appended
    
    name
        The rule comment. Used for checking if the rule is already loaded
    
    table
        The table to load the rule in
    
    rule
        The IPTables rule to load
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not rule:
        ret['result'] = False
        ret['comment'] = 'Rule needs to be specified'
        return ret
    
    iptables_data = __salt__['iptables.get_saved_rules']()
    if not name in iptables_data[table][chain]['rules_comment']:
        run_rule='{0} {1} -m comment --comment {2}'.format(chain,rule,name)
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'State iptables appended rule -t {0} -A {1}'.format(table,run_rule)
            return ret
        __salt__['iptables.append'](table,run_rule)
        ret['comment'] = 'Inserted rule -t {0} -A {1}'.format(table,run_rule)
        ret['changes']['append'] = name
    else:
      ret['comment'] = '{0} already installed'.format(name)
    return ret

def save(
        name,
        ):
    '''
    Save the rules file
    
    name
        Path to the file to save the rules in
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'State iptables saved rules to {0}'.format(name)
        return ret
    
    __salt__['iptables.save'](name)
    ret['comment'] = 'Saved to {0}'.format(name)
    ret['changes']['saved'] = name
    return ret
