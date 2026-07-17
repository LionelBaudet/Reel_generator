import unittest

from pydantic import ValidationError

from ownyourtime.models import HookCandidate


class HookCandidateTests(unittest.TestCase):
    def test_hook_rejects_more_than_twelve_words(self) -> None:
        with self.assertRaisesRegex(ValidationError, "at most 12 words"):
            HookCandidate(
                text="un deux trois quatre cinq six sept huit neuf dix onze douze treize",
                angle="test",
                predicted_score=7,
            )

    def test_hook_score_must_stay_between_zero_and_ten(self) -> None:
        with self.assertRaises(ValidationError):
            HookCandidate(text="Un hook valide", angle="test", predicted_score=11)


if __name__ == "__main__":
    unittest.main()
