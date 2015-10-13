# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
from threading import Thread, RLock, Event

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salt.utils.dictthread import DictThread
from salt.utils import dictthread
from salt.ext.six.moves import range

ensure_in_syspath('../../')
TCOUNT = 10


class UtilDictthreadTestCase(TestCase):

    dict1 = {'A': 'B', 'C': {'D': 'E', 'F': {'G': 'H', 'I': 'J'}}}

    def test_basic(self):
        # Create threaded dict from dict
        tdict = dictthread.DictThread(self.dict1)
        self.assertEqual(tdict, self.dict1)

        # Create threaded dict from threaded dict
        tdict2 = dictthread.DictThread(tdict)
        self.assertEqual(tdict2, self.dict1)

        tdict = DictThread(val=999)
        self.assertEqual(tdict, {'val': 999})
        l = RLock()
        event = Event()
        num = [0]
        tlist = []

        def t_set_val(x, num, event):
            last = False
            tdict['val'] = x
            with l:
                num[0] += 1
                if num[0] == TCOUNT:
                    last = True
            if not last:
                event.wait()
            else:
                event.set()
            self.assertEqual(tdict['val'], x)

        for i in range(10):
            t = Thread(target=t_set_val, args=[i, num, event])
            tlist.append(t)
        for t in tlist:
            t.start()
        for t in tlist:
            t.join()
        self.assertEqual(len(tdict._tmap), TCOUNT + 1)  # One is for 'mainThread'
        for k in tdict._tmap:
            d = tdict._tmap[k]
            self.assertEqual(len(d), 1)
            self.assertTrue('val' in d)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(UtilDictthreadTestCase, needs_daemon=False)
