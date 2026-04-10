import reflex as rx
from course_search.states.chat_state import ChatState


def feature_card(
    title: str,
    subtitle: str,
    icon_name: str | None,
    dot_color: str,
    image_src: str | None = None,
) -> rx.Component:
    return rx.el.button(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    class_name=f"size-2 rounded-full {dot_color} absolute -top-1 -right-1"
                ),
                rx.cond(
                    image_src,
                    rx.image(src=image_src, class_name="size-8 object-contain"),
                    rx.icon(
                        icon_name if icon_name else "circle-help",
                        class_name="h-6 w-6 text-gray-600",
                    ),
                ),
                class_name="relative p-2 bg-gray-50 rounded-lg shrink-0 flex items-center justify-center size-10",
            ),
            rx.el.div(
                rx.el.p(title, class_name="text-sm font-bold text-gray-900 text-left"),
                rx.el.p(
                    subtitle, class_name="text-xs text-gray-500 text-left line-clamp-1"
                ),
                class_name="flex flex-col gap-0.5 overflow-hidden",
            ),
            class_name="flex items-center gap-4 p-4",
        ),
        on_click=lambda: ChatState.select_feature(title),
        class_name="w-full bg-white border border-gray-100 rounded-2xl shadow-sm hover:shadow-md hover:border-blue-200 hover:-translate-y-0.5 transition-all duration-200",
    )


def feature_grid() -> rx.Component:
    return rx.el.div(
        feature_card(
            "Self Paced Learning",
            "Learn at your own pace with curated courses",
            "graduation-cap",
            "bg-green-500",
        ),
        feature_card(
            "Add to Discord Server",
            "Start educating your community & Monetize your knowledge",
            None,
            "bg-orange-500",
            image_src="/discord-black-icon-1.png",
        ),
        feature_card(
            "Course Builder",
            "Create and share your own courses",
            "wrench",
            "bg-blue-500",
        ),
        feature_card(
            "Google Classroom Integration",
            "You build your courses, we handle the rest",
            None,
            "bg-red-500",
            image_src="/google-classroom_bw.jpg",
        ),
        class_name="grid grid-cols-1 md:grid-cols-2 gap-4 w-full",
    )