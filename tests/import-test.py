"""
import test for bandage.
"""

import bandage
try:
    raise bandage.Exceptions.TargetError("test")
except bandage.Exceptions.TargetError:
    print("test")
pass
