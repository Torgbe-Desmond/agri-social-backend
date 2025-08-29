import tensorflow as tf
import numpy as np
from fastapi import UploadFile
from PIL import Image
import io
import base64
import httpx
import os
import random
import string
import requests
import mimetypes
from urllib.parse import urlparse

import torch
from torchvision import transforms
import torch.nn as nn
import torch.nn.functional as F

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from aiosmtplib import send
from email.message import EmailMessage
load_dotenv()



class TomatoDiseaseCNN(nn.Module):
    def __init__(self, num_classes=9):
        super(TomatoDiseaseCNN, self).__init__()

        self.conv_layers = nn.Sequential(
            # Block 1: 3 -> 32
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 2: 32 -> 64
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 3: 64 -> 128
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 4: 128 -> 256
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 5: 256 -> 512
            nn.Conv2d(256, 512, kernel_size=3, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, kernel_size=3, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2)
        )

        self.dense_layers = nn.Sequential(
            nn.Linear(512 * 8 * 8, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(512, num_classes)
        )

    def forward(self, x):
        x = self.conv_layers(x)
        x = x.view(x.size(0), -1)
        x = self.dense_layers(x)
        return x


async def _predict_image_class(file_bytes: bytes, model: torch.nn.Module):
    try:
        # Load image from bytes
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")

        # Preprocessing (must match your training preprocessing)
        preprocess = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])
        ])

        input_tensor = preprocess(image).unsqueeze(0)

        # Ensure model is in evaluation mode
        model.eval()

        with torch.no_grad():
            outputs = model(input_tensor)
            probabilities = torch.softmax(outputs, dim=1)
            confidence, result_index = torch.max(probabilities, dim=1)
            print("result_index inside utils",result_index)

        return result_index.item(), confidence.item()

    except Exception as e:
        print(f"Prediction error: {e}")
        raise


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

async def predict_image_class(file_bytes:bytes , model: tf.keras.Model):
    try:
        image = Image.open(io.BytesIO(file_bytes)).resize((256, 256))
        input_arr = tf.keras.preprocessing.image.img_to_array(image)
        input_arr = np.expand_dims(input_arr, axis=0)
        prediction = model.predict(input_arr)
        confidence = float(np.max(prediction))  
        result_index = np.argmax(prediction)
        return result_index, confidence
    except Exception as e:
        print(f"Prediction error: {e}")
        raise


async def convert_file_to_base64(file: UploadFile):
    file_bytes = await file.read()
    base64_encoded = base64.b64encode(file_bytes).decode('utf-8')
    return base64_encoded


async def convert_file_url_to_base64(file_url: str):
    async with httpx.AsyncClient() as client:
        headers = {
            "Api-Key": os.getenv("PLANT_ID_API_KEY"),
            "Content-Type": "application/json"
        }
        response = await client.get(file_url, headers=headers)
        if response.status_code == 200:
            encoded_base64 = base64.b64encode(response.content).decode('utf-8')
            return encoded_base64
        else:
            raise Exception(f"Failed to download. Status code: {response.status_code}")


def generate_random_string(length=12):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))


def download_and_process_file(url: str):
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        raise Exception("Failed to download file.")
    file_bytes = response.content
    return file_bytes



async def send_email_to_recipient(verification_data):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # points to blog/
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("password_verification.html")
    
    html_content = template.render(username=verification_data.get("username"), verification_link=verification_data.get("verification_link"))
    
    message = EmailMessage()
    message["From"] = os.getenv("GMAIL_USER")
    message["To"] = verification_data.get("to")
    message["Subject"] = verification_data.get("subject")
    message.set_content(html_content, subtype="html")

    await send(
        message,
        hostname="smtp.gmail.com",
        port=587,
        start_tls=True,
        username=os.getenv("GMAIL_USER"),
        password=os.getenv("GMAIL_PASS"),
    )
