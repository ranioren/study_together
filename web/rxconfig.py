import reflex as rx

config = rx.Config(
    app_name="course_search",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)