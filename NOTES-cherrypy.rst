The CherryPy Request
====================

Several steps occur here to convert the incoming stream to more usable data
structures, pass the request to the appropriate user code, and then convert
outbound data. In-between the standard processing steps, users can define extra
code to be run via filters (CP 2.2) or hooks (CP 3).

1.  Request.processRequestLine() analyzes the first line of the request,
    turning "GET /path/to/resource?key=val HTTP/1.1" into a request method,
    path, query string, and version.

3.  Request.processHeaders() turns the incoming HTTP request headers into a
    dictionary, and separates Cookie information.

7.  The user-supplied page handler is looked up (see below).

2.  Any on_start_resource filters are run.

4.  Any before_request_body filters are run.

5.  Request.processBody() turns the incoming HTTP request body into a
    dictionary if possible, otherwise, it's passed onward as a file-like
    object.

6.  Any before_main filters are run.

8.  The user-supplied page handler is invoked. Its return value, which can be a
    string, a list, a file, or a generator object, will be used for the
    response body.

9.  Any before_finalize filters will be run.

10. Response.finalize() checks for HTTP correctness of the response, and
    transforms user-friendly data structures into HTTP-server-friendly
    structures.

11. Any on_end_resource filters are run.

CherryPy 3 performs the same steps as above, but in the order: 1, 3, 7, 2, 4,
5, 6, 8, 9, 10, 11. That is, it determines which bit of user code will respond
to the request much earlier in the process. This also means that internal
redirects can "start over" much earlier. In addition, CP 3 can collect
configuration data once (at the same time that it looks up the page handler);
CP 2 recollected config data every time it was used.
