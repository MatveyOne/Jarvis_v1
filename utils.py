import json
import os
import time
from datetime import datetime

import requests


def create_new_token():
    """Создание нового токена"""
    metadata_url = "http://ваш ip/computeMetadata/v1/instance/service-accounts/default/token"
    headers = {"Metadata-Flavor": "Google"}

    token_dir = os.path.dirname(TOKEN_PATH)
    if not os.path.exists(token_dir):
        os.makedirs(token_dir)

    try:
        response = requests.get(metadata_url, headers=headers)
        if response.status_code == 200:
            token_data = response.json()
            # Добавляем время истечения токена к текущему времени
            token_data['expires_at'] = time.time() + token_data['expires_in']
            with open(TOKEN_PATH, "w") as token_file:
                json.dump(token_data, token_file)
            logging.info("TOKEN CREATED")
        else:
            logging.error(f"Failed to retrieve token. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while retrieving token: {e}")


def get_creds() -> (str, str):
    """Получение токена и folder_id из yandex cloud command line interface"""
    try:
        with open(TOKEN_PATH, 'r') as f:
            d = json.load(f)
            expiration = datetime.strptime(d["expires_at"][:26], "%Y-%m-%dT%H:%M:%S.%f")

        if expiration < datetime.now():
            logging.info("TOKEN EXPIRED")
            create_new_token()
    except:
        create_new_token()

    with open(TOKEN_PATH, 'r') as f:
        d = json.load(f)
        token = d["access_token"]

    with open(FOLDER_ID_PATH, 'r') as f:
        folder_id = f.read().strip()

    return token, folder_id