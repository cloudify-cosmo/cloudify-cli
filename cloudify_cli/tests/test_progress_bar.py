import sys
import unittest
# TODO: Use io instead and fix unicode
from cStringIO import StringIO

from .. import utils


class TestProgressBar(unittest.TestCase):
    def test_progress_bar_1(self):
        results = (
            '\r test |------------------------| 0.0%',
            '\r test |#####-------------------| 20.0%',
            '\r test |##########--------------| 40.0%',
            '\r test |##############----------| 60.0%',
            '\r test |###################-----| 80.0%',
            '\r test |########################| 100.0%\n')

        try:
            progress_func = utils.generate_progress_handler(
                file_path='test', max_bar_length=40)
            total_size = 5
            for iteration in xrange(6):
                sys.stdout = captured = StringIO()
                progress_func(iteration, total_size)
                self.assertEqual(captured.getvalue(), results[iteration])

        finally:
            sys.stdout = sys.__stdout__

    def test_progress_bar_2(self):
        results = (
            '\r test |----------------------------------| 0.0%',
            '\r test |----------------------------------| 0.38%',
            '\r test |#---------------------------------| 3.84%',
            '\r test |#############---------------------| 38.44%',
            '\r test |#############---------------------| 39.38%',
            '\r test |#####################-------------| 62.5%',
            '\r test |##################################| 100.0%\n')

        total_size = 32000
        increments = (0, 123, 1230, 12300, 12600, 20000, 32000)

        try:
            progress_func = utils.generate_progress_handler(
                file_path='test', max_bar_length=50)
            for iteration in xrange(7):
                sys.stdout = captured = StringIO()
                progress_func(increments[iteration], total_size)
                self.assertEqual(captured.getvalue(), results[iteration])

        finally:
            sys.stdout = sys.__stdout__
