import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase2_curate_pdb import (
    build_search_query,
    is_protein_sequence,
    parse_rcsb_fasta,
    protein_chains,
    select_for_regime,
    to_boltz_fasta,
)

PROT = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
NUC = "ACGTACGTACGTACGTACGTACGTACGTACGT"


class QueryTests(unittest.TestCase):
    def test_monomer_query_constrains_single_protein_entity(self):
        q = build_search_query(released_after="2025-07-01", max_resolution=3.0, regime="monomer", rows=10)
        attrs = [n["parameters"]["attribute"] for n in q["query"]["nodes"]]
        self.assertIn("rcsb_entry_info.polymer_entity_count_protein", attrs)
        self.assertIn("rcsb_entry_info.deposited_polymer_entity_instance_count", attrs)
        self.assertIn("rcsb_accession_info.initial_release_date", attrs)
        self.assertEqual(q["return_type"], "entry")

    def test_complex_query_requires_two_plus_protein_entities(self):
        q = build_search_query(released_after="2025-07-01", max_resolution=3.0, regime="complex", rows=10)
        node = [n for n in q["query"]["nodes"]
                if n["parameters"]["attribute"] == "rcsb_entry_info.polymer_entity_count_protein"][0]
        self.assertEqual(node["parameters"]["operator"], "greater_or_equal")
        self.assertEqual(node["parameters"]["value"], 2)

    def test_bad_regime_raises(self):
        with self.assertRaises(ValueError):
            build_search_query(released_after="2025-07-01", max_resolution=3.0, regime="dimerish", rows=10)


class ParseTests(unittest.TestCase):
    def test_parse_multi_record_fasta(self):
        text = f">1ABC_1|Chain A|x\n{PROT}\n>1ABC_2|Chain B|y\n{NUC}\n"
        recs = parse_rcsb_fasta(text)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0][1], PROT)

    def test_protein_detection(self):
        self.assertTrue(is_protein_sequence(PROT))
        self.assertFalse(is_protein_sequence(NUC))
        self.assertFalse(is_protein_sequence("MKV"))  # too short

    def test_protein_chains_filters_nucleotide(self):
        text = f">e1\n{PROT}\n>e2\n{NUC}\n"
        self.assertEqual(protein_chains(text), [PROT])


class RegimeSelectionTests(unittest.TestCase):
    def test_monomer_requires_exactly_one_chain(self):
        self.assertEqual(select_for_regime([PROT], regime="monomer", min_len=50, max_total_len=1200, max_chains=4), [PROT])
        self.assertIsNone(select_for_regime([PROT, PROT], regime="monomer", min_len=50, max_total_len=1200, max_chains=4))

    def test_complex_requires_two_to_max_chains(self):
        self.assertEqual(len(select_for_regime([PROT, PROT], regime="complex", min_len=50, max_total_len=1200, max_chains=4)), 2)
        self.assertIsNone(select_for_regime([PROT], regime="complex", min_len=50, max_total_len=1200, max_chains=4))

    def test_total_length_cap(self):
        self.assertIsNone(select_for_regime([PROT, PROT], regime="complex", min_len=50, max_total_len=100, max_chains=4))

    def test_to_boltz_fasta_labels_chains(self):
        out = to_boltz_fasta([PROT, PROT])
        self.assertIn(">A|protein", out)
        self.assertIn(">B|protein", out)


if __name__ == "__main__":
    unittest.main()
