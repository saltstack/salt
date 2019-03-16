CREATE TABLE test_update (a INT);
insert into test_update values (1);
update test_update set a=2 where a=1;
