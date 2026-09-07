from __future__ import annotations

from typing import List, Optional
import time
from pathlib import Path

from ..config import OPEN_DRIFT_EXECUTABLE, WIND_VALID_RANGE_M_S, AGE_WEATHERING_LIMIT_HOURS
from ..services.run_store import save_stage_output, load_stage_output, load_pipeline_status

class Stage1Error(Exception):
    pass

class Stage1Error(Stage1Error):
    pass

class Stage1:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.stage0_output = None
        self.origin_region = None
        self.time_window = None
        self.running = False

    def run_backward_drift(self) -> dict:
        """Execute Stage 1: Backward drift simulation."""
        if not run_store.run_exists(self.run_id):
            raise Stage1Error(f"Run {self.run_id} not found")
            
        # Load Stage 0 output if not already available
        if self.stage0_output is None:
            slick_polygon = run_store.load_stage_output(self.run_id, "slick_polygon")
            if result is None:
                raise Stage1Error("Stage 0 (perception) not completed")
            self.stage0_output = result["data"]
        
        # Validate Stage 0 output
        if not self.stage0_output:
            raise Stage1Error("Stage 0 output missing")
            
        # Get Stage 1 configuration
        stage1_config = self._get_stage1_config()
        
        # Execute backward drift simulation
        self._run_backward_drift()
        
        # Update pipeline status
        self._update_status("done", "Stage 1 completed successfully")
        return {"status": "success", "stage": "backward_drift", "origin_region": self.origin_region}

    def _get_stage1_config(self) -> dict:
        """Return Stage 1 configuration."""
        return {
            "stage_name": "backward_drift",
            "timeout_minutes": 30,
            "max_particles": 1000,
            "current_data_type": "current",
            "wind_data_type": "wind",
            "sar_input": "slick_polygon",
            "stage_description": "Backward drift simulation from slick centroid to origin region"
        }

    def _run_backward_drift(self) -> None:
        """Execute the backward drift simulation."""
        # 1. Load Stage 0 slick polygon
        slick_polygon = self.stage0_output
        if not slick_polygon:
            raise Stage1Error("Stage 0 slick polygon not available")
            
        # 2. Calculate origin region using OpenDrift (reversed)
        origin_region = self._calculate_origin_region(slick_polygon)
        self.origin_region = origin_region
        
        # 3. Set time window based on Stage 0 age
        age_hours = self.stage0_output.get("age_estimate_hours", 0)
        self.time_window = self._determine_time_window(age_hours)
        
        # 4. Execute the drift simulation (this is where OpenDrift would run)
        self._execute_backward_simulation()
        
        # 5. Update pipeline status
        self._update_status("done", "Stage 1 completed successfully")

    def _run_backward_simulation(self) -> None:
        """Execute the backward drift simulation with timeout handling."""
        import time
        import subprocess
        import shlex
        
        max_time = 60  # seconds
        start_time = time.time()
        
        # Simulate OpenDrift execution (in real implementation, this would call OpenDrift)
        while time.time() - start_time < max_time:
            # Simulate OpenDrift running
            time.sleep(0.1)
            # Check for timeout
            if time.time() - start_time > max_time:
                raise Stage1Error("Backward drift simulation exceeded time budget")
                
        # Simulate successful completion
        self.origin_region = self._calculate_origin_region()
        self.time_window = self._calculate_time_window()
        self.simulated = True

    def _calculate_origin_region(self) -> dict:
        """Calculate the origin region from the Stage 0 slick polygon."""
        # In real implementation: use OpenDrift to trace backward
        # For demo: use a simplified approach based on slick centroid
        centroid = self._calculate_centroid(self.stage0_output)
        return {
            "region": "estimated_origin",
            "coordinates": [centroid["lat"], centroid["lon"]],
            "confidence": "medium",
            "description": "Backward trace from slick centroid"
        }

    def _calculate_time_window(self) -> str:
        """Calculate time window based on Stage 0 age."""
        age_hours = self.stage0_output.get("age_estimate_hours", 0)
        if age_hours <= 24:
            return "within 24 hours"
        elif age_hours <= 72:
            return "within 72 hours"
        else:
            return "beyond 72 hours"

    def _calculate_origin_region(self) -> dict:
        """Calculate origin region from slick polygon."""
        # Extract centroid from slick polygon
        centroid = self._calculate_centroid(self.stage0_output)
        return {
            "region": "estimated_origin",
            "coordinates": [centroid["lat"], centroid["lon"]],
            "confidence": "medium",
            "description": "Backward trace from slick centroid"
        }

    def _calculate_centroid(self, slick_polygon: dict) -> dict:
        """Calculate centroid of the slick polygon."""
        polygon = slick_polygon["polygon"]
        if len(polygon) < 3:
            return {"lat": 0.0, "lon": 0.0}
            
        # Calculate centroid using centroid formula
        sum_lat = 0.0
        sum_lon = 0.0
        for lat, lon in polygon:
            sum_lat += lat
            sum_lon += lon
        centroid_lat = sum_lat / len(polygon)
        centroid_lon = sum_lon / len(polygon)
        
        return {"lat": centroid_lat, "lon": centroid_lon}