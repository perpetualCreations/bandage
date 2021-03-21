"""
import test for bandage.
"""

import bandage
try:
    raise bandage.Exceptions.MissingVersionsError("test")
except bandage.Exceptions.MissingVersionsError:
    print("test")
pass
