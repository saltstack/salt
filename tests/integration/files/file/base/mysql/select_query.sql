CREATE TABLE test_select (a INT);
insert into test_select values (1);
insert into test_select values (3);
insert into test_select values (4);
insert into test_select values (5);
update test_select set a=2 where a=1;
select * from test_select;
