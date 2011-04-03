'''
Module for running arbitrairy tests
'''

import time

def echo(text):
    '''
    Return a string - used for testing the connection

    CLI Example:
    salt '*' test.echo 'foo bar baz quo qux'
    '''
    print 'Echo got called!'
    return text

def ping():
    '''
    Just used to make sure the minion is up and responding
    Return True

    CLI Example:
    salt '*' test.ping
    '''
    return True

def fib(num):
    '''
    Return a fibonachi sequence up to the passed number, and the time it took
    to compute in seconds. Used for performance tests

    CLI Example:
    salt '*' test.fib 3
    '''
    start = time.time()
    a, b = 0, 1
    ret = [0]
    while b < num:
        ret.append(b)
        a, b = b, a + b
    return ret, time.time() - start

def collatz(start):
    '''
    Execute the collatz conjecture from the passed starting number, returns
    the sequence and the time it took to compute. Used for performance tests.

    CLI Example:
    salt '*' test.collatz 3
    '''
    begin = time.time()
    steps = []
    while start != 1:
        steps.append(start)
        if start > 1:
            if start % 2 == 0:
                start = start / 2
            else:
                start = start * 3 + 1
    return steps, time.time() - begin

