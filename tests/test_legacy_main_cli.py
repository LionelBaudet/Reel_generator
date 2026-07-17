import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("legacy_main", ROOT / "main.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load legacy main.py")
main = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(main)


class LegacyMainCliTests(unittest.TestCase):
    def test_setup_flag_does_not_require_generation_arguments(self) -> None:
        args = main.build_parser().parse_args(["--setup"])
        self.assertTrue(args.setup)
        self.assertIsNone(args.config)
        self.assertIsNone(args.output)


if __name__ == "__main__":
    unittest.main()
