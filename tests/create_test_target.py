"""
tool for clearing test_target directory and unpacking old.zip into it
"""

from shutil import unpack_archive, rmtree
from os import mkdir

rmtree("test_target")
mkdir("test_target")
unpack_archive("old.zip", "test_target")
