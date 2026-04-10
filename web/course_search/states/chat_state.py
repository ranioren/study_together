import reflex as rx
from typing import TypedDict
import asyncio


class Message(TypedDict):
    role: str
    content: str


class ChatState(rx.State):
    messages: list[Message] = [
        {
            "role": "bot",
            "content": "Hello! Welcome to the Learning Community. How can I help you explore our features today?",
        }
    ]
    input_text: str = ""
    is_processing: bool = False

    @rx.event
    async def send_message(self, form_data: dict[str, str]):
        user_msg = form_data.get("input_text", "").strip()
        if not user_msg:
            return
        self.messages.append({"role": "user", "content": user_msg})
        self.input_text = ""
        self.is_processing = True
        yield
        await asyncio.sleep(1)
        bot_response = self._get_bot_response(user_msg)
        self.messages.append({"role": "bot", "content": bot_response})
        self.is_processing = False

    @rx.event
    def select_feature(self, feature_name: str):
        prompt = f"Tell me more about {feature_name}"
        return ChatState.send_message({"input_text": prompt})

    def _get_bot_response(self, user_msg: str) -> str:
        msg = user_msg.lower()
        if "self paced" in msg:
            return "Our Self Paced Learning module offers thousands of curated courses from top universities. You can start anytime and learn at your own speed!"
        elif "discord" in msg:
            return "Our Discord community is where the magic happens! You'll get access to study groups, live Q&A sessions, and peer mentorship."
        elif "course builder" in msg:
            return "The Course Builder is a powerful tool for educators. You can drag and drop videos, quizzes, and assignments to create a unique learning path."
        elif "google classroom" in msg:
            return "We offer seamless integration with Google Classroom. Sync your rosters and assignments automatically with just a few clicks."
        else:
            return "Thanks for reaching out! I can help you with learning resources, Discord setup, course building, or Google Classroom integration. Which one interests you?"