"""This is the main Py Dev Hammer module."""

from py_dev_hammer import convert_markup_types, github_status_posting


def entry_point(args):
    github_status_posting.entry_point(args)
    convert_markup_types.entry_point(args)
