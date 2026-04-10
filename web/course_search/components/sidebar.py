import reflex as rx
from course_search.states.dashboard_state import DashboardState


def nav_item(label: str, icon: str) -> rx.Component:
    is_active = DashboardState.active_section == label
    return rx.el.button(
        rx.icon(
            icon,
            class_name=rx.cond(
                is_active, "h-5 w-5 mr-3 text-white", "h-5 w-5 mr-3 text-gray-500"
            ),
        ),
        rx.el.span(
            label,
            class_name=rx.cond(
                is_active, "font-semibold text-white", "font-medium text-gray-600"
            ),
        ),
        on_click=lambda: DashboardState.navigate_to(label),
        class_name=rx.cond(
            is_active,
            "flex items-center w-full p-3 rounded-xl bg-blue-600 shadow-sm transition-all mb-2",
            "flex items-center w-full p-3 rounded-xl hover:bg-gray-100 transition-all mb-2",
        ),
    )


def sidebar() -> rx.Component:
    return rx.el.aside(
        rx.el.div(
            rx.el.div(
                rx.el.div(class_name="size-8 bg-orange-500 rounded-lg mr-3 shrink-0"),
                rx.el.div(
                    rx.el.span(
                        "#LearningCommunity",
                        class_name="text-lg font-black text-gray-900 tracking-tight",
                    ),
                    rx.el.span(
                        "v2.0-stable",
                        class_name="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full ml-2",
                    ),
                    class_name="flex items-center",
                ),
                class_name="flex items-center px-4 py-8",
            ),
            rx.el.nav(
                nav_item("Dashboard", "layout-dashboard"),
                nav_item("Your Courses", "book-open"),
                nav_item("Settings", "settings"),
                class_name="px-4 flex-1",
            ),
            rx.el.div(
                rx.el.button(
                    rx.el.div(
                        rx.image(
                            src=f"https://api.dicebear.com/9.x/notionists/svg?seed={DashboardState.user_name}",
                            class_name="size-10 rounded-full bg-gray-100",
                        ),
                        rx.el.div(
                            rx.el.p(
                                DashboardState.user_name,
                                class_name="text-sm font-bold text-gray-900",
                            ),
                            rx.el.p("Teacher", class_name="text-xs text-gray-500"),
                            class_name="flex flex-col items-start",
                        ),
                        class_name="flex items-center gap-3",
                    ),
                    on_click=lambda: DashboardState.navigate_to("Settings"),
                    class_name="w-full p-4 hover:bg-gray-50 transition-colors border-t border-gray-100",
                ),
                rx.el.button(
                    rx.icon("log-out", class_name="h-4 w-4 mr-2"),
                    "Logout",
                    on_click=lambda: DashboardState.navigate_to("Logout"),
                    class_name="w-full p-4 flex items-center justify-center text-xs font-bold text-red-500 hover:bg-red-50 transition-colors",
                ),
                class_name="mt-auto",
            ),
            class_name="flex flex-col h-full",
        ),
        class_name="fixed left-0 top-0 bottom-0 w-64 bg-white border-r border-gray-100 z-10",
    )