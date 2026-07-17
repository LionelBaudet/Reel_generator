import json
import tempfile
import unittest
from pathlib import Path

from ownyourtime.models import RunStatus
from ownyourtime.providers import OfflineContentProvider
from ownyourtime.quality import QualityGate
from ownyourtime.store import ArtifactStore
from ownyourtime.workflow import CreateReelWorkflow


class CreateReelWorkflowTests(unittest.TestCase):
    def test_offline_workflow_creates_traceable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workflow = CreateReelWorkflow(
                provider=OfflineContentProvider(),
                store=ArtifactStore(Path(temporary_directory)),
                quality_gate=QualityGate(minimum_score=7.5),
            )

            run = workflow.run("Automatiser un reporting Power BI")

            self.assertIs(run.status, RunStatus.NEEDS_REVIEW)
            self.assertIsNotNone(run.quality)
            self.assertTrue(run.quality.publishable)
            self.assertIsNotNone(run.script)
            self.assertLessEqual(15, run.script.duration_seconds)
            self.assertLessEqual(run.script.duration_seconds, 30)
            self.assertTrue((run.output_directory / "run.json").exists())
            self.assertTrue((run.output_directory / "script.json").exists())
            self.assertTrue((run.output_directory / "quality.json").exists())

            saved = json.loads((run.output_directory / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["run_id"], run.run_id)
            self.assertEqual(saved["status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
