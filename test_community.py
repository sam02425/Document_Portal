
import requests
import os
import json

API_URL = "http://localhost:8001/extract/invoice"
IMG_DIR = "/home/currycreations/Desktop/New Folder/drive-download-20251225T035218Z-1-001"
FILE = "AE04739B-4F62-4218-B881-136822A7861A.JPG"

print(f"Testing {FILE}...")
files = [('files', (FILE, open(os.path.join(IMG_DIR, FILE), 'rb'), 'image/jpeg'))]

try:
    resp = requests.post(API_URL, files=files)
    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2))
        res = data['results'][0]['extracted']['data']
        print(f"Doc Type: {res.get('doc_type')}")
        print(f"Vendor: {res.get('vendor', {}).get('name')}")
        print(f"Total: {res.get('financials', {}).get('total_amount')}")
    else:
        print(f"Error: {resp.status_code}")
except Exception as e:
    print(e)
