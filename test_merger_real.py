
import requests
import os
import json

API_URL = "http://localhost:8000/extract/invoice"
IMG_DIR = "/home/currycreations/Desktop/New Folder/drive-download-20251225T035218Z-1-001"

# PepsiCo Split Invoice (Page 1 & 2)
# Identified by user: E3E271D3... & D73CB49D...
file1 = "E3E271D3-F374-4981-8DEE-390210976C9E.JPG"
file2 = "D73CB49D-509F-4F01-8DE2-7127319EB828.JPG"

files_payload = [
    ('files', (file1, open(os.path.join(IMG_DIR, file1), 'rb'), 'image/jpeg')),
    ('files', (file2, open(os.path.join(IMG_DIR, file2), 'rb'), 'image/jpeg'))
]

print(f"Sending Batch: {file1} + {file2}")

try:
    resp = requests.post(API_URL, files=files_payload)
    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2))
        
        # Verify Merge
        if data['merged_count'] == 1 and data['batch_count'] == 2:
            print("SUCCESS: 2 Pages merged into 1 Invoice!")
            
            # Check Line Items
            merged = data['results'][0]
            items = merged['extracted']['data'].get('line_items', [])
            print(f"Extracted Line Items: {len(items)}")
            if len(items) > 5: 
                print("Line Item extraction looks rich/correct.")
        else:
            print("FAILURE: Pages did not merge.")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")
except Exception as e:
    print(f"Exception: {e}")
