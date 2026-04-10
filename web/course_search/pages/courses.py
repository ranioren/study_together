import reflex as rx
from course_search.components.dashboard_layout import dashboard_layout
from course_search.states.dashboard_state import DashboardState


def course_card(course: dict) -> rx.Component:
    status_style = rx.match(
        course["status"],
        ("Active", "text-green-600 bg-green-100"),
        ("Draft", "text-orange-600 bg-orange-100"),
        ("Archived", "text-gray-600 bg-gray-100"),
        "text-gray-600 bg-gray-100",
    )
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    course["status"],
                    class_name=f"text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full {status_style}",
                ),
                rx.el.button(
                    rx.icon("gallery_vertical", class_name="h-4 w-4 text-gray-400"),
                    class_name="p-1 hover:bg-gray-50 rounded-lg",
                ),
                class_name="flex items-center justify-between mb-4",
            ),
            rx.el.h4(
                course["title"], class_name="text-lg font-bold text-gray-900 mb-2"
            ),
            rx.el.p(
                course["description"],
                class_name="text-sm text-gray-500 mb-6 line-clamp-2 min-h-[40px]",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.p(
                        "Avg. Progress", class_name="text-xs font-bold text-gray-400"
                    ),
                    rx.el.p(
                        f"{course['progress']}%",
                        class_name="text-xs font-bold text-blue-600",
                    ),
                    class_name="flex justify-between mb-1.5",
                ),
                rx.el.div(
                    rx.el.div(
                        class_name="h-1.5 bg-blue-600 rounded-full",
                        style={"width": f"{course['progress']}%"},
                    ),
                    class_name="w-full h-1.5 bg-gray-100 rounded-full",
                ),
                class_name="mb-6",
            ),
            rx.el.div(
                rx.el.div(
                    rx.icon("users", class_name="h-4 w-4 text-gray-400 mr-1"),
                    rx.el.span(
                        f"{course['students']} students",
                        class_name="text-xs font-bold text-gray-500",
                    ),
                    class_name="flex items-center",
                ),
                rx.el.span(
                    f"Updated {course['last_updated']}",
                    class_name="text-[10px] font-bold text-gray-400",
                ),
                class_name="flex items-center justify-between pt-4 border-t border-gray-50",
            ),
        ),
        class_name="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all",
    )


def courses_page() -> rx.Component:
    return dashboard_layout(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.h2(
                        "Your Courses (", DashboardState.courses.length(), ")",
                        class_name="text-2xl font-black text-gray-900 mb-1",
                    ),
                    rx.el.p(
                        "Manage and monitor your educational content",
                        class_name="text-sm font-medium text-gray-500",
                    ),
                    class_name="flex flex-col",
                ),
                rx.el.button(
                    rx.icon("plus", class_name="h-5 w-5 mr-2"),
                    "New Course",
                    on_click=lambda: DashboardState.navigate_to("Course Builder"),
                    class_name="px-6 py-3 bg-green-600 hover:bg-green-700 text-white font-bold rounded-xl shadow-md flex items-center transition-all",
                ),
                class_name="flex items-center justify-between mb-10",
            ),
            rx.el.div(
                rx.el.div(
                    rx.icon(
                        "search",
                        class_name="h-4 w-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2",
                    ),
                    rx.el.input(
                        placeholder="Filter courses...",
                        class_name="pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl w-full max-w-sm text-sm",
                    ),
                    class_name="relative",
                ),
                rx.el.div(
                    rx.el.button(
                        rx.icon("sliders_horizontal", class_name="h-4 w-4 mr-2"),
                        "Filters",
                        class_name="px-4 py-2 bg-white border border-gray-200 rounded-xl text-sm font-bold text-gray-600 flex items-center",
                    ),
                    class_name="flex items-center gap-3",
                ),
                class_name="flex items-center justify-between mb-8",
            ),
            rx.el.div(
                rx.foreach(DashboardState.courses, course_card),
                class_name="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6",
            ),
        )
    )