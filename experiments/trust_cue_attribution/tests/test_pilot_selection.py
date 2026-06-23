import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from cues import generate_cue_packets
from episodes import make_request_records
from panels import PanelConfig, build_panels_from_rows
from pilot_selection import DEFAULT_MAIN_CUES, filter_requests, select_stratified_panels
from test_panels_cues_scoring import single_effects, synthetic_rows


class PilotSelectionTests(unittest.TestCase):
    def test_selects_nonleakage_pilot_requests(self):
        panels = build_panels_from_rows(
            synthetic_rows(),
            single_effects(),
            PanelConfig(n=10, min_wrong=3, min_correct=3),
        )
        packets = generate_cue_packets(panels)
        requests = make_request_records(packets, "{{EVIDENCE_PACKET_JSON}}", model="test")
        panel_ids, summaries = select_stratified_panels(panels, n_panels=2, seed=1)
        subset = filter_requests(requests, panel_ids, DEFAULT_MAIN_CUES)
        self.assertEqual(len(panel_ids), 2)
        self.assertEqual(len(summaries), 2)
        self.assertEqual(len(subset), 2 * len(DEFAULT_MAIN_CUES))
        self.assertNotIn("raw_assay_stats_shown", {row["cue_condition"] for row in subset})


if __name__ == "__main__":
    unittest.main()
