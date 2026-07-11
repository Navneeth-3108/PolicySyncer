"""
Dev convenience only: runs every test_ function in this directory using
plain stdlib, for environments where `pip install pytest` isn't possible.
Prefer `pytest tests/` normally. Mirrors policy_layer1/2/3's own runner.
"""

import importlib
import sys
import os
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_MODULES = [
    "test_adapter",
]

total = 0
failed = 0

for mod_name in TEST_MODULES:
    mod = importlib.import_module(mod_name)
    for attr in dir(mod):
        if attr.startswith("test_"):
            fn = getattr(mod, attr)
            total += 1
            try:
                fn()
                print(f"PASS  {mod_name}.{attr}")
            except Exception:
                failed += 1
                print(f"FAIL  {mod_name}.{attr}")
                traceback.print_exc()

print(f"\n{total - failed}/{total} passed")
sys.exit(1 if failed else 0)
