import reflex as rx

config = rx.Config(
    app_name="course_search",
    api_url="http://127.0.0.1:8000",
    backend_port=8000,
    frontend_port=3000,
    backend_host="0.0.0.0",
    cors_allowed_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)