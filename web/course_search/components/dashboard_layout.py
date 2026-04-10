import reflex as rx
from course_search.components.sidebar import sidebar
from course_search.components.dashboard_header import dashboard_header


def dashboard_layout(content: rx.Component) -> rx.Component:
    return rx.el.div(
        sidebar(),
        rx.el.main(
            dashboard_header(),
            rx.el.div(content, class_name="p-8 max-w-7xl mx-auto"),
            class_name="flex-1 ml-64 min-h-screen bg-gray-50/50",
        ),
        class_name="flex min-h-screen w-full font-['Inter']",
    )