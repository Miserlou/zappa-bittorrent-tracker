# -*- coding: utf8 -*-
import base64
import collections
import json
import os
import random
import string
import unittest

from track import fail

class TestZBT(unittest.TestCase):

    ##
    # Sanity Tests
    ##

    def test_test(self):
        self.assertTrue(True)

    def test_fail(self):
        fail('shit')


if __name__ == '__main__':
    unittest.main()
