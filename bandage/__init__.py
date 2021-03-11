"""
bandage, v1.0
Made by perpetualCreations
"""

from platform import system
from hashlib import md5
from time import time
from tempfile import gettempdir
from os import mkdir, path
from shutil import unpack_archive, copy
from io import StringIO
from contextlib import redirect_stdout
from json import load as jsonload
from json import dump as jsondump
import urllib3
import filecmp

# ref for shallow fix, https://stackoverflow.com/questions/4187564/recursively-compare-two-directories-to-ensure-they-have-the-same-files-and-subdi
class dircmp(filecmp.dircmp):
    """
    Compare the content of dir1 and dir2. In contrast with filecmp.dircmp, this
    subclass compares the content of files with the same path.
    """

    def phase3(self):
        """
        Find out differences between common files.
        Ensure we are using content comparison with shallow=False.
        """
        fcomp = filecmp.cmpfiles(self.left, self.right, self.common_files, shallow=False)
        self.same_files, self.diff_files, self.funny_files = fcomp

class Exceptions:
    """
    Class with exceptions for bandage nested under.
    """
    class WeaveFetchError(BaseException):
        """
        Raised when bandage.Weave encounters an error.
        """
    class ReleaseFileFormatError(BaseException):
        """
        Raised when a user-defined release file is invalid (i.e. is not a compressed archive such as zip or tar.gz, file cannot be uncompressed).
        """

class Patcher:
    """
    Main class for bandage.patcher instances, which apply patches.
    """
    def __init__(self):
        pass

class Weave:
    """
    Main class for bandage.weave instances, which generates patches.
    """
    def __init__(self, release_old, release_new):
        """
        Takes two release files, and compares them for differences.
        :param release_old: str, web address or path to old release file
        :param release_new: str, web address or path to new release file
        """
        self.urllib3_pool_manager = urllib3.PoolManager()
        self.WORK_DIR = Weave.create_work_directory()

        self.release_old = release_old
        self.release_new = release_new

        if "https://" in self.release_old[:8] or "http://" in self.release_old[:8]:
            release_old_grab = Weave.fetch(self, self.release_old)
            with open(gettempdir() + self.WORK_DIR + "/old" + self.release_old.path.splitext()[1], "w") as release_old_data_dump: release_old_data_dump.write(release_old_grab.data)
            self.release_old = gettempdir() + self.WORK_DIR + "/old" + self.release_old.path.splitext()[1]

        if "https://" in self.release_new[:8] or "http://" in self.release_new[:8]:
            release_new_grab = Weave.fetch(self, self.release_new)
            with open(gettempdir() + self.WORK_DIR + "/new" + self.release_new.path.splitext()[1], "w") as release_new_data_dump: release_new_data_dump.write(release_new_grab.data)
            self.release_new = gettempdir() + self.WORK_DIR + "/new" + self.release_new.path.splitext()[1]

        unpack_archive(self.release_old, gettempdir() + self.WORK_DIR + "/old/")
        unpack_archive(self.release_new, gettempdir() + self.WORK_DIR + "/new/")

        self.index = Weave.comparison(self)

        with open(gettempdir() + self.WORK_DIR + "/patch/CHANGE.json") as changelog_dump_handle: jsondump({"remove":str(self.index[0]), "add":str(self.index[1]), "keep":str(self.index[2]), "replace":str(self.index[3])}, changelog_dump_handle)

        for x in range(0, len(self.index[1])): copy(gettempdir() + self.WORK_DIR + "/new/" + self.index[1][x], gettempdir() + self.WORK_DIR + "/patch/add/" + self.index[1][x])
        for y in range(0, len(self.index[3])): copy(gettempdir() + self.WORK_DIR + "/new/" + self.index[3][y], gettempdir() + self.WORK_DIR + "/patch/replace/" + self.index[3][y])


    def fetch(self, target: str) -> object:
        """
        Fetches HTTP and HTTPS requests through URLLIB3, returns request object, raises exception if status is not in 2XX or 301, 302.
        :param target:
        :return: object
        """
        fetch_request = self.urllib3_pool_manager.request("GET", target)
        if str(fetch_request.status)[:1] is not "2" and fetch_request.status not in [301, 302]:
            raise Exceptions.WeaveFetchError("Failed to fetch resource, returned status code " + str(fetch_request.status) + ".")
        else: return fetch_request

    @staticmethod
    def create_work_directory() -> str:
        """
        Creates directory under the OS temporary directory with a unique name to prevent conflicting instances.
        Returns generated name.
        :return: str, generated tempdir name
        """
        identifier = "/bandage_weave_session_" + md5(str(time()).encode(encoding = "ascii", errors = "replace")).decode(encoding = "utf-8", errors = "replace")
        mkdir(gettempdir() + identifier)
        mkdir(gettempdir() + identifier + "/old")
        mkdir(gettempdir() + identifier + "/new")
        mkdir(gettempdir() + identifier + "/patch")
        mkdir(gettempdir() + identifier + "/patch/add")
        mkdir(gettempdir() + identifier + "/patch/replace")
        return identifier

    def comparison(self) -> list:
        """
        Compares old and new directories under self.WORK_DIR for differences, returns as list.
        :return: list, contains release differences
        """
        handle = StringIO()
        with redirect_stdout(handle): dircmp(gettempdir() + self.WORK_DIR + "/old/", gettempdir() + self.WORK_DIR + "/new/").report_full_closure()
        raw = handle.getvalue().rstrip("\n").split("\n")
        del raw[0]
        dump = [[], [], [], []]
        for x in range(0, len(raw)):
            if raw[x][:(8 + len(gettempdir() + self.WORK_DIR + "/old/"))] == "Only in " + gettempdir() + self.WORK_DIR + "/old/":
                dump[0] = raw[x].lstrip("Only in " + gettempdir() + self.WORK_DIR + "/old/").strip("[]").split(", ")
                for y in range(0, len(dump[0])): dump[0][y] = dump[0][y].strip("'")
            if raw[x][:(8 + len(gettempdir() + self.WORK_DIR + "/new/"))] == "Only in " + gettempdir() + self.WORK_DIR + "/new/":
                dump[1] = raw[x].lstrip("Only in " + gettempdir() + self.WORK_DIR + "/new/").strip("[]").split(", ")
                for y in range(0, len(dump[1])): dump[1][y] = dump[1][y].strip("'")
            if raw[x][:18] == "Identical files : ":
                dump[2] = raw[x].lstrip("Identical files : ").strip("[]").split(", ")
                for y in range(0, len(dump[2])): dump[2][y] = dump[2][y].strip("'")
            if raw[x][:18] == "Differing files : ":
                dump[3] = raw[x].lstrip("Differing files : ").strip("[]").split(", ")
                for y in range(0, len(dump[3])): dump[3][y] = dump[3][y].strip("'")
        return dump

class Supply:
    """
    Main class for bandage.supply instances, which checks for new patches on remotes.
    """
    def __init__(self):
        pass
