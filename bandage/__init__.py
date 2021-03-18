"""
bandage, v1.0
Made by perpetualCreations
"""

from platform import system
from hashlib import md5
from time import time
from tempfile import gettempdir
from os import mkdir, path, remove
from shutil import unpack_archive, copy, make_archive, rmtree
from io import StringIO
from contextlib import redirect_stdout
from json import load as jsonload
from json import dump as jsondump
from typing import Union
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

    TODO REFACTOR, HEAVILY VERBOSE
    """
    class FetchError(BaseException):
        """
        Raised when a web fetch request fails (qualified when status code is not in 200 range and is not 301 or 302).
        """
    class ReleaseFileFormatError(BaseException):
        """
        Raised when a user-defined release file is invalid (i.e. is not a compressed archive such as zip or tar.gz, file cannot be uncompressed).
        """
    class ReleaseNameError(BaseException):
        """
        Raised when releases have different NAME files or are missing NAME files.
        This is indicative of a inconsistent release continuum, the releases are for two different software applications, or they're simply undefined.
        Can be suppressed by specifying the set_name parameter to a string, which will be the new NAME of the patch archive.
        """
    class PatchingNameError(BaseException):
        """
        ReleaseNameError, specifically for bandage.Patcher. Raised when the patch and target have different or missing NAME files.
        Can be suppressed by specifying the suppress_name_check to True, skipping NAME checks.
        """
    class MissingVersionsError(BaseException):
        """
        Raised when releases are missing VERSION files. Intended to be raised by bandage.Weave only.
        This can be suppressed by initializing the Weave class with suppress_missing_versions as True.
        If the patch is made with versions left unspecified, the Supply class cannot detect the release automatically, Patcher must be directed to the patch archive manually.
        """
    class VersionsError(BaseException):
        """
        Raised when patch archive and/or target directory have invalid (i.e. unreadable or undefined version values, version upgrading listed in patch archive being different from target), or missing VERSION files.
        Intended for bandage.Patcher, is also raised by bandage.Supply when target VERSION file does not exist.
        This can be suppressed by initializing the Patcher class with suppress_version_check as True.
        """
    class MissingChangeDataError(BaseException):
        """
        Raised when a release archive is missing the CHANGE.json file.
        """
    class UnableToParseError(BaseException):
        """
        Raised when Bandage is unable to interpret and parse data. Usually raised with additional information.
        """
    class TargetMissingKeeps(BaseException):
        """
        Raised when bandage.Patcher finds files or directories listed under the "keep" list that are missing from the target.
        This can be suppressed by initializing the Patcher class with skip_keep_check as True.
        """
    class PatchMissingAdditions(BaseException):
        """
        Raised when bandage.Patcher finds files or directories listed under the "add" list that are missing from the patch archive.
        """
    class PatchMissingReplacements(BaseException):
        """
        Raised when bandage.Patcher finds files or directories listed under the "replace" list that are missing from the patch archive.
        """
    class PatchNotFound(BaseException):
        """
        Raised when patch defined for bandage.Patcher does not exist, or if patch repo targeted for bandage.Supply does not exist.
        """
    class PatchTargetInvalid(BaseException):
        """
        Raised when target directory defined for bandage.Patcher does not exist.
        """
    class ReleaseNotFound(BaseException):
        """
        Raised when target releases for bandage.Weave does not exist.
        """
    class RemoteNotHTTP(BaseException):
        """
        Raised when defined remote for bandage.Supply is not an HTTP or HTTPS address.
        """
    class RemoteNotSupported(BaseException):
        """
        Raised when defined remote for bandage.Supply is not supported.
        """
    class VersionMissingFromRemoteLineage(BaseException):
        """
        Raised when defined remote's lineage header does not contain supplied current version.
        """

class Patcher:
    """
    Main class for bandage.Patcher instances, which apply patches.
    """
    def __init__(self, patch: str, target: str, suppress_version_check: bool = False, suppress_name_check: bool = False, skip_keep_check: bool = False):
        """
        Takes patch file and target application directory, and applies changes after checking VERSION and NAME. Inorganic and for robots.
        :param patch: str, web address or path to patch file
        :param target: str, path to application directory for patching
        :param suppress_version_check: bool, if True VERSION/VERSIONS check is ignored, unsafe, default is False
        :param suppress_name_check: bool, if True NAME check is ignored, unsafe, default is False
        :param skip_keep_check: bool, if True Patcher does not check if files listed under Keep exist, default is False
        :param skip_pre_patch_backup_generation: bool, if True Patcher does not
        """
        self.urllib3_pool_manager = urllib3.PoolManager()
        self.WORK_DIR = Patcher.create_work_directory()

        self.patch = patch
        self.target = target

        if "https://" in patch[:8] or "http://" in patch[:8]:
            patch_grab = Patcher.fetch(self, patch)
            with open(gettempdir() + self.WORK_DIR + self.patch.path.splitext()[1], "w") as patch_data_dump: patch_data_dump.write(patch_grab.data)
            self.patch = gettempdir() + self.WORK_DIR + self.patch.splitext()[1]
        else:
            if path.isfile(self.patch) is False: raise Exceptions.PatchNotFound("Patch file with path " + self.patch + " does not exist.")

        if path.isdir(self.target) is False: raise Exceptions.PatchTargetInvalid("Target directory " + self.target + " does not exist.")

        unpack_archive(self.patch, gettempdir() + self.WORK_DIR)

        try:
            if suppress_name_check is False:
                with open(gettempdir() + self.WORK_DIR + "/NAME") as patch_name_handle: patch_name = patch_name_handle.read()
                with open(self.target + "/NAME") as target_name_handle:
                    if target_name_handle.read() != patch_name: raise Exceptions.ReleaseNameError("NAME files of target and patch are different. Target is " + target_name_handle.read() + " and patch " + patch_name + ".")
        except FileNotFoundError as ParentException: raise Exceptions.PatchingNameError("Missing NAME file(s).") from ParentException

        try:
            if suppress_version_check is False:
                with open(gettempdir() + self.WORK_DIR + "/VERSIONS") as versions_handle: patch_versions = versions_handle.read()
                self.patch_versions = patch_versions.split(" -> ")
                with open(target + "/VERSION") as version_handle:
                    if version_handle.read() != self.patch_versions[0]: raise Exceptions.VersionsError("VERSIONS file specifies a different upgrade-from version compared to the target VERSION file. Target is on " + version_handle.read() + ", and patch supporting " + self.patch_versions[0] + ".")
        except FileNotFoundError as ParentException: raise Exceptions.VersionsError("Missing VERSION(S) file(s).") from ParentException

        try:
            with open(gettempdir() + self.WORK_DIR + "/CHANGE.json") as changelog_handle: self.change = jsonload(changelog_handle)
        except FileNotFoundError as ParentException: raise Exceptions.MissingChangeDataError("CHANGE.json file of patch archive is missing.") from ParentException

        for x in self.change:
            self.change[x] = self.change[x].strip("[]").split(", ")
            for y in self.change[x]: self.change[x][y] = self.change[x][y].strip("'")

        if skip_keep_check is False:
            for x in range(0, len(self.change["keep"])):
                if path.isdir(self.target + "/" + self.change["keep"][x]) is not True and path.isfile(self.target + "/" + self.change["keep"][x]) is not True: raise Exceptions.TargetMissingKeeps("Target missing item(s) that should exist, listed under the keep operation. Raised on " + self.change["keep"][x] + ".")

        for x in range(0, len(self.change["add"])):
            if path.isdir(gettempdir() + self.WORK_DIR + "/patch/add/" + self.change["add"][x]) is not True and path.isfile(gettempdir() + self.WORK_DIR + "/patch/add" + self.change["add"][x]) is not True: raise Exceptions.PatchMissingAdditions("Missing item(s) for addition. Raised on " + self.change["add"][x] + ".")

        for x in range(0, len(self.change["replace"])):
            if path.isdir(gettempdir() + self.WORK_DIR + "/patch/replace/" + self.change["replace"][x]) is not True and path.isfile(gettempdir() + self.WORK_DIR + "/patch/replace" + self.change["replace"][x]) is not True: raise Exceptions.PatchMissingReplacements("Missing item(s) for replacement. Raised on " + self.change["replace"][x] + ".")

        for x in range(0, len(self.change["add"])): copy(gettempdir() + self.WORK_DIR + "/patch/add/" + self.change["add"][x], self.target + "/" + path.dirname(self.change["add"][x]))

        for x in range(0, len(self.change["replace"])):
            if path.isdir(self.target + "/" + self.change["replace"][x]) is True or path.isfile(self.target + "/" + self.change["replace"][x]) is True: remove(self.target + "/" + self.change["replace"][x])
            copy(gettempdir() + self.WORK_DIR + "/patch/replace/" + self.change["replace"][x], self.target + "/" + path.dirname(self.change["replace"][x]))

        for x in range(0, len(self.change["remove"])):
            if path.isdir(self.change["remove"][x]) is True: rmtree(self.target + "/" + self.change["remove"][x])
            if path.isfile(self.change["remove"][x]) is True: remove(self.target + "/" + self.change["remove"][x])

        with open(self.target + "/VERSION", "w") as version_overwrite_handle:
            version_overwrite_handle.truncate(0)
            version_overwrite_handle.write(self.patch_versions[1])

        rmtree(gettempdir() + self.WORK_DIR)

    def fetch(self, target: str) -> object:
        """
        Fetches HTTP and HTTPS requests through URLLIB3, returns request object, raises exception if status is not in 2XX or 301, 302.
        :param target:
        :return: object
        """
        fetch_request = self.urllib3_pool_manager.request("GET", target)
        if str(fetch_request.status)[:1] is not "2" and fetch_request.status not in [301, 302]: raise Exceptions.FetchError("Failed to fetch resource, returned HTTP status code " + str(fetch_request.status) + ".") from None
        else: return fetch_request

    @staticmethod
    def create_work_directory() -> str:
        """
        Creates directory under the OS temporary directory with a unique name to prevent conflicting instances.
        Returns generated name.
        :return: str, generated tempdir name
        """
        identifier = "/bandage_patcher_session_" + md5(str(time()).encode(encoding = "ascii", errors = "replace")).decode(encoding = "utf-8", errors = "replace")
        mkdir(gettempdir() + identifier)
        return identifier

class Weave:
    """
    Main class for bandage.Weave instances, which generates patches.
    """
    def __init__(self, release_old: str, release_new: str, output_path: str, set_name: Union[str, None] = None, suppress_missing_versions: bool = False):
        """
        Takes two release files, and compares them for differences, then generates patch file to given output path. Inorganic and for robots.
        :param release_old: str, web address or path to old release file
        :param release_new: str, web address or path to new release file
        :param output_path: str, path to output archive, if archive already exists, deletes archive and "overwrites" it with the new archive file
        :param set_name: Union[str, None], new patch NAME file, if not None, NAME check is ignored, default None
        :param suppress_missing_versions: bool, if True missing versions error is ignored, Supply class cannot detect the release automatically, Patcher must be directed to the patch archive manually, default False
        """
        self.urllib3_pool_manager = urllib3.PoolManager()
        self.WORK_DIR = Weave.create_work_directory()

        self.release_old = release_old
        self.release_new = release_new

        if "https://" in self.release_old[:8] or "http://" in self.release_old[:8]:
            release_old_grab = Weave.fetch(self, self.release_old)
            with open(gettempdir() + self.WORK_DIR + "/old/" + self.release_old.path.splitext()[1], "w") as release_old_data_dump: release_old_data_dump.write(release_old_grab.data)
            self.release_old = gettempdir() + self.WORK_DIR + "/old/" + self.release_old.path.splitext()[1]
        else:
            if path.isfile(self.release_old) is False: raise Exceptions.ReleaseNotFound("Old release file " + self.release_old + " does not exist.")

        if "https://" in self.release_new[:8] or "http://" in self.release_new[:8]:
            release_new_grab = Weave.fetch(self, self.release_new)
            with open(gettempdir() + self.WORK_DIR + "/new/" + self.release_new.path.splitext()[1], "w") as release_new_data_dump: release_new_data_dump.write(release_new_grab.data)
            self.release_new = gettempdir() + self.WORK_DIR + "/new/" + self.release_new.path.splitext()[1]
        else:
            if path.isfile(self.release_new) is False: raise Exceptions.ReleaseNotFound("New release file " + self.release_new + " does not exist.")

        unpack_archive(self.release_old, gettempdir() + self.WORK_DIR + "/old/")
        unpack_archive(self.release_new, gettempdir() + self.WORK_DIR + "/new/")

        try:
            with open(gettempdir() + self.WORK_DIR + "/old/NAME") as release_name_handle: self.release_name_old = release_name_handle.read()
            with open(gettempdir() + self.WORK_DIR + "/new/NAME") as release_name_handle: self.release_name_new = release_name_handle.read()
            if self.release_name_new != self.release_name_old and set_name is None: raise Exceptions.ReleaseNameError("NAME files of old and new releases do not match. Old is " + self.release_name_old + " and new " + self.release_name_new + ".")
        except FileNotFoundError as ParentException:
            if set_name is not None: raise Exceptions.ReleaseNameError("NAME files of old and new releases are missing.") from ParentException

        try:
            with open(gettempdir() + self.WORK_DIR + "/old/VERSION") as release_version_handle: self.release_version_old = release_version_handle.read()
            with open(gettempdir() + self.WORK_DIR + "/new/VERSION") as release_version_handle: self.release_version_new = release_version_handle.read()
        except FileNotFoundError as ParentException:
            if suppress_missing_versions is False: raise Exceptions.MissingVersionsError("VERSION files of old and new releases are missing.") from ParentException
            else:
                self.release_version_old = "NaN"
                self.release_version_new = "NaN"

        if suppress_missing_versions is False and len(self.release_version_old.split(" -> ")) != 0 or len(self.release_version_new.split(" -> ")) != 0: raise Exceptions.UnableToParseError('Release versions contain " -> " which will disrupt Patcher when trying to read the VERSIONS header.')

        self.index = Weave.comparison(self)

        with open(gettempdir() + self.WORK_DIR + "/patch/CHANGE.json", "w") as changelog_dump_handle: jsondump({"remove":str(self.index[0]), "add":str(self.index[1]), "keep":str(self.index[2]), "replace":str(self.index[3])}, changelog_dump_handle)

        for x in range(0, len(self.index[1])): copy(gettempdir() + self.WORK_DIR + "/new/" + self.index[1][x], gettempdir() + self.WORK_DIR + "/patch/add/" + self.index[1][x])
        for y in range(0, len(self.index[3])): copy(gettempdir() + self.WORK_DIR + "/new/" + self.index[3][y], gettempdir() + self.WORK_DIR + "/patch/replace/" + self.index[3][y])

        with open(gettempdir() + self.WORK_DIR + "/patch/VERSIONS", "w") as release_version_handle: release_version_handle.write(self.release_version_old + " -> " + self.release_version_new)
        if set_name is None:
            with open(gettempdir() + self.WORK_DIR + "/patch/NAME", "w") as release_name_handle: release_name_handle.write(self.release_name_new)
            make_archive(root_dir = gettempdir() + self.WORK_DIR + "/patch/", base_dir = output_path, base_name = self.release_name_new + "_" + self.release_name_old + "_to_" + self.release_name_new + "_bandage_patch", format = ".zip")
        else:
            with open(gettempdir() + self.WORK_DIR + "/patch/NAME", "w") as release_name_handle: release_name_handle.write(set_name)
            make_archive(root_dir = gettempdir() + self.WORK_DIR + "/patch/", base_dir = output_path, base_name = set_name + "_" + self.release_name_old + "_to_" + self.release_name_new + "_bandage_patch", format = ".zip")

        # TODO archive checksum generation

        rmtree(gettempdir() + self.WORK_DIR) # turns out Windows doesn't automatically clear out the temp directory! (https://superuser.com/questions/296824/when-is-a-windows-users-temp-directory-cleaned-out)

    def fetch(self, target: str) -> object:
        """
        Fetches HTTP and HTTPS requests through URLLIB3, returns request object, raises exception if status is not in 2XX or 301, 302.
        :param target:
        :return: object
        """
        fetch_request = self.urllib3_pool_manager.request("GET", target)
        if str(fetch_request.status)[:1] is not "2" and fetch_request.status not in [301, 302]: raise Exceptions.FetchError("Failed to fetch resource, returned status code " + str(fetch_request.status) + ".") from None
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
        raw = handle.getvalue().split("\n")
        dump = [[], [], [], []]
        parsing_directory = "" # directory path appends for old and new archive, allows for handling of sub-directories.
        for x in range(0, len(raw)):
            if raw[x][:4] == "diff":
                if len(raw[x].split(" ")) != 3: raise Exceptions.UnableToParseError("Release archives contain directories with spaces in their names. This breaks comparison interpretation.") from None
                parsing_directory = raw[x].split(" ")[1].lstrip(gettempdir() + self.WORK_DIR + "/old/")
            if raw[x][:(8 + len(gettempdir() + self.WORK_DIR + "/old/"))] == "Only in " + gettempdir() + self.WORK_DIR + "/old/":
                dump[0] = raw[x].lstrip("Only in " + gettempdir() + self.WORK_DIR + "/old/" + parsing_directory).strip("[]").split(", ")
                for y in range(0, len(dump[0])): dump[0][y] = parsing_directory + dump[0][y].strip("'")
            if raw[x][:(8 + len(gettempdir() + self.WORK_DIR + "/new/"))] == "Only in " + gettempdir() + self.WORK_DIR + "/new/":
                dump[1] = raw[x].lstrip("Only in " + gettempdir() + self.WORK_DIR + "/new/" + parsing_directory).strip("[]").split(", ")
                for y in range(0, len(dump[1])): dump[1][y] = parsing_directory + dump[1][y].strip("'")
            if raw[x][:18] == "Identical files : ":
                dump[2] = raw[x].lstrip("Identical files : ").strip("[]").split(", ")
                for y in range(0, len(dump[2])): dump[2][y] = parsing_directory + dump[2][y].strip("'")
            if raw[x][:18] == "Differing files : ":
                dump[3] = raw[x].lstrip("Differing files : ").strip("[]").split(", ")
                for y in range(0, len(dump[3])): dump[3][y] = parsing_directory + dump[3][y].strip("'")
        return dump

class Supply:
    """
    Main class for bandage.Supply instances, which checks for new patches on remotes.
    """
    def __init__(self, remote: str, version_file: str):
        """
        Checks a remote HTTP endpoint for new patches. Inorganic and for robots.
        If no exception is thrown, dumps status and patch download URL to self.result and self.patch_web_source respectively, which can be retrieved as a list through method bandage.Supply.realize.

        If the remote is a repository on raw.githubusercontent.com, looks through repository contents for headers and patch files.
        It will be treated as a normal web server request. The remote URL should point to the correct branch and patch directory ot root.
        If the previous provision fails, throws Exceptions.RemoteInvalid.

        If the remote is a repository on github.com, looks for a release tagged "BANDAGE" for patch files and headers.
        If the previous provision fails, throws Exceptions.RemoteInvalid.

        If the endpoint is not a Github repository, bandage.Supply assumes the remote is a normal web server.
        bandage.Supply will request BANDAGE_PATCHES and BANDAGE_LINEAGE (it will literally append those files to the remote string parameter).
        It will retrieve a list of patches from BANDAGE_PATCHES, lookup the current version with BANDAGE_LINEAGE and trace the next version in series (hence, lineage).
        BANDAGE_LINEAGE release series will then be looked up in BANDAGE_PATCHES, for the patch that brings the current version to the most latest release.

        If bandage.Supply succeeded in finding headers and looking up lineage series, however finds the current version to be the latest, self.result is 0.
        If bandage.Supply succeeded in finding headers and looking up lineage series, and finds a patch to be applied for updating, self.result is -1 with self.patch_web_source as web address to patch file.
        If bandage.Supply succeeded in finding headers and looking up lineage series, however finds no patch available to upgrade with, self.result is 1.
        If bandage.Supply raised an exception, self.result and self.patch_web_source are None.

        Preliminary information if obtained is dumped into self.preliminary_dump. Contains version list and patches available, as list object. Retrieved through bandage.Supply.pre_collect.

        See documentation for more information.

        TODO cleanup doc strings

        :param remote: str, web address of patch host
        :param version_file: str, path to version file
        """
        self.urllib3_pool_manager = urllib3.PoolManager()

        self.remote = remote
        self.version_file = version_file

        try:
            with open(version_file) as version_handle: self.version = version_handle.read()
        except FileNotFoundError as ParentException: raise Exceptions.VersionsError("VERSION file directed by path " + self.version_file + " does not exist.") from ParentException

        if "https://" not in self.remote[:8] and "http://" not in self.remote[:8]: raise Exceptions.RemoteNotHTTP("Supplied remote " + self.remote + " is not a HTTP/HTTPS web address.")

        if self.remote[-1:] != "/": self.remote += "/"

        if "https://github.com" == self.remote[:18] or "http://github.com" == self.remote[:18]:
            if self.remote[-18] == "/releases/BANDAGE/":
                self.pre_collect = [Supply.fetch(self, self.remote.rstrip("/BANDAGE/") + "/download/BANDAGE/BANDAGE_PATCHES").data.decode(encoding = "utf-8", errors = "replace").split("\n"), Supply.fetch(self, self.remote.rstrip("/BANDAGE/") + "/download/BANDAGE/BANDAGE_LINEAGE").data.decode(encoding = "utf-8", errors = "replace").split("\n")]
                for x in range(0, len(self.pre_collect[1])):
                    if self.version == self.pre_collect[1][x]:
                        self.version_gap = x
                        break
                if self.version_gap is None: raise Exceptions.VersionMissingFromRemoteLineage("Version " + self.version + " does not exist in remote's lineage header.")
                elif self.version_gap == 0: self.result = 0
                else:
                    compatible_sources = []
                    for x in range(0, len(self.pre_collect[0])):
                        if self.pre_collect[0][x].split("||")[0].split(" -> ")[0] == self.version: compatible_sources.append(self.pre_collect[0][x].split("||")[0])
                    if not compatible_sources: self.result = 1
                    else:
                        for x in range(0, self.version_gap):
                            for y in compatible_sources:
                                if y.split(" -> ")[1] == self.pre_collect[x]:
                                    self.result = -1
                                    self.patch_web_source = self.remote.rstrip("/BANDAGE/") + "/download/BANDAGE/" + self.pre_collect[0][x].split("||")[1]
            else: raise Exceptions.RemoteNotSupported("Remote defined as " + self.remote + " is not supported.")
        else:
            self.pre_collect = [Supply.fetch(self, self.remote + "BANDAGE_PATCHES").data.decode(encoding = "utf-8", errors = "replace").split("\n"), Supply.fetch(self, self.remote + "BANDAGE_LINEAGE").data.decode(encoding = "utf-8", errors = "replace").split("\n")]
            for x in range(0, len(self.pre_collect[1])):
                if self.version == self.pre_collect[1][x]:
                    self.version_gap = x
                    break
            if self.version_gap is None: raise Exceptions.VersionMissingFromRemoteLineage("Version " + self.version + " does not exist in remote's lineage header.")
            elif self.version_gap == 0: self.result = 0
            else:
                compatible_sources = []
                for x in range(0, len(self.pre_collect[0])):
                    if self.pre_collect[0][x].split("||")[0].split(" -> ")[0] == self.version: compatible_sources.append(self.pre_collect[0][x].split("||")[0])
                if not compatible_sources: self.result = 1
                else:
                    for x in range(0, self.version_gap):
                        for y in compatible_sources:
                            if y.split(" -> ")[1] == self.pre_collect[x]:
                                self.result = -1
                                if self.pre_collect[0][x].split("||")[1][:8] == "https://" or "http://" in self.pre_collect[0][x].split("||")[1][:8]: self.patch_web_source = self.pre_collect[0][x].split("||")[1]
                                else:
                                    if self.pre_collect[0][x].split("||")[1][:1] != "/": self.remote = self.remote.rstrip("/")
                                    self.patch_web_source = self.remote + self.pre_collect[0][x].split("||")[1]

    def fetch(self, target: str) -> object:
        """
        Fetches HTTP and HTTPS requests through URLLIB3, returns request object, raises exception if status is not in 2XX or 301, 302.
        :param target:
        :return: object
        """
        fetch_request = self.urllib3_pool_manager.request("GET", target)
        if str(fetch_request.status)[:1] is not "2" and fetch_request.status not in [301, 302]: raise Exceptions.FetchError("Failed to fetch resource, returned status code " + str(fetch_request.status) + ".") from None
        else: return fetch_request
