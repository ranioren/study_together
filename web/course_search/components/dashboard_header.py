import reflex as rx
from course_search.states.dashboard_state import DashboardState


def dashboard_header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.icon(
                    "search",
                    class_name="h-4 w-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2",
                ),
                rx.el.input(
                    placeholder="Global search...",
                    class_name="pl-10 pr-4 py-2 bg-gray-50 border-none rounded-xl focus:ring-2 focus:ring-blue-100 w-64 text-sm font-medium text-gray-600",
                ),
                class_name="relative",
            ),
            rx.el.div(
                rx.el.button(
                    rx.icon("bell", class_name="h-5 w-5 text-gray-500"),
                    class_name="p-2 rounded-xl hover:bg-gray-100 transition-colors relative",
                ),
                rx.el.div(
                    rx.el.div(
                        rx.el.p(
                            DashboardState.user_name,
                            class_name="text-sm font-bold text-gray-900",
                        ),
                        rx.el.p(
                            "Teacher", class_name="text-xs text-gray-500 text-right"
                        ),
                        class_name="hidden md:flex flex-col",
                    ),
                    rx.image(
                        src=f"https://api.dicebear.com/9.x/notionists/svg?seed={DashboardState.user_name}",
                        class_name="size-8 rounded-full bg-gray-50",
                    ),
                    class_name="flex items-center gap-3 pl-4 border-l border-gray-100",
                ),
                class_name="flex items-center gap-4",
            ),
            class_name="flex items-center justify-between w-full h-16 px-8",
        ),
        class_name="sticky top-0 bg-white/80 backdrop-blur-md border-b border-gray-100 z-10",
    )