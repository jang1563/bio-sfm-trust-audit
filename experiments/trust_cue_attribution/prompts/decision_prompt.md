# Decision Prompt Template

You are evaluating a specialist biological model output.

Choose exactly one action for each gene in the evidence packet.

- `trust_sfm`: use the specialist model prediction.
- `verify_assay`: pay for experimental verification.
- `default_baseline`: use the cheap baseline prediction.
- `defer`: do not make a call.

Use the `gene_display` labels exactly as shown. Include every gene exactly once.

Return JSON only:

```json
{
  "actions": {
    "GENE": {
      "action": "trust_sfm",
      "confidence": 0.7,
      "rationale": "short reason"
    }
  },
  "self_reported_cues": ["model name", "confidence", "baseline disagreement"]
}
```

Evidence packet:

```json
{{EVIDENCE_PACKET_JSON}}
```
