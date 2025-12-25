import os
import requests
import json
from pathlib import Path

# Config
IMAGE_DIR = "/home/currycreations/Desktop/New Folder/drive-download-20251225T035218Z-1-001"
API_URL = "http://localhost:8000/extract/invoice"

def test_bills():
    print(f"--- Processing Bills in {IMAGE_DIR} ---")
    files = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    results = []
    
    for filename in files:
        filepath = os.path.join(IMAGE_DIR, filename)
        print(f"Processing: {filename}...")
        
        try:
            with open(filepath, 'rb') as f:
                response = requests.post(API_URL, files={'file': f})
                
            if response.status_code == 200:
                data = response.json()
                extracted = data.get("extracted", {}).get("data", {})
                confidence = data.get("extracted", {}).get("confidence", 0)
                
                print(f"  > Success! Conf: {confidence}%")
                print(f"  > Data: {json.dumps(extracted, indent=2)}")
                results.append({
                    "file": filename,
                    "data": extracted,
                    "confidence": confidence
                })
            else:
                print(f"  > Failed: {response.text}")
                
        except Exception as e:
            print(f"  > Error: {e}")
            
    print("\n--- Summary ---")
    print(f"Processed {len(files)} files.")
    success_count = len([r for r in results if r["confidence"] > 0])
    print(f"Extracted Data from: {success_count}/{len(files)}")

if __name__ == "__main__":
    if not os.path.exists(IMAGE_DIR):
        print(f"Error: Directory not found: {IMAGE_DIR}")
    else:
        test_bills()
