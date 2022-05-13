/*
multiline
comment
*/
CREATE TABLE test_update (a INT); # end of line comment
# example comment
insert into test_update values (1); -- ending comment
-- another comment type
update test_update set a=2 where a=1;
