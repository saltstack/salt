# -*- coding: utf-8 -*-
'''
    salt.utils.filebuffer
    ~~~~~~~~~~~~~~~~~~~~~

    This utility allows parsing a file in chunks.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import salt libs
import salt.utils
from salt.exceptions import SaltException


class InvalidFileMode(SaltException):
    '''
    An invalid file mode was used to open the file passed to the buffer
    '''


class BufferedReader(object):
    '''
    This object allows iterating through the contents of a file keeping
    X configurable bytes in memory which can be used to, for example,
    do regex search/matching on more than a single line.

    So, **an imaginary, non accurate**, example could be:

        1 - Initiate the BufferedReader filing it to max_in_men:
            br = [1, 2, 3]

        2 - next chunk(pop chunk_size from the left, append chunk_size to the
        right):
            br = [2, 3, 4]


    :type  path: str
    :param path: The file path to be read

    :type  max_in_mem: int
    :param max_in_mem: The maximum bytes kept in memory while iterating through
                       the file. Default 256KB.

    :type  chunk_size: int
    :param chunk_size: The size of each consequent read chunk. Default 32KB.

    :type  mode: str
    :param mode: The mode the file should be opened. **Only read modes**.

    '''
    def __init__(self, path, max_in_mem=256 * 1024, chunk_size=32 * 1024,
                 mode='r'):
        if 'a' in mode or 'w' in mode:
            raise InvalidFileMode("Cannot open file in write or append mode")
        self.__path = path
        self.__file = salt.utils.fopen(self.__path, mode)
        self.__max_in_mem = max_in_mem
        self.__chunk_size = chunk_size
        self.__buffered = None

    # Public attributes
    @property
    def buffered(self):
        return self.__buffered

    # Support iteration
    def __iter__(self):
        return self

    def next(self):
        '''
        Return the next iteration by popping `chunk_size` from the left and
        appending `chunk_size` to the right if there's info on the file left
        to be read.
        '''
        if self.__buffered is None:
            multiplier = self.__max_in_mem / self.__chunk_size
            self.__buffered = ""
        else:
            multiplier = 1
            self.__buffered = self.__buffered[self.__chunk_size:]

        data = self.__file.read(self.__chunk_size * multiplier)

        if not data:
            self.__file.close()
            raise StopIteration

        self.__buffered += data
        return self.__buffered

    # Support with statements
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


def _main():
    def timeit_string(fpath, max_size, chunk_size):

        breader = BufferedReader(fpath, max_size, chunk_size)
        for chunk in breader:
            chunk
        return

    def sizeof_fmt(num):
        for unit in ['bytes', 'KB', 'MB', 'GB']:
            if num < 1024.0:
                return '{0:3.1f}{1}'.format(num, unit)
            num /= 1024.0
        return '{0:3.1f}{1}'.format(num, 'TB')

    import os
    import timeit
    fpath = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "../../doc/topics/tutorials/starting_states.rst"
    ))

    tpath = "/tmp/starting_states.rst"

    for fmultiplier in (1, 10, 50, 100, 800, 3200):
        ffile = salt.utils.fopen(tpath, "w")
        while fmultiplier > 0:
            ffile.write(salt.utils.fopen(fpath).read())
            fmultiplier -= 1

        ffile.close()

        tnumber = 1000

        print('Running tests against a file with the size of {0}'.format(
            sizeof_fmt(os.stat(tpath).st_size))
        )

        for multiplier in [4, 8, 16, 32, 64, 128, 256]:
            chunk_size = multiplier * 1024
            max_size = chunk_size * 5
            timer = timeit.Timer(
                "timeit_string('{0}', {1:d}, {2:d})".format(
                    tpath, max_size, chunk_size
                ), "from __main__ import timeit_string"
            )
            print("timeit_string ({0: >7} chunks; max: {1: >7}):".format(
                sizeof_fmt(chunk_size), sizeof_fmt(max_size))),
            print(u"{0: >6} \u00B5sec/pass".format(u"{0:0.2f}".format(
                tnumber * timer.timeit(number=tnumber) / tnumber
            )))

        print


if __name__ == '__main__':
    _main()
