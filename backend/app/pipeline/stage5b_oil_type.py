"""
stage5b_oil_type.py — Offline script to generate mock oil-type fingerprint.
"""

import json
import os
from app.config import PROTOTYPE_CACHE_DIR

def run():
    os.makedirs(PROTOTYPE_CACHE_DIR, exist_ok=True)
    out_path = os.path.join(PROTOTYPE_CACHE_DIR, "oil_type.json")
    
    data = {
        "prototype": True,
        "label": "Prototype — architecture below",
        "classified_type": "crude",
        "confidence": 0.74,
        "method": "Sentinel-2 band ratio (B11/B8A) + sklearn SVM classifier",
        "note": "Pre-computed on demo dataset; no live inference in this build.",
    }
    
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
        
    print(f"Generated prototype cache: {out_path}")

if __name__ == "__main__":
    run()
