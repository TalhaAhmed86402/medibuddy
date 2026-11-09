"""Runs the usage examples written in docstrings.  They are pinned to the dev split in data/dev,
so rebuilding that split (new generator, new seed) means re-checking the printed values."""
import datetime as dt
import doctest
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)


def load_tests(loader, tests, ignore):
    import medibuddy_bench.world as world
    w = world.load_world(os.path.join(ROOT, "data/dev/world.json"))
    tests.addTests(doctest.DocTestSuite(world, globs={**vars(world), "w": w, "dt": dt},
                                        optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE))
    return tests


if __name__ == "__main__":
    unittest.main()
