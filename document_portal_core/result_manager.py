"""
Result Manager Module.
Logs extraction results, performance metrics, and usage costs to a structured directory.
"""
import os
import json
import time
from datetime import datetime
from pathlib import Path

class ResultManager:
    def __init__(self, base_dir: str = "results"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def log_result(self, model_name: str, filename: str, data: dict, duration_seconds: float, confidence: float):
        """
        Saves the result to results/{model_name}/{timestamp}_{filename}.json
        """
        # Create model directory
        model_dir = self.base_dir / model_name
        model_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = Path(filename).stem
        output_file = model_dir / f"{timestamp}_{safe_filename}.json"
        
        record = {
            "metadata": {
                "filename": filename,
                "timestamp": datetime.now().isoformat(),
                "model": model_name,
                "duration_seconds": round(duration_seconds, 4),
                "confidence_score": confidence
            },
            "extraction": data
        }
        
        try:
            with open(output_file, 'w') as f:
                json.dump(record, f, indent=2)
        except Exception as e:
            print(f"Failed to log result: {e}")

RESULT_MANAGER = ResultManager()
