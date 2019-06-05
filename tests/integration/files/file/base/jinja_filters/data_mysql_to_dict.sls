{% set test_mysql_output =  ['+----+------+-----------+------+---------+------+-------+------------------+',
                             '| Id | User | Host      | db   | Command | Time | State | Info             |',
                             '+----+------+-----------+------+---------+------+-------+------------------+',
                             '|  7 | root | localhost | NULL | Query   |    0 | init  | show processlist |',
                             '+----+------+-----------+------+---------+------+-------+------------------+'] %}

{% set result = test_mysql_output | mysql_to_dict('Info') %}

{% include 'jinja_filters/common.sls' %}
