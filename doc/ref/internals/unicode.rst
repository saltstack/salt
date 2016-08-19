.. __unicode:

===============
Unicode in Salt
===============

Though Unicode handling in large projects can often be complex, Salt adheres to
several basic rules to help developers determine when to use bytes and when to
use Unicode.

(For a basic introduction to this problem, see Ned Batchelder's
`excellent intoroduction to the topic <http://nedbatchelder.com/text/unipain/unipain.html>`.

Salt's basic workflow for string handling is as follows:

1) Salt converts whatever data is passed on CLI/API to Unicode.

2) Modules and various Salt pluggable systems use incoming data assuming Unicode.

    2.1) For Salt modules that query an API; the module should convert the data received from the API into Unicode.

    2.2) For Salt modules that shell out to get output; the module should convert data received into Unicode. (This does not apply if using the `cmd` execution module, which should handle this for you.

    2.3) For Salt modules which print directly to the console (not via an outputter) or which write directly to disk, a string should be converted to bytes directly before doing so. To handle this conversion, the global variable `__salt_system_encoding__` is available, which declares the locale of the system that Salt is running on.

3) When a function in a Salt module returns, it should return Unicode.

4) When Salt delivers the data to an outputter or a returner, it is the job of the outputter
or returner to convert the data back to bytes before displaying it on the console or writing it to storage.
