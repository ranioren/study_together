import reflex as rx

import os

app_url = os.getenv("APP_URL", "http://localhost:3000")
api_url = os.getenv("API_URL", "http://127.0.0.1:8000")

config = rx.Config(
    app_name="course_search",
    api_url=api_url,
    backend_port=8000,
    frontend_port=3000,
    backend_host="0.0.0.0",
    cors_allowed_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        app_url,
        api_url,
    ] + (["*"] if os.getenv("CORS_ALLOW_ALL") == "true" else []),
)