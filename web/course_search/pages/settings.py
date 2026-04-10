import reflex as rx
from course_search.components.dashboard_layout import dashboard_layout
from course_search.states.dashboard_state import DashboardState


def settings_card(title: str, subtitle: str, content: rx.Component) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h3(title, class_name="text-lg font-bold text-gray-900"),
            rx.el.p(subtitle, class_name="text-sm font-medium text-gray-500"),
            class_name="mb-6",
        ),
        content,
        class_name="bg-white p-8 rounded-2xl border border-gray-100 shadow-sm mb-8",
    )


def settings_page() -> rx.Component:
    return dashboard_layout(
        rx.el.div(
            rx.el.h2("Settings", class_name="text-2xl font-black text-gray-900 mb-8"),
            settings_card(
                "Profile Settings",
                "Update your personal information and biography",
                rx.el.form(
                    rx.el.div(
                        rx.el.div(
                            rx.el.label(
                                "Full Name",
                                class_name="text-xs font-bold text-gray-400 mb-1.5 block",
                            ),
                            rx.el.input(
                                default_value=DashboardState.user_name,
                                class_name="w-full p-3 bg-gray-50 border border-gray-100 rounded-xl text-sm font-medium",
                            ),
                            class_name="mb-4",
                        ),
                        rx.el.div(
                            rx.el.label(
                                "Email Address",
                                class_name="text-xs font-bold text-gray-400 mb-1.5 block",
                            ),
                            rx.el.input(
                                default_value=DashboardState.user_email,
                                class_name="w-full p-3 bg-gray-50 border border-gray-100 rounded-xl text-sm font-medium",
                            ),
                            class_name="mb-4",
                        ),
                        rx.el.div(
                            rx.el.label(
                                "Biography",
                                class_name="text-xs font-bold text-gray-400 mb-1.5 block",
                            ),
                            rx.el.textarea(
                                default_value=DashboardState.user_bio,
                                class_name="w-full p-3 bg-gray-50 border border-gray-100 rounded-xl text-sm font-medium h-32",
                            ),
                            class_name="mb-6",
                        ),
                        rx.el.button(
                            "Save Changes",
                            class_name="px-6 py-3 bg-blue-600 text-white font-bold rounded-xl shadow-md hover:bg-blue-700 transition-all",
                        ),
                    ),
                    reset_on_submit=True,
                ),
            ),
            settings_card(
                "Notifications",
                "Control when and how you receive updates",
                rx.el.div(
                    rx.el.div(
                        rx.el.div(
                            rx.el.p(
                                "Email Notifications",
                                class_name="text-sm font-bold text-gray-800",
                            ),
                            rx.el.p(
                                "Receive weekly summaries and important alerts",
                                class_name="text-xs text-gray-400",
                            ),
                            class_name="flex flex-col",
                        ),
                        rx.el.input(
                            type="checkbox",
                            default_checked=DashboardState.email_notifications,
                            class_name="size-5 text-blue-600 border-gray-200 rounded",
                        ),
                        class_name="flex items-center justify-between py-4 border-b border-gray-50",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.el.p(
                                "Student Messages",
                                class_name="text-sm font-bold text-gray-800",
                            ),
                            rx.el.p(
                                "Get notified when students send direct inquiries",
                                class_name="text-xs text-gray-400",
                            ),
                            class_name="flex flex-col",
                        ),
                        rx.el.input(
                            type="checkbox",
                            default_checked=DashboardState.student_messages,
                            class_name="size-5 text-blue-600 border-gray-200 rounded",
                        ),
                        class_name="flex items-center justify-between py-4 border-b border-gray-50",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.el.p(
                                "Course Analytics",
                                class_name="text-sm font-bold text-gray-800",
                            ),
                            rx.el.p(
                                "Monthly performance reports for your courses",
                                class_name="text-xs text-gray-400",
                            ),
                            class_name="flex flex-col",
                        ),
                        rx.el.input(
                            type="checkbox",
                            default_checked=DashboardState.course_updates,
                            class_name="size-5 text-blue-600 border-gray-200 rounded",
                        ),
                        class_name="flex items-center justify-between py-4",
                    ),
                ),
            ),
            settings_card(
                "Account Management",
                "Security and connected integrations",
                rx.el.div(
                    rx.el.div(
                        rx.el.p(
                            "Connected Accounts",
                            class_name="text-sm font-bold text-gray-800 mb-4",
                        ),
                        rx.el.div(
                            rx.el.div(
                                rx.el.div(
                                    class_name="size-8 bg-blue-100 rounded-lg flex items-center justify-center"
                                ),
                                rx.el.p(
                                    "Google Workspace",
                                    class_name="text-sm font-medium text-gray-700",
                                ),
                                class_name="flex items-center gap-3",
                            ),
                            rx.el.button(
                                "Disconnect",
                                class_name="text-xs font-bold text-red-500 hover:text-red-600",
                            ),
                            class_name="flex items-center justify-between p-4 bg-gray-50 rounded-xl mb-3",
                        ),
                        rx.el.div(
                            rx.el.div(
                                rx.el.div(
                                    class_name="size-8 bg-indigo-100 rounded-lg flex items-center justify-center"
                                ),
                                rx.el.p(
                                    "Discord Community",
                                    class_name="text-sm font-medium text-gray-700",
                                ),
                                class_name="flex items-center gap-3",
                            ),
                            rx.el.button(
                                "Connect",
                                class_name="text-xs font-bold text-blue-600 hover:text-blue-700",
                            ),
                            class_name="flex items-center justify-between p-4 bg-gray-50 rounded-xl mb-8",
                        ),
                    ),
                    rx.el.div(
                        rx.el.p(
                            "Danger Zone",
                            class_name="text-sm font-bold text-red-500 mb-4",
                        ),
                        rx.el.button(
                            "Delete Account",
                            class_name="px-6 py-3 bg-red-50 text-red-600 border border-red-100 font-bold rounded-xl hover:bg-red-100 transition-all",
                        ),
                    ),
                ),
            ),
        )
    )