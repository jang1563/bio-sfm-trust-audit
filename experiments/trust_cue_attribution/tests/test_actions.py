import unittest

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from actions import normalize_action, parse_action_record


class ActionTests(unittest.TestCase):
    def test_aliases_normalize(self):
        self.assertEqual(normalize_action("verify"), "verify_assay")
        self.assertEqual(normalize_action("additive"), "default_baseline")
        self.assertEqual(normalize_action("trust model"), "trust_sfm")

    def test_parse_json_and_plain_text(self):
        self.assertEqual(parse_action_record('{"action": "verify", "confidence": 0.8}')["action"], "verify_assay")
        self.assertEqual(parse_action_record("I would use the baseline")["action"], "default_baseline")


if __name__ == "__main__":
    unittest.main()
