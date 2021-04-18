"""
bandage, v1.0
Made by perpetualCreations
"""

from platform import system
from hashlib import md5
from time import time
from tempfile import gettempdir
from os import mkdir, path, remove, listdir
from shutil import unpack_archive, copyfile, make_archive, rmtree, copytree
from io import StringIO
from contextlib import redirect_stdout
from json import load as jsonload
from json import dump as jsondump
from typing import Union
import urllib3
import filecmp


# ref for shallow fix,
# https://stackoverflow.com/questions/4187564/recursively-compare-two-directories-to-ensure-they-have-the-same-files-and-subdi


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


class Backend:
    """
    Shared backend static functions.
    """

    @staticmethod
    def fetch(target: str) -> object:
        """
        Fetches HTTP and HTTPS requests through URLLIB3, returns request object, raises exception if status is not in
        2XX or 301, 302.

        :param target: str, HTTPS/HTTP address
        :return: object
        """
        urllib3_pool_manager = urllib3.PoolManager()
        fetch_request = urllib3_pool_manager.request("GET", target)
        if str(fetch_request.status)[:1] is not "2" and fetch_request.status not in [301, 302]:
            raise Exceptions.FetchError(
                "Failed to fetch resource, returned HTTP status code " + str(fetch_request.status) + ".") from None
        else:
            return fetch_request

    @staticmethod
    def directory_split_recursive(whole: str) -> list:
        """
        Takes path parameter and applies path.split recursively, dumps spliced directory tree to return variable.
        It will produce segmented directories, i.e:
        /path/to/somewhere/ -> /path/to -> /path/
        ...Which will be appended to the return list as mentioned previously.

        :param whole: str, path for splitting into component directories
        :return: list, contains components
        """
        # append components to this list, function return
        dump = []
        # remaining path after splitting previous component
        previous = "/INITIAL/INITIAL"
        while path.split(previous)[1] != "":
            if previous == "/INITIAL/INITIAL":
                previous = path.split(whole)[0]
            else:
                previous = path.split(previous)[0]
            if previous != "/":
                dump.append(previous)
        return dump


class Exceptions:
    """
    bandage exception class with children classes.
    """

    class FetchError(BaseException):
        """
        Raised when a web fetch request fails (qualified when status code is not in 200 range and is not 301 or 302).
        """

    class PatchError(BaseException):
        """
        Raised for errors involving patch files, caused by them being missing, invalid...
        """

    class ReleaseError(BaseException):
        """
        Raised for errors involving release archive files, caused by them being missing, invalid...
        """

    class TargetError(BaseException):
        """
        Raised for errors involving specified bandage.Patcher target for upgrade.
        """

    class RemoteError(BaseException):
        """
        Raised for errors involving specified bandage.Patcher remotes for fetching.
        """

    class VersionError(BaseException):
        """
        Raised for errors involving VERSION files, caused by them being missing, invalid, mismatching, being the same...
        """

    class UnableToParseError(BaseException):
        """
        Raised when Bandage is unable to interpret a string, usually raised with additional information.
        """


class Patcher:
    """
    Main class for bandage.Patcher instances, which apply patches.
    """

    def __init__(self, patch: str, target: str, suppress_version_check: bool = False, suppress_name_check: bool = False,
                 skip_keep_check: bool = False):
        """
        Takes patch file and target application directory, and applies changes after checking VERSION and NAME.
        Inorganic and for robots.

        :param patch: str, web address or path to patch file
        :param target: str, path to application directory for patching
        :param suppress_version_check: bool, if True VERSION/VERSIONS check is ignored, unsafe, default is False
        :param suppress_name_check: bool, if True NAME check is ignored, unsafe, default is False
        :param skip_keep_check: bool, if True Patcher does not check if files listed under Keep exist, default is False
        """
        self.WORK_DIR = Patcher.create_work_directory()

        self.patch = patch
        self.target = target

        if "https://" in patch[:8] or "http://" in patch[:8]:
            patch_grab = Backend.fetch(patch)
            with open(gettempdir() + self.WORK_DIR + path.splitext(self.patch)[1], "w") as patch_data_dump:
                patch_data_dump.write(patch_grab.data)
            self.patch = gettempdir() + self.WORK_DIR + path.splitext(self.patch)[1]
        else:
            if path.isfile(self.patch) is False:
                raise Exceptions.PatchError("Patch file with path " + self.patch + " does not exist.")

        if path.isdir(self.target) is False or not listdir(self.target):
            raise Exceptions.TargetError("Target directory " + self.target + " does not exist or is empty.")

        unpack_archive(self.patch, gettempdir() + self.WORK_DIR)

        try:
            if suppress_name_check is False:
                with open(gettempdir() + self.WORK_DIR + "/NAME") as patch_name_handle:
                    patch_name = patch_name_handle.read()
                with open(self.target + "/NAME") as target_name_handle:
                    if target_name_handle.read() != patch_name:
                        raise Exceptions.PatchError("NAME files of target and patch are different. Target is " +
                                                    target_name_handle.read() + " and patch " + patch_name + ".")
        except FileNotFoundError as ParentException:
            raise Exceptions.PatchError("Missing NAME file(s).") from ParentException

        try:
            if suppress_version_check is False:
                with open(gettempdir() + self.WORK_DIR + "/VERSIONS") as versions_handle:
                    patch_versions = versions_handle.read()
                self.patch_versions = patch_versions.split(" -> ")
                with open(path.join(target, "VERSION")) as version_handle:
                    current_version = version_handle.read()
                if current_version != self.patch_versions[0]:
                    raise Exceptions.VersionError("VERSIONS file specifies a different upgrade-from version "
                                                  "compared to the target VERSION file. Target is on " + current_version
                                                  + ", and patch supporting " + self.patch_versions[0] + ".")
        except FileNotFoundError as ParentException:
            raise Exceptions.VersionError("Missing VERSION(S) file(s).") from ParentException

        try:
            with open(gettempdir() + self.WORK_DIR + "/CHANGE.json") as changelog_handle:
                self.change = jsonload(changelog_handle)
        except FileNotFoundError as ParentException:
            raise Exceptions.PatchError("CHANGE.json file of patch archive is missing.") from ParentException

        for x in self.change:
            self.change[x] = self.change[x].strip("[]").split(", ")
            for y in range(0, len(self.change[x])):
                self.change[x][y] = self.change[x][y].strip("'")

        if skip_keep_check is False:
            for x in range(0, len(self.change["keep"])):
                if path.isdir(path.join(self.target, self.change["keep"][x])) is not True and \
                        path.isfile(path.join(self.target, self.change["keep"][x])) is not True:
                    raise Exceptions.TargetError("Target missing item(s) that should exist, listed under the keep "
                                                 "operation. Raised on " + self.change["keep"][x] + ".")

        for x in range(0, len(self.change["add"])):
            if path.isdir(gettempdir() + self.WORK_DIR + "/add/" + self.change["add"][x]) is not True and path.isfile(
                gettempdir() + self.WORK_DIR + "/add/" + self.change["add"][
                    x]) is not True:
                raise Exceptions.PatchError("Missing item(s) for addition. Raised on " + self.change["add"][x] + ".")

        for x in range(0, len(self.change["replace"])):
            if path.isdir(gettempdir() + self.WORK_DIR + "/replace/" + self.change["replace"][x]) is not True \
                    and path.isfile(gettempdir() + self.WORK_DIR + "/replace/" + self.change["replace"][x]) is not True:
                raise Exceptions.PatchError("Missing item(s) for replacement. Raised on " + self.change["replace"][x]
                                            + ".")

        for x in range(0, len(self.change["add"])):
            component = Backend.directory_split_recursive(self.change["add"][x])
            for a in component:
                if path.isdir(path.join(self.target, a)) is False:
                    mkdir(path.join(self.target, a))
            if path.isfile(gettempdir() + self.WORK_DIR + "/add/" + self.change["add"][x]):
                copyfile(gettempdir() + self.WORK_DIR + "/add/" + self.change["add"][x],
                         path.join(self.target, self.change["add"][x]))
            if path.isdir(gettempdir() + self.WORK_DIR + "/add/" + self.change["add"][x]):
                copytree(gettempdir() + self.WORK_DIR + "/add/" + self.change["add"][x],
                         path.join(self.target, self.change["add"][x]))

        for x in range(0, len(self.change["replace"])):
            if path.isfile(path.join(self.target, self.change["replace"][x])) is True:
                remove(path.join(self.target, self.change["replace"][x]))
                copyfile(gettempdir() + self.WORK_DIR + "/replace/" + self.change["replace"][x],
                         path.join(self.target, self.change["replace"][x]))
            elif path.isdir(path.join(self.target, self.change["replace"][x])) is True:
                rmtree(path.join(self.target, self.change["replace"][x]))
                copytree(gettempdir() + self.WORK_DIR + "/replace/" + self.change["replace"][x],
                         path.join(self.target, self.change["replace"][x]))
            else:
                raise Exceptions.TargetError("Target " + self.change["replace"][x] + " for replacement does not exist.")

        for x in range(0, len(self.change["remove"])):
            if path.isdir(path.join(self.target, self.change["remove"][x])) is True:
                rmtree(path.join(self.target, self.change["remove"][x]))
            elif path.isfile(path.join(self.target, self.change["remove"][x])) is True:
                remove(path.join(self.target, self.change["remove"][x]))
            else:
                raise Exceptions.TargetError("Target " + self.change["remove"][
                    x] + " for removal does not exist, or is not a file or directory.")

        with open(self.target + "/VERSION", "w") as version_overwrite_handle:
            # this is redundant, VERSION gets overwritten by replace anyways, since Weave detects two different version
            # files automatically
            # if one day this module needed to be slimmed down, remove this for a slight amount of I/O performance gain
            version_overwrite_handle.truncate(0)
            version_overwrite_handle.write(self.patch_versions[1])

        rmtree(gettempdir() + self.WORK_DIR)

    @staticmethod
    def create_work_directory() -> str:
        """
        Creates directory under the OS temporary directory with a unique name to prevent conflicting instances.
        Returns generated name.
        :return: str, generated tempdir name
        """
        identifier = "/bandage_patcher_session_" + md5(
            str(time()).encode(encoding="ascii", errors="replace")).hexdigest()
        mkdir(gettempdir() + identifier)
        return identifier


class Weave:
    """
    Main class for bandage.Weave instances, which generates patches.
    """

    def __init__(self, release_old: str, release_new: str, output_path: str, set_name: Union[str, None] = None,
                 suppress_missing_versions: bool = False):
        """
        Takes two release files, and compares them for differences, then generates patch file to given output path.
        Inorganic and for robots.

        :param release_old: str, web address or path to old release file
        :param release_new: str, web address or path to new release file
        :param output_path: str, path to output archive, if archive already exists, deletes archive and "overwrites" it
            with the new archive file
        :param set_name: Union[str, None], new patch NAME file, if not None, NAME check is ignored, default None
        :param suppress_missing_versions: bool, if True missing versions error is ignored, Supply class cannot detect
            the release automatically, Patcher must be directed to the patch archive manually, default False
        """
        self.WORK_DIR = Weave.create_work_directory()

        self.release_old = release_old
        self.release_new = release_new

        if path.isdir(output_path) is False:
            raise Exceptions.PatchError("Specified output directory " + output_path + " is not a directory.")

        if "https://" in self.release_old[:8] or "http://" in self.release_old[:8]:
            release_old_grab = Backend.fetch(self.release_old)
            with open(gettempdir() + self.WORK_DIR + "/old/" + path.splitext(self.release_old)[1], "w") as \
                    release_old_data_dump:
                release_old_data_dump.write(release_old_grab.data)
            self.release_old = gettempdir() + self.WORK_DIR + "/old/" + path.splitext(self.release_old)[1]
        else:
            if path.isfile(self.release_old) is False:
                raise Exceptions.ReleaseError("Old release file " + self.release_old + " does not exist.")

        if "https://" in self.release_new[:8] or "http://" in self.release_new[:8]:
            release_new_grab = Backend.fetch(self.release_new)
            with open(gettempdir() + self.WORK_DIR + "/new/" + path.splitext(self.release_new)[1], "w") as \
                    release_new_data_dump:
                release_new_data_dump.write(release_new_grab.data)
            self.release_new = gettempdir() + self.WORK_DIR + "/new/" + path.splitext(self.release_new)[1]
        else:
            if path.isfile(self.release_new) is False:
                raise Exceptions.ReleaseError("New release file " + self.release_new + " does not exist.")

        unpack_archive(self.release_old, gettempdir() + self.WORK_DIR + "/old/")
        unpack_archive(self.release_new, gettempdir() + self.WORK_DIR + "/new/")

        try:
            with open(gettempdir() + self.WORK_DIR + "/old/NAME") as release_name_handle:
                self.release_name_old = release_name_handle.read()
            with open(gettempdir() + self.WORK_DIR + "/new/NAME") as release_name_handle:
                self.release_name_new = release_name_handle.read()
            if self.release_name_new != self.release_name_old and set_name is None:
                raise Exceptions.ReleaseError("NAME files of old and new releases do not match. Old is " +
                                              self.release_name_old + " and new " + self.release_name_new + ".")
        except FileNotFoundError as ParentException:
            if set_name is not None:
                raise Exceptions.ReleaseError("NAME files of old and new releases are missing.") from ParentException

        try:
            with open(gettempdir() + self.WORK_DIR + "/old/VERSION") as release_version_handle:
                self.release_version_old = release_version_handle.read()
            with open(gettempdir() + self.WORK_DIR + "/new/VERSION") as release_version_handle:
                self.release_version_new = release_version_handle.read()
        except FileNotFoundError as ParentException:
            if suppress_missing_versions is False:
                raise Exceptions.VersionError("VERSION files of old and new releases are missing.") from ParentException
            else:
                self.release_version_old = "NaN"
                self.release_version_new = "NaN"

        if suppress_missing_versions is False and len(self.release_version_old.split(" -> ")) != 1 or \
                len(self.release_version_new.split(" -> ")) != 1:
            raise Exceptions.UnableToParseError('Release versions contain " -> " which will disrupt Patcher when '
                                                'trying to read the VERSIONS header.')

        self.index = Weave.comparison(self)

        with open(gettempdir() + self.WORK_DIR + "/patch/CHANGE.json", "w") as changelog_dump_handle:
            jsondump({"remove": str(self.index[0]), "add": str(self.index[1]), "keep": str(self.index[2]),
                      "replace": str(self.index[3])}, changelog_dump_handle)

        for x in range(0, len(self.index[1])):
            component = Backend.directory_split_recursive(self.index[1][x])
            for a in component:
                if path.isdir(gettempdir() + self.WORK_DIR + "/patch/add/" + a) is False:
                    mkdir(gettempdir() + self.WORK_DIR + "/patch/add/" + a)
            if path.isfile(gettempdir() + self.WORK_DIR + "/new/" + self.index[1][x]) is True:
                copyfile(gettempdir() + self.WORK_DIR + "/new/" + self.index[1][x], gettempdir() + self.WORK_DIR +
                         "/patch/add/" + self.index[1][x])
            if path.isdir(gettempdir() + self.WORK_DIR + "/new/" + self.index[1][x]) is True:
                copytree(gettempdir() + self.WORK_DIR + "/new/" + self.index[1][x], gettempdir() + self.WORK_DIR +
                         "/patch/add/" + self.index[1][x])

        for y in range(0, len(self.index[3])):
            component = Backend.directory_split_recursive(self.index[3][y])
            for b in component:
                if path.isdir(gettempdir() + self.WORK_DIR + "/patch/replace/" + b) is False:
                    mkdir(gettempdir() + self.WORK_DIR + "/patch/replace/" + b)
            if path.isfile(gettempdir() + self.WORK_DIR + "/new/" + self.index[3][y]) is True:
                copyfile(gettempdir() + self.WORK_DIR + "/new/" + self.index[3][y], gettempdir() + self.WORK_DIR +
                         "/patch/replace/" + self.index[3][y])
            if path.isdir(gettempdir() + self.WORK_DIR + "/new/" + self.index[3][y]) is True:
                copytree(gettempdir() + self.WORK_DIR + "/new/" + self.index[3][y], gettempdir() + self.WORK_DIR +
                         "/patch/replace/" + self.index[3][y])

        with open(gettempdir() + self.WORK_DIR + "/patch/VERSIONS", "w") as release_version_handle:
            release_version_handle.write(self.release_version_old + " -> " + self.release_version_new)
        if set_name is None:
            with open(gettempdir() + self.WORK_DIR + "/patch/NAME", "w") as release_name_handle:
                release_name_handle.write(self.release_name_new)
            base_name = (output_path + self.release_name_new + "_" + self.release_version_old + "_to_" +
                         self.release_version_new + "_bandage_patch")
            make_archive(root_dir=gettempdir() + self.WORK_DIR + "/patch/", base_name=base_name, format="zip")
        else:
            with open(gettempdir() + self.WORK_DIR + "/patch/NAME", "w") as release_name_handle:
                release_name_handle.write(set_name)
            base_name = (output_path + set_name + "_" + self.release_version_old + "_to_" + self.release_version_new +
                         "_bandage_patch")
            make_archive(root_dir=gettempdir() + self.WORK_DIR + "/patch/", base_name=base_name, format="zip")

        # TODO archive checksum generation

        # turns out Windows doesn't automatically clear out the temp directory!
        # (https://superuser.com/questions/296824/when-is-a-windows-users-temp-directory-cleaned-out)
        rmtree(gettempdir() + self.WORK_DIR)

    @staticmethod
    def create_work_directory() -> str:
        """
        Creates directory under the OS temporary directory with a unique name to prevent conflicting instances.
        Returns generated name.
        :return: str, generated tempdir name
        """
        identifier = "/bandage_weave_session_" + md5(str(time()).encode(encoding="ascii", errors="replace")).hexdigest()
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
        with redirect_stdout(handle):
            dircmp(gettempdir() + self.WORK_DIR + "/old/", gettempdir() + self.WORK_DIR + "/new/").report_full_closure()
        raw = handle.getvalue().split("\n")
        dump = [[], [], [], []]
        # directory path appends for old and new archive, allows for handling of sub-directories.
        parsing_directory = ""
        for x in range(0, len(raw)):
            if raw[x][:4] == "diff":
                if len(raw[x].split(" ")) != 3:
                    raise Exceptions.UnableToParseError("Release archives contain directories with spaces in their "
                                                        "names. This breaks comparison interpretation.") from None
                parsing_directory = raw[x].split(" ")[1].lstrip(gettempdir()).lstrip(self.WORK_DIR).lstrip("/old/")
                if parsing_directory != "":
                    parsing_directory += "/"
            if raw[x][:(8 + len(
                    gettempdir() + self.WORK_DIR + "/old/"))] == "Only in " + gettempdir() + self.WORK_DIR + "/old/":
                for_extend = raw[x].lstrip(
                    "Only in " + gettempdir() + self.WORK_DIR + "/old/" + parsing_directory).strip("[]").split(", ")
                for y in range(0, len(for_extend)):
                    for_extend[y] = parsing_directory + for_extend[y].strip("'")
                dump[0].extend(for_extend)
            if raw[x][:(8 + len(
                    gettempdir() + self.WORK_DIR + "/new/"))] == "Only in " + gettempdir() + self.WORK_DIR + "/new/":
                for_extend = raw[x].lstrip(
                    "Only in " + gettempdir() + self.WORK_DIR + "/new/" + parsing_directory).strip("[]").split(", ")
                for y in range(0, len(for_extend)):
                    for_extend[y] = parsing_directory + for_extend[y].strip("'")
                dump[1].extend(for_extend)
            if raw[x][:18] == "Identical files : ":
                for_extend = raw[x].lstrip("Identical files : ").strip("[]").split(", ")
                for y in range(0, len(for_extend)):
                    for_extend[y] = parsing_directory + for_extend[y].strip("'")
                dump[2].extend(for_extend)
            if raw[x][:18] == "Differing files : ":
                for_extend = raw[x].lstrip("Differing files : ").strip("[]").split(", ")
                for y in range(0, len(for_extend)):
                    for_extend[y] = parsing_directory + for_extend[y].strip("'")
                dump[3].extend(for_extend)
        return dump


class Supply:
    """
    Main class for bandage.Supply instances, which checks for new patches on remotes.
    """

    def __init__(self, remote: str, version_file: str):
        """
        Checks a remote HTTP endpoint for new patches. Inorganic and for robots.
        If no exception is thrown, dumps status and patch download URL to self.result and self.patch_web_source
        respectively, which can be retrieved as a list through method bandage.Supply.realize.

        The remote parameter should be an HTTPS/HTTP address pointing to a web server, or a Github release tagged
        BANDAGE.
        For pointing to a Github repository's contents, use raw.githubusercontent.com.

        If bandage.Supply succeeded in finding headers and looking up lineage series, however finds the current version
        to be the latest, self.result is 0.
        If bandage.Supply succeeded in finding headers and looking up lineage series, and finds a patch to be applied
        for updating, self.result is -1 with self.patch_web_source as web address to patch file.
        If bandage.Supply succeeded in finding headers and looking up lineage series, however finds no patch available
        to upgrade with, self.result is 1.
        If bandage.Supply raised an exception, self.result and self.patch_web_source are None.

        Preliminary information if obtained is dumped into self.pre_collect. Contains version list and patches
        available, as list object. Retrieved through bandage.Supply.pre_collect_dump.

        See documentation for more information.

        :param remote: str, web address of patch host
        :param version_file: str, path to version file
        """
        self.patch_web_source = None
        self.result = 1

        self.remote = remote
        self.version_file = version_file

        try:
            with open(version_file) as version_handle:
                self.version = version_handle.read()
        except FileNotFoundError as ParentException:
            raise Exceptions.VersionError("VERSION file directed by path " + self.version_file + " does not exist.") \
                from ParentException

        if "https://" not in self.remote[:8] and "http://" not in self.remote[:8]:
            raise Exceptions.RemoteError("Supplied remote " + self.remote + " is not a HTTP/HTTPS web address.")

        if self.remote[-1:] != "/":
            self.remote += "/"

        if "https://github.com" == self.remote[:18] or "http://github.com" == self.remote[:18]:
            if self.remote[-22:] == "/releases/tag/BANDAGE/":
                self.pre_collect = [Backend.fetch(
                    self.remote.rstrip("/tag/BANDAGE/") + "/download/BANDAGE/BANDAGE_PATCHES").data.decode(
                    encoding="utf-8", errors="replace").split("\n"), Backend.fetch(
                    self.remote.rstrip("/tag/BANDAGE/") + "/download/BANDAGE/BANDAGE_LINEAGE").data.decode(
                    encoding="utf-8", errors="replace").split("\n")]
                for x in range(0, len(self.pre_collect[1])):
                    if self.version == self.pre_collect[1][x].rstrip("\r"):
                        self.version_gap = x
                        break
                if self.version_gap is None:
                    raise Exceptions.VersionError(
                        "Version " + self.version + " does not exist in remote's lineage header.")
                elif self.version_gap == 0:
                    self.result = 0
                else:
                    compatible_sources = []
                    for x in range(0, len(self.pre_collect[0])):
                        if self.pre_collect[0][x].split("||")[0].split(" -> ")[0] == self.version:
                            compatible_sources.append(self.pre_collect[0][x].split("||")[0])
                    if not compatible_sources:
                        self.result = 1
                    else:
                        for x in self.pre_collect[0]:
                            for y in compatible_sources:
                                if y.split(" -> ")[1] == x.split("||")[0].split(" -> ")[1]:
                                    self.result = -1
                                    self.patch_web_source = self.remote.rstrip("/BANDAGE/") + path.join(
                                        "/download/BANDAGE/", x.split("||")[1])
            else:
                raise Exceptions.RemoteError("Remote defined as " + self.remote + " is not supported.")
        else:
            self.pre_collect = [
                Backend.fetch(self.remote + "BANDAGE_PATCHES").data.decode(encoding="utf-8", errors="replace").split(
                    "\n"),
                Backend.fetch(self.remote + "BANDAGE_LINEAGE").data.decode(encoding="utf-8", errors="replace").split(
                    "\n")]
            for x in range(0, len(self.pre_collect[1])):
                if self.version == self.pre_collect[1][x]:
                    self.version_gap = x
                    break
            if self.version_gap is None:
                raise Exceptions.VersionError("Version " + self.version + " does not exist in remote's lineage header.")
            elif self.version_gap == 0:
                self.result = 0
            else:
                compatible_sources = []
                for x in range(0, len(self.pre_collect[0])):
                    if self.pre_collect[0][x].split("||")[0].split(" -> ")[0] == self.version:
                        compatible_sources.append(self.pre_collect[0][x].split("||")[0])
                if not compatible_sources:
                    self.result = 1
                else:
                    for x in self.pre_collect[0]:
                        for y in compatible_sources:
                            if y.split(" -> ")[1] == x.split("||")[0].split(" -> ")[1]:
                                self.result = -1
                                if x.split("||")[1][:8] == "https://" or "http://" in x.split("||")[1][:8]:
                                    self.patch_web_source = x.split("||")[1]
                                else:
                                    self.patch_web_source = path.join(self.remote, x.split("||")[1])

    def realize(self) -> list:
        """
        Returns list containing self.result and self.patch_web_source.
        :return: list, [self.result, self.patch_web_source]
        """
        return [self.result, self.patch_web_source]

    def pre_collect_dump(self) -> list:
        """
        Returns self.pre_collect_dump.
        :return: list, pre_collect_dump
        """
        return self.pre_collect
