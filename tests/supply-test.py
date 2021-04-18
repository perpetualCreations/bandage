"""
unit test for bandage.Supply
"""

import bandage

supplier = bandage.Supply("https://github.com/perpetualCreations/bandage/releases/tag/BANDAGE",
                          "F://bandage//tests//test_target//VERSION")

print(supplier.realize())
print(supplier.pre_collect_dump())
print(supplier.version_gap)
