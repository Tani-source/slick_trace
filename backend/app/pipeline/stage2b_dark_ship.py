"""
stage2b_dark_ship.py — Offline script to generate mock dark-ship detection.
"""

import json
import os
from app.config import PROTOTYPE_CACHE_DIR

def run():
    os.makedirs(PROTOTYPE_CACHE_DIR, exist_ok=True)
    out_path = os.path.join(PROTOTYPE_CACHE_DIR, "dark_ship.json")
    
    data = {
        "prototype": True,
        "label": "Prototype — architecture below",
        "detected_vessels": [
            {
                "lat": 28.52, 
                "lon": -90.0, 
                "confidence": 0.81, 
                "note": "No AIS match within 3 NM"
            }
        ],
        "method": "CFAR (constant false alarm rate) on SAR amplitude image",
    }
    
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
        
    print(f"Generated prototype cache: {out_path}")

if __name__ == "__main__":
    run()
