import reflex as rx
from typing import TypedDict, Literal
import json
import os
import uuid
import datetime




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
    topics: list[dict]


class DashboardState(rx.State):
    active_section: str = "Dashboard"
    oauth_code_verifier: str = ""
    user_name: str = "Local Dev User"
    user_email: str = "dev@localhost"
    user_bio: str = (
        "Developer and educator exploring localized curriculum generation."
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
    courses: list[Course] = []
    email_notifications: bool = True
    push_notifications: bool = False
    course_updates: bool = True
    student_messages: bool = True
    
    # Course Builder State
    course_name: str = ""
    course_author: str = ""
    course_description: str = ""
    my_topics: list[dict[str, str]] = []
    current_editing_id: str = ""
    full_courses: list[dict] = []
    user_info: dict[str, str] = {
        "email": "dev@localhost",
        "name": "Local Dev User",
        "picture": "/alex_avatar.png"
    }

    def on_load(self):
        """Triggered when the page or state is initialized."""
        self.load_courses()

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

    @rx.event
    def logout(self):
        self.user_info = {}
        self.full_courses = []
        self.courses = []
        self.active_section = "Dashboard"
        return rx.redirect("/")

    def get_user_dir(self):
        email = self.user_info.get("email", "dev@localhost")
        # Go up to project root from web/course_search/states/
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        user_dir = os.path.join(base_dir, "data", email)
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)
        return user_dir

    def load_courses(self):
        user_dir = self.get_user_dir()
        
        # Migration logic for legacy single-file storage
        email = self.user_info.get("email", "dev@localhost")
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        legacy_file = os.path.join(base_dir, "data", f"{email}.json")
        if os.path.exists(legacy_file):
            try:
                with open(legacy_file, "r") as f:
                    legacy_courses = json.load(f)
                for c in legacy_courses:
                    c_id = c.get("id")
                    if c_id:
                        with open(os.path.join(user_dir, f"{c_id}.json"), "w") as f:
                            json.dump(c, f, indent=2)
                # Rename legacy file to avoid re-migration
                os.rename(legacy_file, legacy_file + ".bak")
            except Exception as e:
                print(f"Migration error: {e}")

        # New style loading: one file per course
        self.full_courses = []
        try:
            for filename in sorted(os.listdir(user_dir)):
                if filename.endswith(".json"):
                    with open(os.path.join(user_dir, filename), "r") as f:
                        self.full_courses.append(json.load(f))
            
            self.courses = [
                {
                    "id": c["id"],
                    "title": c["title"],
                    "description": c["description"],
                    "status": c.get("status", "Active"),
                    "students": c.get("students", 0),
                    "progress": c.get("progress", 0),
                    "last_updated": c.get("last_updated", ""),
                    "topics": c.get("topics", [])
                }
                for c in self.full_courses
            ]
        except Exception as e:
            print(f"Error loading courses: {e}")

    def save_courses(self):
        user_dir = self.get_user_dir()
        try:
            for c in self.full_courses:
                c_id = c.get("id")
                if c_id:
                    with open(os.path.join(user_dir, f"{c_id}.json"), "w") as f:
                        json.dump(c, f, indent=2)
            self.load_courses() # Refresh summaries
        except Exception as e:
            print(f"Error saving courses: {e}")

    @rx.event
    def create_new_course(self):
        """Reset builder state and navigate to builder."""
        self.course_name = ""
        self.course_description = ""
        self.course_author = ""
        self.my_topics = []
        self.current_editing_id = ""
        return self.navigate_to("Course Builder")

    @rx.event
    def edit_course(self, course_id: str):
        """Load a course into the builder for editing."""
        course = None
        for c in self.full_courses:
            if c["id"] == course_id:
                course = c
                break
        
        if course:
            self.current_editing_id = course["id"]
            self.course_name = course.get("title", "")
            self.course_description = course.get("description", "")
            self.course_author = course.get("author", "")
    @rx.event
    def set_active_dashboard(self):
        self.active_section = "Dashboard"

    @rx.event
    def set_active_courses(self):
        self.active_section = "Your Courses"

    @rx.event
    def set_active_settings(self):
        self.active_section = "Settings"

    @rx.event
    def set_active_settings_nav(self):
        return self.navigate_to("Settings")

    @rx.event
    def navigate_sidebar(self, label: str):
        return self.navigate_to(label)