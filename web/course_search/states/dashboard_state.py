import reflex as rx
from typing import TypedDict, Literal
from faker import Faker

fake = Faker()


class StatCard(TypedDict):
    title: str
    value: str
    icon: str
    change: str
    is_up: bool


class Activity(TypedDict):
    description: str
    time: str


class Course(TypedDict):
    id: str
    title: str
    description: str
    status: Literal["Active", "Draft", "Archived"]
    students: int
    progress: int
    last_updated: str


class DashboardState(rx.State):
    active_section: str = "Dashboard"
    user_name: str = "Alex Johnson"
    user_email: str = "alex.j@learningcommunity.edu"
    user_bio: str = (
        "Passionate educator focusing on computer science and data literacy."
    )
    stats: list[StatCard] = [
        {
            "title": "Total Students",
            "value": "1,247",
            "icon": "users",
            "change": "+12%",
            "is_up": True,
        },
        {
            "title": "Active Courses",
            "value": "8",
            "icon": "book-open",
            "change": "+2",
            "is_up": True,
        },
        {
            "title": "Completion Rate",
            "value": "87%",
            "icon": "check-circle",
            "change": "-3%",
            "is_up": False,
        },
        {
            "title": "Revenue",
            "value": "$12,450",
            "icon": "dollar-sign",
            "change": "+18%",
            "is_up": True,
        },
    ]
    activities: list[Activity] = [
        {"description": "New enrollment in Python Basics", "time": "2 mins ago"},
        {"description": "Assignment submitted by Sarah M.", "time": "15 mins ago"},
        {"description": "Course 'Web Dev 101' updated", "time": "1 hour ago"},
        {"description": "New review: 5 stars on Data Science", "time": "3 hours ago"},
        {"description": "System backup completed", "time": "5 hours ago"},
    ]
    courses: list[Course] = [
        {
            "id": "c1",
            "title": "Python for Data Science",
            "description": "Master Python libraries like Pandas, NumPy and Matplotlib for data analysis.",
            "status": "Active",
            "students": 450,
            "progress": 65,
            "last_updated": "2024-03-20",
        },
        {
            "id": "c2",
            "title": "Web Development Bootcamp",
            "description": "Full-stack development with React, Node.js and PostgreSQL.",
            "status": "Active",
            "students": 320,
            "progress": 40,
            "last_updated": "2024-03-18",
        },
        {
            "id": "c3",
            "title": "AI Ethics & Governance",
            "description": "Understanding the societal impact and responsible AI implementation.",
            "status": "Draft",
            "students": 0,
            "progress": 0,
            "last_updated": "2024-03-15",
        },
    ]
    email_notifications: bool = True
    push_notifications: bool = False
    course_updates: bool = True
    student_messages: bool = True

    @rx.event
    def navigate_to(self, section: str):
        self.active_section = section
        if section == "Dashboard":
            return rx.redirect("/dashboard")
        elif section == "Your Courses":
            return rx.redirect("/courses")
        elif section == "Settings":
            return rx.redirect("/settings")
        elif section == "Course Builder":
            return rx.redirect("/course-builder")
        elif section == "Logout":
            self.active_section = "Dashboard"
            return rx.redirect("/")