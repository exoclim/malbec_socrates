# -*- coding: utf-8 -*-
"""Paths to data."""
from pathlib import Path

home = Path.home()

# Absolute path to the current directory
cur_dir = Path(__file__).absolute().parent

# Planetary constants directory (see https://exoclim.github.io/aeolus/examples/00_Constants.html)
const_dir = cur_dir / "const"

# Directory with UM start dumps
start_dump_dir = Path.home() / "start_dumps" / "malbec"

# Common directory with inputs provided by PSG
psg_data_dir = cur_dir.parent / "cases"
