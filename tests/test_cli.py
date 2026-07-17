import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from ownyourtime.cli import main


class CliTests(unittest.TestCase):
    def test_generate_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            stdout = StringIO()
            with redirect_stdout(stdout):
                result = main(
                    [
                        "generate",
                        "--topic",
                        "Automatiser un ETL",
                        "--dry-run",
                        "--output-dir",
                        str(Path(temporary_directory)),
                    ]
                )

            self.assertEqual(result, 0)
            output = json.loads(stdout.getvalue())
            self.assertEqual(output["status"], "needs_review")
            self.assertGreaterEqual(output["quality_score"], 7.5)


if __name__ == "__main__":
    unittest.main()
