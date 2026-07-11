"""Runs every test_* function in this directory without requiring pytest."""
import importlib
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_MODULES = [
    "test_citations",
    "test_field_presence",
    "test_health_score",
]


def main():
    sys.path.insert(0, os.path.dirname(__file__))
    total = 0
    failed = 0
    for mod_name in TEST_MODULES:
        mod = importlib.import_module(mod_name)
        for name in dir(mod):
            if name.startswith("test_"):
                total += 1
                fn = getattr(mod, name)
                try:
                    fn()
                    print(f"PASS  {mod_name}.{name}")
                except Exception:
                    failed += 1
                    print(f"FAIL  {mod_name}.{name}")
                    traceback.print_exc()
    print(f"\n{total - failed}/{total} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
