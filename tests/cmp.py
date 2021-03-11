import filecmp
from io import StringIO
from contextlib import redirect_stdout

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
        fcomp = filecmp.cmpfiles(self.left, self.right, self.common_files, shallow = False)
        self.same_files, self.diff_files, self.funny_files = fcomp

handle = StringIO()
with redirect_stdout(handle):
    dircmp('F://bandage//tests//a', 'F://bandage//tests//b').report_full_closure()
print(len(handle.getvalue().rstrip("\n").split("\n")))
print(handle.getvalue().rstrip("\n").split("\n"))