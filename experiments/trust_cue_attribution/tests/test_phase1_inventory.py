import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1_inventory import (
    _h5dump_dataspace_size,
    _quoted_h5dump_strings,
    build_scfoundation_input_inventory,
    summarize_gene_overlap,
)


def _anndata_stack_available():
    try:
        import anndata  # noqa: F401
        import numpy  # noqa: F401
        import pandas  # noqa: F401
    except Exception:
        return False
    return True


class Phase1InventoryTests(unittest.TestCase):
    def test_gene_overlap_is_case_insensitive(self):
        result = summarize_gene_overlap(["Actb", "Gapdh", "Extra"], ["ACTB", "GAPDH", "MALAT1"])

        self.assertEqual(result["input_gene_count"], 3)
        self.assertEqual(result["vocabulary_gene_count"], 3)
        self.assertEqual(result["overlap_count"], 2)
        self.assertAlmostEqual(result["overlap_fraction_of_input"], 2 / 3)

    def test_missing_input_blocks_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gene_index = root / "gene_index.tsv"
            gene_index.write_text("gene_name\tgene_id\nACTB\t0\n")

            result = build_scfoundation_input_inventory(
                input_data=str(root / "missing.h5ad"),
                gene_index=str(gene_index),
            )

        self.assertEqual(result["status"], "blocked_missing_input_data")

    def test_h5dump_string_parser(self):
        text = '''
DATA {
   (0): "ABL1", "ABO",
   (2): "GAPDH"
}
DATASPACE  SIMPLE { ( 834 ) / ( 834 ) }
'''
        self.assertEqual(_quoted_h5dump_strings(text), ["ABL1", "ABO", "GAPDH"])
        self.assertEqual(_h5dump_dataspace_size(text), 834)

    @unittest.skipIf(not _anndata_stack_available(), "anndata stack unavailable")
    def test_ready_h5ad_inventory(self):
        import anndata as ad
        import numpy as np
        import pandas as pd

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gene_index = root / "gene_index.tsv"
            gene_index.write_text("gene_name\tgene_id\nACTB\t0\nGAPDH\t1\nMALAT1\t2\n")
            h5ad = root / "input.h5ad"
            adata = ad.AnnData(
                X=np.ones((2, 3)),
                obs=pd.DataFrame(index=["cell1", "cell2"]),
                var=pd.DataFrame(index=["ACTB", "GAPDH", "EXTRA"]),
            )
            adata.write_h5ad(h5ad)

            result = build_scfoundation_input_inventory(
                input_data=str(h5ad),
                gene_index=str(gene_index),
                min_overlap=2,
            )

        self.assertEqual(result["status"], "ready_for_adapter_smoke")
        self.assertEqual(result["gene_overlap"]["overlap_count"], 2)
        self.assertNotIn("gene_names", result["h5ad"])
        self.assertIn("low_fraction_of_input_genes_mapped_to_scfoundation_vocabulary", result["quality_warnings"])
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()
