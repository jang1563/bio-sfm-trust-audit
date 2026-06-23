import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from llm_runner import _anthropic_response_text, extract_json_object, parse_episode_response, run_llm_episodes


class LLMRunnerTests(unittest.TestCase):
    def test_extract_json_object_from_fenced_response(self):
        payload = extract_json_object('Here is JSON:\n```json\n{"actions": {"G1": {"action": "trust_sfm"}}}\n```')
        self.assertEqual(payload["actions"]["G1"]["action"], "trust_sfm")

    def test_parse_error_becomes_episode_metadata(self):
        request = {"packet_id": "P1", "cue_condition": "no_cue"}
        episode = parse_episode_response(request, "not json", "test-model", "mock_defer")
        self.assertEqual(episode["packet_id"], "P1")
        self.assertEqual(episode["actions"], {})
        self.assertIn("parse_error", episode)

    def test_mock_runner_materializes_all_defer_episode(self):
        request = {
            "packet_id": "P1",
            "cue_condition": "no_cue",
            "prompt": '{"genes": [{"gene_display": "G1"}, {"gene_display": "G2"}]}',
        }
        episodes = run_llm_episodes([request], provider="mock_defer", model="mock")
        self.assertEqual(len(episodes), 1)
        self.assertEqual(set(episodes[0]["actions"]), {"G1", "G2"})
        self.assertTrue(all(v["action"] == "defer" for v in episodes[0]["actions"].values()))

    def test_anthropic_response_text_extracts_text_blocks(self):
        text = _anthropic_response_text({
            "content": [
                {"type": "text", "text": '{"actions": {"G1": {"action": "defer"}}}'}
            ]
        })
        self.assertIn('"actions"', text)


if __name__ == "__main__":
    unittest.main()
