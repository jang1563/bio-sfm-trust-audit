#!/usr/bin/env bash
# Phase 2 leakage audit — sequence-identity search of the 80 v1 targets vs the full PDB.
# Run on Cayuga. pdb_seqres.txt from https://files.wwpdb.org/pub/pdb/derived_data/pdb_seqres.txt.gz
# Query built by prefixing each target fasta header with its target_id (<tid>|<chain>).
mmseqs easy-search query80.fasta pdb_seqres.txt results.m8 tmp \
  --format-output query,target,pident,alnlen,qcov,tcov,evalue,bits \
  -s 6 --max-seqs 500 -e 0.001 --threads 8
# Then: leak_dates.py joins non-self hits (pident>=30, qcov>=0.8) to RCSB release dates.
