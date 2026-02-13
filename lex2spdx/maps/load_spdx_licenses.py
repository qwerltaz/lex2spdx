import os
import xml

from IPython.terminal.shortcuts.filters import not_inside_unclosed_string

from .. import cvar


def load_spdx_licenses():
    license_list = []
    for dirpath, dirnames, filenames in os.walk(cvar.spdx_license_list_dir):
        raise NotImplementedError



load_spdx_licenses()
