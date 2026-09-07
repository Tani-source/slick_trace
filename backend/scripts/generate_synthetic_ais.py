import os
import csv
import random
from datetime import datetime, timedelta

output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "ais_2023_11_15_synthetic.csv")

header = [
    "MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading", 
    "VesselName", "IMO", "CallSign", "VesselType", "Status", "Length", 
    "Width", "Draft", "Cargo", "TransceiverClass"
]

start_time = datetime(2023, 11, 15, 12, 0, 0)
num_vessels = 50

# Main Pass region bounding box
min_lat, max_lat = 28.5, 29.5
min_lon, max_lon = -89.5, -88.0

with open(output_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    
    for v_id in range(num_vessels):
        mmsi = 366000000 + v_id
        v_name = f"VESSEL_{v_id}"
        v_type = random.choice([70, 80, 30]) # Tanker, Cargo, Fishing
        draft = round(random.uniform(5.0, 15.0), 1) if random.random() > 0.2 else ""
        
        # Start position
        lat = random.uniform(min_lat, max_lat)
        lon = random.uniform(min_lon, max_lon)
        sog = random.uniform(8.0, 15.0)
        cog = random.uniform(0, 360)
        
        for step in range(60): # 60 hours
            current_time = start_time + timedelta(hours=step)
            
            # Simple linear movement
            lat += (sog / 60) * 0.016 * (1 if cog < 180 else -1)
            lon += (sog / 60) * 0.016 * (1 if cog > 90 and cog < 270 else -1)
            
            row = [
                mmsi,
                current_time.strftime("%Y-%m-%dT%H:%M:%S"),
                round(lat, 5),
                round(lon, 5),
                round(sog, 1),
                round(cog, 1),
                round(cog, 0),
                v_name,
                "", "", v_type, 0, 100, 20, draft, "", "A"
            ]
            writer.writerow(row)

print(f"Generated synthetic AIS data at: {output_path}")
