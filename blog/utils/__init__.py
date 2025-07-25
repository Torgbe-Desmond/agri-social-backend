# import tensorflow as tf
# import numpy as np
from fastapi import UploadFile
# from PIL import Image
import io
import base64
import httpx
import os    
import random
import string
import requests
import mimetypes
from urllib.parse import urlparse

def get_connection_string(auth_type, server_name=None, database_name=None, username=None, password=None, driver="ODBC Driver 17 for SQL Server"):
    """
    Returns a formatted connection string based on the authentication type.

    :param auth_type: 'local', 'password', or 'supabase'
    :param server_name: Server name or host (not needed for supabase if included in the URL)
    :param database_name: Database name
    :param username: For 'password' and 'supabase'
    :param password: For 'password' and 'supabase'
    :param driver: ODBC Driver (for SQL Server only)
    :return: SQLAlchemy connection string
    """
    
    if auth_type == 'local':
        return f"mssql+aioodbc://{server_name}/{database_name}?driver={driver.replace(' ', '+')}&trusted_connection=yes"

    elif auth_type == 'password' and username and password:
        return f"mssql+pyodbc://{username}:{password}@{server_name}/{database_name}?driver={driver.replace(' ', '+')}"

    elif auth_type == 'supabase':
        return f"postgresql://postgres.qolhywmalugdwssrxyrl:@#$%1234@#$%____@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"

    else:
        raise ValueError("Invalid connection parameters.")
    
    

# @#$%1234@#$%____

# async def predict_image_class(file_bytes:bytes , model: tf.keras.Model):
    try:
      
        # Load image from bytes and resize it
        image = Image.open(io.BytesIO(file_bytes)).resize((256, 256))

        # Convert image to array and prepare input
        input_arr = tf.keras.preprocessing.image.img_to_array(image)
        input_arr = np.expand_dims(input_arr, axis=0)

        # Make prediction
        prediction = model.predict(input_arr)
        
        # Confidence of the predicted class
        confidence = float(np.max(prediction))  

        result_index = np.argmax(prediction)

        return result_index, confidence

    except Exception as e:
        print(f"Prediction error: {e}")
        raise
    
    

# async def convert_file_to_base64(file: UploadFile):
#     file_bytes = await file.read()
#     base64_encoded = base64.b64encode(file_bytes).decode('utf-8')
#     return base64_encoded

async def convert_file_url_to_base64(file_url:str):
    async with httpx.AsyncClient() as client:
           headers = {
            "Api-Key": os.getenv("PLANT_ID_API_KEY"),
            "Content-Type": "application/json"
           }
           response = await client.get(file_url, headers=headers)  
           if response.status_code == 200:
               # Encode binary content to base64
               encoded_base64 = base64.b64encode(response.content).decode('utf-8')
               return encoded_base64
           else:
               raise Exception(f"Failed to download. Status code: {response.status_code}")
           
           
def generate_random_string(length=12):
    characters = string.ascii_letters + string.digits  # a-zA-Z0-9
    return ''.join(random.choices(characters, k=length))



# def download_and_process_file(url: str):
#     # Download file
#     response = requests.get(url, stream=True)
#     if response.status_code != 200:
#         raise Exception("Failed to download file.")

#     # Get the file bytes
#     file_bytes = response.content

#     return file_bytes
    