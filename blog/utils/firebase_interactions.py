import firebase_admin
from firebase_admin import credentials, storage
import os
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# cred_path = Path(__file__).parent / "file-transfer-app-74625-firebase-adminsdk-4vum9-d106be7043.json"
# _credentials = os.getenv("GOOGLE_CREDENTIALS_JSON")
import os
import firebase_admin
from firebase_admin import credentials

# Path to the secret file (uploaded via Render's "Secret Files")
cred_path = "/etc/secrets/file-transfer-app-74625-firebase-adminsdk-4vum9-d106be7043.json"

# Initialize Firebase Admin SDK only once
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET")
    })

bucket = storage.bucket()

# Upload file to Firebase Storage
async def upload_file_to_storage(user_id, file_name, file_bytes, content_type):
    try:
        blob = bucket.blob(f'plant_disease_detection/{user_id}/{file_name}')
        blob.upload_from_string(file_bytes, content_type=content_type)  # <-- Use upload_from_string
        blob.make_public()
        return blob.public_url
    except Exception as e:
        print(f"❌ Upload failed: {str(e)}")
        raise

# Delete file from Firebase Storage
async def delete_file_from_storage(user_id, file_name):
    try:
        blob = bucket.blob(f'plant_disease_detection/{user_id}/{file_name}')  # <-- corrected your path
        if blob.exists():
            blob.delete()
    except Exception as e:
        print(f"❌ Delete failed: {str(e)}")
        raise
