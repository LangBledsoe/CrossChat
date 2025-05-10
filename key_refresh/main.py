import requests
from google.cloud import secretmanager
import json
import os
from flask import Request


def refresh_instagram_token(request: Request):
    """Refreshes the Instagram access token stored in Secret Manager.
    Args:
        request (flask.Request): The Flask request object.
                                 Although we don't directly use it,
                                 HTTP-triggered Cloud Functions receive this.
    """
    project_id = os.environ.get("GCP_PROJECT")
    secret_name = "mysecrets-json"

    if not project_id:
        print("Error: GCP_PROJECT environment variable not set.")
        return

    # Initialize Secret Manager client
    client = secretmanager.SecretManagerServiceClient()
    secret_version_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

    try:
        # Get the current secret data from Secret Manager
        response = client.access_secret_version(name=secret_version_name)
        current_secret_json = response.payload.data.decode("utf-8")
        current_secrets = json.loads(current_secret_json)

        # Get the current access token
        current_access_token = current_secrets.get("INSTAGRAM_ACCESS_TOKEN")
        if not current_access_token:
            print("Error: 'INSTAGRAM_ACCESS_TOKEN' not found in the secret.")
            return

        # Instagram API endpoint for refreshing the token
        refresh_url = "https://graph.instagram.com/refresh_access_token"
        params = {
            "grant_type": "ig_refresh_token",
            "access_token": current_access_token
        }

        # Make the refresh request
        refresh_response = requests.get(refresh_url, params=params)
        refresh_response.raise_for_status()  # Raise an exception for bad status codes
        new_token_data = refresh_response.json()
        new_access_token = new_token_data.get("access_token")

        if new_access_token:
            # Update the access token in the dictionary
            current_secrets["INSTAGRAM_ACCESS_TOKEN"] = new_access_token

            # Convert the updated dictionary back to JSON
            updated_secret_json = json.dumps(current_secrets)
            payload = updated_secret_json.encode("utf-8")

            # Add a new version of the secret in Secret Manager
            update_response = client.add_secret_version(
                parent=f"projects/{project_id}/secrets/{secret_name}",
                payload={"data": payload}
            )
            print(f"Successfully refreshed Instagram access token. New version: {update_response.name}")
        else:
            print(f"Error: Could not retrieve new access token from Instagram API response: {refresh_response.json()}")

    except Exception as e:
        print(f"An error occurred: {e}")

    return "OK"
