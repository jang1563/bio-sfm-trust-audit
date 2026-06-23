import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase2_truth import (
    ca_lddt,
    lddt_for_structures,
    match_chains,
    matched_ca_pairs,
    nw_match,
)


class AlignTests(unittest.TestCase):
    def test_identical_sequences_align_fully(self):
        self.assertEqual(nw_match("ACDEF", "ACDEF"), [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)])

    def test_alignment_handles_missing_residue(self):
        # ref resolved seq missing the 'D' (index 2 of full); full pred has it
        pairs = nw_match("ACEF", "ACDEF")
        # every ref residue maps to the matching pred residue
        self.assertEqual([(i, j) for i, j in pairs if "ACEF"[i] == "ACDEF"[j]],
                         [(0, 0), (1, 1), (2, 3), (3, 4)])


class LddtMathTests(unittest.TestCase):
    def test_identical_coords_give_one(self):
        pts = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (4.0, 0.0, 0.0), (6.0, 0.0, 0.0)]
        matched = [(p, p) for p in pts]
        self.assertAlmostEqual(ca_lddt(matched), 1.0, places=9)

    def test_known_value_for_2x_scaling(self):
        ref = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (4.0, 0.0, 0.0), (6.0, 0.0, 0.0)]
        pred = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (8.0, 0.0, 0.0), (12.0, 0.0, 0.0)]
        matched = list(zip(ref, pred))
        # diffs over 6 pairs = [2,4,6,2,4,2]; preserved only at t=4 for diff<4 (the three 2s)
        # lddt = mean(0,0,0, 3/6) = 0.125
        self.assertAlmostEqual(ca_lddt(matched), 0.125, places=9)

    def test_rigid_shift_preserves_lddt(self):
        # lDDT is superposition-free: a rigid translation must not change it
        ref = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (4.0, 0.0, 0.0)]
        pred = [(10.0, 5.0, -3.0), (12.0, 5.0, -3.0), (14.0, 5.0, -3.0)]
        self.assertAlmostEqual(ca_lddt(list(zip(ref, pred))), 1.0, places=9)

    def test_too_few_pairs_returns_none(self):
        self.assertIsNone(ca_lddt([((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))]))


class ChainMatchTests(unittest.TestCase):
    def test_matches_chains_by_sequence_identity(self):
        ref = {"A": [(c, (0.0, 0.0, 0.0)) for c in "ACDEFGHIK"],
               "B": [(c, (0.0, 0.0, 0.0)) for c in "MNPQRSTVW"]}
        pred = {"X": [(c, (0.0, 0.0, 0.0)) for c in "MNPQRSTVW"],
                "Y": [(c, (0.0, 0.0, 0.0)) for c in "ACDEFGHIK"]}
        self.assertEqual(sorted(match_chains(ref, pred)), [("A", "Y"), ("B", "X")])

    def test_lddt_for_structures_identical(self):
        chain = [(c, (float(i) * 2.0, 0.0, 0.0)) for i, c in enumerate("ACDEFGHIK")]
        ref = {"A": chain}
        pred = {"A": chain}
        self.assertAlmostEqual(lddt_for_structures(ref, pred), 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
