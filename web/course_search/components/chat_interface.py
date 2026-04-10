import reflex as rx
from course_search.states.chat_state import ChatState


def message_bubble(message: dict) -> rx.Component:
    is_user = message["role"] == "user"
    return rx.el.div(
        rx.el.div(
            rx.el.p(
                message["content"],
                class_name=rx.cond(
                    is_user,
                    "text-white text-sm font-medium",
                    "text-gray-800 text-sm font-medium",
                ),
            ),
            class_name=rx.cond(
                is_user,
                "bg-blue-600 rounded-2xl rounded-tr-none px-4 py-2 max-w-[80%] ml-auto",
                "bg-gray-100 rounded-2xl rounded-tl-none px-4 py-2 max-w-[80%] mr-auto",
            ),
        ),
        class_name="mb-4 w-full",
    )


def google_login_button() -> rx.Component:
    from course_search.states.dashboard_state import DashboardState

    from course_search.course_search import State
    return rx.el.button(
        rx.el.div(
            rx.el.div(
                rx.el.svg(
                    rx.el.path(
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z",
                        fill="#4285F4",
                    ),
                    rx.el.path(
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z",
                        fill="#34A853",
                    ),
                    rx.el.path(
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z",
                        fill="#FBBC05",
                    ),
                    rx.el.path(
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z",
                        fill="#EA4335",
                    ),
                    view_box="0 0 24 24",
                    class_name="size-5",
                ),
                class_name="bg-white p-2 rounded-lg mr-4 shadow-sm",
            ),
            rx.el.span(
                "Login with Google to start teaching!",
                class_name="text-white font-semibold text-sm mr-2",
            ),
            class_name="flex items-center",
        ),
        on_click=State.login_with_google,
        class_name="bg-blue-600 hover:bg-blue-700 transition-all duration-200 px-6 py-3 rounded-2xl flex items-center mx-auto mb-10 shadow-lg hover:shadow-xl hover:-translate-y-1 transform",
    )


def chat_interface() -> rx.Component:
    return rx.el.div(
        google_login_button(),
        rx.el.div(
            rx.el.div(
                rx.icon("settings", class_name="h-5 w-5 text-gray-400"),
                rx.el.h3(
                    "How can I help you today?",
                    class_name="text-lg font-semibold text-gray-800",
                ),
                class_name="flex items-center gap-2 mb-6 justify-center",
            ),
            rx.el.div(
                rx.foreach(ChatState.messages, message_bubble),
                class_name="overflow-y-auto max-h-[400px] pr-2 custom-scrollbar",
                id="chat-box",
            ),
            class_name="mb-6",
        ),
        rx.el.div(
            rx.el.form(
                rx.el.div(
                    rx.el.input(
                        placeholder="Ask me anything...",
                        name="input_text",
                        class_name="flex-1 bg-transparent border-none focus:ring-0 text-gray-700 font-medium px-4 py-3",
                        default_value=ChatState.input_text,
                    ),
                    rx.el.button(
                        rx.icon("arrow-up", class_name="h-5 w-5 text-white"),
                        type="submit",
                        class_name="bg-blue-600 hover:bg-blue-700 transition-colors rounded-full p-2 mr-2 flex items-center justify-center shadow-md",
                    ),
                    class_name="flex items-center border border-gray-200 rounded-2xl focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all bg-white shadow-sm",
                ),
                on_submit=ChatState.send_message,
                reset_on_submit=True,
            ),
            class_name="sticky bottom-0 bg-white pt-2",
        ),
        class_name="w-full mt-12 pt-12 border-t border-gray-100",
    )