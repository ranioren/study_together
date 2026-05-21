import os
import json
from google_auth_oauthlib.flow import Flow

def get_google_flow(creds_path, scopes, redirect_uri):
    """
    Constructs a Google OAuth Flow.
    If GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are in the environment,
    it uses them (Production mode).
    Otherwise, it falls back to reading the local secrets file (Dev mode).
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip().strip('\'"')
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip().strip('\'"')
    
    if client_id and client_secret:
        client_config = {
            "web": {
                "client_id": client_id,
                "project_id": os.getenv("GOOGLE_PROJECT_ID", "study-together"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": client_secret,
                "redirect_uris": [redirect_uri]
            }
        }
        return Flow.from_client_config(client_config, scopes=scopes, redirect_uri=redirect_uri)
    else:
        if not os.path.exists(creds_path):
            raise FileNotFoundError(f"OAuth credentials not found. Ensure '{creds_path}' exists or environment variables are set.")
        return Flow.from_client_secrets_file(creds_path, scopes=scopes, redirect_uri=redirect_uri)
