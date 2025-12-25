
import requests
import os
import json

API_URL = "http://localhost:8001/extract/invoice"
IMG_DIR = "/home/currycreations/Desktop/New Folder/drive-download-20251225T035218Z-1-001"

# 4 Pages of Night Audit
audit_files = [
    "71FC1CD9-417F-41E8-B132-4C88FEA3414D.JPG",
    "C8617D64-50EE-415B-9BF6-40B392F8C30E.JPG",
    "8A18F0A0-A428-4EF2-A14D-ABFE4EA05E90.JPG",
    "C60280D0-425C-4FFB-A8B2-3823A811E81E.JPG"
]

files_payload = []
for f in audit_files:
    files_payload.append(('files', (f, open(os.path.join(IMG_DIR, f), 'rb'), 'image/jpeg')))

print(f"Sending Batch: 4 Night Audit Pages")

try:
    resp = requests.post(API_URL, files=files_payload)
    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2))
        
        if data['merged_count'] == 1:
            print("SUCCESS: 4 Pages merged into 1 Report!")
            merged = data['results'][0]
            print(f"Doc Type: {merged['extracted']['data'].get('doc_type')}")
        else:
            print(f"FAILURE: Merged Count is {data['merged_count']}")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")
except Exception as e:
    print(f"Exception: {e}")
