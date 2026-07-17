import unittest

import main


class LegacyMainCliTests(unittest.TestCase):
    def test_setup_flag_does_not_require_generation_arguments(self) -> None:
        args = main.build_parser().parse_args(["--setup"])
        self.assertTrue(args.setup)
        self.assertIsNone(args.config)
        self.assertIsNone(args.output)


if __name__ == "__main__":
    unittest.main()
