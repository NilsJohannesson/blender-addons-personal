"""Shared Blender test bootstrap."""

import argparse
import os
import sys


def extension_root_from_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extension-root", required=True)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return os.path.abspath(parser.parse_args(argv).extension_root)


def load_extension():
    extension_root = extension_root_from_args()
    addons_root = os.path.dirname(extension_root)
    if addons_root not in sys.path:
        sys.path.insert(0, addons_root)

    import render_spine

    return render_spine


def assert_equal(actual, expected, message=""):
    if actual != expected:
        detail = "{} != {}".format(repr(actual), repr(expected))
        raise AssertionError("{}: {}".format(message, detail) if message else detail)


def finish(name):
    print("RSP_TEST_PASS: {}".format(name))
