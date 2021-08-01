"""
fbscrape
Copyright (C) 2021  schnusch

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os.path
import subprocess
import unittest


class Flake8(unittest.TestCase):
    def test_flake8(self):
        directory = os.path.join(os.path.dirname(__file__), '..')
        p = subprocess.run(['flake8', '--', 'bin', 'fbscrape', 'tests', 'setup.py'],
                           cwd=directory)
        self.assertEqual(p.returncode, 0)
