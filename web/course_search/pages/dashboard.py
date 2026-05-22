import reflex as rx
from course_search.components.dashboard_layout import dashboard_layout
from course_search.states.dashboard_state import DashboardState


def stat_card(item: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.match(
                    item["icon"],
                    ("users", rx.icon(tag="users", class_name="h-5 w-5 text-blue-600")),
                    ("book-open", rx.icon(tag="book-open", class_name="h-5 w-5 text-blue-600")),
                    ("check-circle", rx.icon(tag="check", class_name="h-5 w-5 text-blue-600")),
                    ("dollar-sign", rx.icon(tag="dollar-sign", class_name="h-5 w-5 text-blue-600")),
                    rx.icon(tag="circle", class_name="h-5 w-5 text-blue-600")
                ),
                class_name="p-2.5 bg-blue-50 rounded-xl",
            ),
            rx.el.div(
                rx.el.span(
                    item["change"],
                    class_name=rx.cond(
                        item["is_up"],
                        "text-xs font-bold text-green-600 bg-green-50 px-2 py-0.5 rounded-full",
                        "text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full",
                    ),
                ),
                class_name="flex items-center",
            ),
            class_name="flex items-center justify-between mb-4",
        ),
        rx.el.h4(item["value"], class_name="text-2xl font-black text-gray-900 mb-1"),
        rx.el.p(item["title"], class_name="text-sm font-medium text-gray-500"),
        class_name="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm",
    )


def dashboard_page() -> rx.Component:
    return dashboard_layout(
        rx.el.div(
            # Dummy Data Banner
            rx.el.div(
                rx.el.p("⚠️ Note: The statistics and activity shown here are currently dummy data for demonstration purposes.", 
                        class_name="text-amber-800 font-medium text-sm"),
                class_name="w-full bg-amber-50 border border-amber-100 p-3 rounded-xl mb-8 flex items-center justify-center"
            ),
            rx.el.div(
                rx.foreach(DashboardState.stats, stat_card),
                class_name="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.el.h3(
                            "Recent Activity",
                            class_name="text-lg font-bold text-gray-900",
                        ),
                        rx.el.button(
                            "View all",
                            class_name="text-sm font-semibold text-blue-600 hover:text-blue-700",
                        ),
                        class_name="flex items-center justify-between mb-6",
                    ),
                    rx.el.div(
                        rx.foreach(
                            DashboardState.activities,
                            lambda act: rx.el.div(
                                rx.el.div(
                                    class_name="size-2 bg-blue-500 rounded-full mt-1.5 shrink-0"
                                ),
                                rx.el.div(
                                    rx.el.p(
                                        act["description"],
                                        class_name="text-sm font-medium text-gray-800 mb-1",
                                    ),
                                    rx.el.p(
                                        act["time"], class_name="text-xs text-gray-400"
                                    ),
                                    class_name="flex-1",
                                ),
                                class_name="flex gap-4 pb-6 border-l-2 border-gray-50 ml-1 pl-4 relative last:pb-0",
                            ),
                        ),
                        class_name="relative",
                    ),
                    class_name="bg-white p-8 rounded-2xl border border-gray-100 shadow-sm lg:col-span-2",
                ),
                rx.el.div(
                    rx.el.h3(
                        "Quick Actions",
                        class_name="text-lg font-bold text-gray-900 mb-6",
                    ),
                    rx.el.div(
                        rx.el.button(
                            rx.icon("plus", class_name="h-4 w-4 mr-2"),
                            "Create New Course",
                            on_click=lambda: DashboardState.navigate_to("Course Builder"),
                            class_name="w-full flex items-center justify-center py-3 bg-blue-600 text-white rounded-xl font-bold hover:bg-blue-700 transition-all shadow-md hover:shadow-lg mb-3",
                        ),
                        rx.el.a(
                            rx.icon("message-square", class_name="h-4 w-4 mr-2"),
                            "Connect to Discord!",
                            href="https://discord.com/oauth2/authorize?client_id=1474401683210637423",
                            target="_blank",
                            class_name="w-full flex items-center justify-center py-3 bg-indigo-600 text-white rounded-xl font-bold hover:bg-indigo-700 transition-all shadow-md hover:shadow-lg mb-3",
                        ),
                        rx.el.button(
                            rx.icon("users", class_name="h-4 w-4 mr-2"),
                            "Manage Students",
                            class_name="w-full flex items-center justify-center py-3 bg-white border border-gray-200 text-gray-700 rounded-xl font-bold hover:bg-gray-50 transition-all mb-3",
                        ),
                        rx.el.button(
                            rx.icon("download", class_name="h-4 w-4 mr-2"),
                            "Export Reports",
                            class_name="w-full flex items-center justify-center py-3 bg-white border border-gray-200 text-gray-700 rounded-xl font-bold hover:bg-gray-50 transition-all",
                        ),
                        class_name="flex flex-col",
                    ),
                    class_name="bg-white p-8 rounded-2xl border border-gray-100 shadow-sm",
                ),
                class_name="grid grid-cols-1 lg:grid-cols-3 gap-8",
            ),
        )
    )