"""Stand ins for what abgal reads from outside: adb and the /proc tree.

Tests under unit/ and integration/ use these, so neither needs adb, KVM or a
running emulator. Tests under e2e/ never do.
"""
