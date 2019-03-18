#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2018 David Lilien <dlilien90@gmail.com>
#
# Distributed under terms of the GNU GPL3.0 license.

"""
Make sure that we can successfully read gssi input files
"""

import os
import unittest
import numpy as np
from impdar.lib import load_pulse_ekko

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


class Dummy(unittest.TestCase):

    def test_load_pe(self):
        load_pulse_ekko.PE(os.path.join(THIS_DIR, 'input_data', 'test_pe.DT1'))


if __name__ == '__main__':
    unittest.main()