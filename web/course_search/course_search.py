import reflex as rx
import psycopg2
import os
import os.path
from fastembed import TextEmbedding
from dotenv import load_dotenv
import json
import uuid

from course_search.components.dashboard_layout import dashboard_layout
from course_search.components.feature_cards import feature_grid
from course_search.components.chat_interface import chat_interface
from course_search.pages.dashboard import dashboard_page
from course_search.pages.courses import courses_page
from course_search.pages.settings import settings_page
from course_search.states.dashboard_state import DashboardState

# Google API Imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Ensure environment variables are loaded from the root .env
import sys
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(root_dir)
load_dotenv(os.path.join(root_dir, ".env"))

try:
    from core.quiz_manager import QuizManager
except ImportError:
    print("Warning: could not import QuizManager from core.")
    QuizManager = None

db_url = os.getenv("AIVEN_DB_URL")

# Load model globally so it's cached in memory during server run
print("Loading fastembed model...")
try:
    model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
except Exception as e:
    print(f"Model load error: {e}")
    model = None

# --- Configuration ---
LOCAL_DEV = os.getenv("LOCAL_DEV", "False").lower() == "true"
# ---------------------

class State(DashboardState):
    """The app state."""
    # Search State
    search_query: str = ""
    search_source: str = "All"
    results: list[dict[str, str]] = []
    is_loading: bool = False
    upload_target_topic_id: str = ""
    
    def set_upload_target(self, topic_id: str):
        self.upload_target_topic_id = topic_id
        
    async def handle_topic_upload(self, files: list[rx.UploadFile]):
        if not self.upload_target_topic_id:
            return
            
        new_files = []
        upload_dir = rx.get_upload_dir()
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            
        for file in files:
            upload_data = await file.read()
            outfile = os.path.join(upload_dir, file.filename)
            with open(outfile, "wb") as f:
                f.write(upload_data)
            new_files.append(outfile)
            
        for i, t in enumerate(self.my_topics):
            if t["id"] == self.upload_target_topic_id:
                existing_str = self.my_topics[i].get("attached_files", "")
                existing = json.loads(existing_str) if existing_str else []
                existing.extend(new_files)
                self.my_topics[i]["attached_files"] = json.dumps(existing)
                break
                
        self.upload_target_topic_id = ""

    # Integration State
    classroom_course_url: str = ""
    show_classroom_dialog: bool = False
    classroom_progress: list[str] = []
    
    def logout(self):
        # Override logout in base state if needed, or just use parent
        return super().logout()
        
    def login_with_google(self):
        if LOCAL_DEV:
            # Bypass authentication for local development
            self.user_info = {
                "name": "Local Dev User",
                "email": "dev@localhost",
                "picture": "/alex_avatar.png"
            }
            self.load_courses()
            return rx.redirect("/dashboard")

        from google_auth_oauthlib.flow import Flow
        import os
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" # For local testing
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        creds_path = os.path.join(base_dir, 'config', 'webapp_credentials.json')
        scopes = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
        app_url = os.getenv("APP_URL", "http://localhost:3000")
        redirect_uri = f"{app_url}/callback"
        
        from core.oauth_helper import get_google_flow
        flow = get_google_flow(
            creds_path,
            scopes=scopes,
            redirect_uri=redirect_uri
        )
        # Using a clean auth URL and ensuring it forces prompt
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        return rx.redirect(auth_url)

    def handle_callback(self):
        code = self.router.page.params.get("code")
        if not code:
            return rx.redirect("/")
            
        from google_auth_oauthlib.flow import Flow
        import os
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        creds_path = os.path.join(base_dir, 'config', 'webapp_credentials.json')
        scopes = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
        app_url = os.getenv("APP_URL", "http://localhost:3000")
        redirect_uri = f"{app_url}/callback"
        
        try:
            from core.oauth_helper import get_google_flow
            flow = get_google_flow(
                creds_path,
                scopes=scopes,
                redirect_uri=redirect_uri
            )
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            from googleapiclient.discovery import build
            user_info_service = build('oauth2', 'v2', credentials=credentials)
            user_info = user_info_service.userinfo().get().execute()
            
            self.user_info = {
                "name": user_info.get("name", ""),
                "email": user_info.get("email", ""),
                "picture": user_info.get("picture", "")
            }
            self.load_courses()
        except Exception as e:
            print(f"Auth error: {e}")
            
        return rx.redirect("/")

    def clear_search(self):
        self.search_query = ""
        self.results = []

    def perform_search(self, form_data: dict = None):
        """Query the vector database."""
        if not self.search_query.strip():
            self.results = []
            return
            
        self.is_loading = True
        print(f"DEBUG: Starting search for: '{self.search_query}'")
        yield
        
        try:
            if model is None:
                raise ValueError("Model not loaded")
                
            query_vector = list(model.embed([self.search_query]))[0].tolist()
            
            conn = psycopg2.connect(db_url)
            with conn.cursor() as cur:
                from pgvector.psycopg2 import register_vector
                register_vector(conn)
                cur.execute(
                    """
                    SELECT course_title, module_name, course_slug, search_text, units, course_url
                    FROM course_modules
                    ORDER BY embedding <=> %s::vector
                    LIMIT 20;
                    """,
                    (query_vector,)
                )
                rows = cur.fetchall()
            conn.close()
            
            new_results = []
            for r in rows:
                course_url_str = str(r[5]).lower()
                if self.search_source == "Coursera" and "coursera" not in course_url_str:
                    continue
                if self.search_source == "Microsoft Learn" and "microsoft" not in course_url_str:
                    continue

                raw_units = r[4]
                units_parsed = []
                if raw_units and isinstance(raw_units, list):
                    for u in raw_units:
                        if isinstance(u, str):
                            units_parsed.append(u.replace('â€¢', '-').replace('Â', ''))
                        elif isinstance(u, dict):
                            units_parsed.append(u.get('title', u.get('name', '')).replace('â€¢', '-').replace('Â', ''))
                units_str = "\\n".join(f"• {u}" for u in units_parsed if u) if units_parsed else ""

                new_results.append({
                    "course_title": str(r[0]),
                    "module_name": str(r[1]) if r[1] else "Unnamed Module",
                    "course_slug": str(r[2]),
                    "description": str(r[3][:150]) + ("..." if len(str(r[3])) > 150 else ""),
                    "units": units_str,
                    "course_url": str(r[5])
                })
            self.results = new_results
            print(f"DEBUG: Found {len(new_results)} results for '{self.search_query}'")
                
        except Exception as e:
            import traceback
            print(f"DEBUG: Error searching database: {e}")
            traceback.print_exc()
            self.results = []
            
        self.is_loading = False

    def add_blank_topic(self):
        """Add a blank manual topic."""
        self.my_topics.append({
            "id": str(uuid.uuid4()),
            "name": "New Topic",
            "content": "",
            "source": "Manual",
            "urls": "",
            "assessment_type": "None",
            "quiz": "",
            "quiz_title": "Module Quiz",
            "quiz_form_id": "",
            "project_details": "",
            "project_link": "",
            "test_question": "",
            "test_description": "",
            "test_link": "",
            "attached_files": ""
        })

    def add_searched_topic(self, result: dict[str, str]):
        """Add a topic populated from search."""
        combined_content = result["description"]
        if result["units"]:
            combined_content += "\\n\\nUnits:\\n" + result["units"]
            
        self.my_topics.append({
            "id": str(uuid.uuid4()),
            "name": result["module_name"],
            "content": combined_content,
            "source": result["course_title"],
            "urls": result["course_url"],
            "assessment_type": "None",
            "quiz": "",
            "quiz_title": "Module Quiz",
            "quiz_form_id": "",
            "project_details": "",
            "project_link": "",
            "test_question": "",
            "test_description": "",
            "test_link": "",
            "attached_files": ""
        })
        
    def remove_topic(self, topic_id: str):
        self.my_topics = [t for t in self.my_topics if t["id"] != topic_id]

    def update_topic_name(self, topic_id: str, new_name: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["name"] = new_name
                break

    def update_topic_content(self, topic_id: str, new_content: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["content"] = new_content
                break

    def update_topic_urls(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["urls"] = new_val
                break
                
    def update_topic_assessment_type(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["assessment_type"] = new_val
                break

    def update_topic_quiz(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["quiz"] = new_val
                break

    def update_topic_quiz_title(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["quiz_title"] = new_val
                break

    def generate_quiz(self, topic_id: str):
        """Generate quiz using Groq via QuizManager."""
        if not QuizManager:
            self.classroom_progress.append("⚠️ QuizManager not found. Mocking output...")
            yield
            for i, t in enumerate(self.my_topics):
                if t["id"] == topic_id:
                    self.my_topics[i]["quiz"] = f"🚀 Mock Quiz for {t['name']}"
                    break
            return

        qm = QuizManager()
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                topic_name = t["name"]
                topic_desc = t["content"]
                self.classroom_progress.append(f"🧠 Asking Groq to generate quiz for '{topic_name}'...")
                yield
                
                material = f"Topic: {topic_name}\nDescription: {topic_desc}"
                quiz_data = qm.generate_weekly_quiz(material)
                
                if quiz_data:
                    # Request was for 4 questions, generate_weekly_quiz currently does 5.
                    # We can slice it or just keep 5. User asked for 4.
                    quiz_data = quiz_data[:4]
                    self.my_topics[i]["quiz"] = json.dumps(quiz_data, indent=2)
                    self.classroom_progress.append("✅ Quiz generated successfully!")
                    yield
                else:
                    self.classroom_progress.append("⚠️ Failed to generate quiz content.")
                    yield
                break

    def update_topic_project(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["project_details"] = new_val
                break

    def update_topic_project_link(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["project_link"] = new_val
                break

    def update_topic_test_question(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["test_question"] = new_val
                break
    
    def update_topic_test_description(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["test_description"] = new_val
                break

    def update_topic_test_link(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["test_link"] = new_val
                break

    def _internal_save(self):
        """Internal helper to save the current builder state without clearing it or navigating."""
        import datetime
        course_data = {
            "title": self.course_name if self.course_name else "Untitled Course",
            "description": self.course_description if self.course_description else "New custom course",
            "author": self.course_author,
            "status": "Draft",
            "students": 0,
            "progress": 0,
            "last_updated": datetime.date.today().strftime("%Y-%m-%d"),
            "topics": self.my_topics
        }

        if self.current_editing_id:
            for i, c in enumerate(self.full_courses):
                if c["id"] == self.current_editing_id:
                    course_data["id"] = self.current_editing_id
                    course_data["status"] = c.get("status", "Draft")
                    course_data["students"] = c.get("students", 0)
                    course_data["progress"] = c.get("progress", 0)
                    self.full_courses[i] = course_data
                    break
        else:
            self.current_editing_id = str(uuid.uuid4())[:8]
            course_data["id"] = self.current_editing_id
            self.full_courses.append(course_data)
        
        self.save_courses()
        return self.current_editing_id

    def save_course(self):
        """Save course and reset builder UI."""
        self._internal_save()
        
        # Reset builder state after saving
        self.course_name = ""
        self.course_description = ""
        self.course_author = ""
        self.my_topics = []
        self.current_editing_id = ""
        
        return DashboardState.navigate_to("Your Courses")

    def update_topic_quiz_form_id(self, topic_id: str, new_val: str):
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                self.my_topics[i]["quiz_form_id"] = new_val
                break

    def get_classroom_creds(self):
        """Helper to get credentials for Google APIs."""
        SCOPES = [
            'https://www.googleapis.com/auth/classroom.courses', 
            'https://www.googleapis.com/auth/classroom.topics',
            'https://www.googleapis.com/auth/classroom.courseworkmaterials',
            'https://www.googleapis.com/auth/classroom.coursework.me',
            'https://www.googleapis.com/auth/classroom.coursework.students',
            'https://www.googleapis.com/auth/forms.body',
            'https://www.googleapis.com/auth/drive.file'
        ]
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        creds_path = os.path.join(base_dir, 'config', 'credentials.json')
        token_path = os.path.join(base_dir, 'config', 'token.json')
        
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
        if not creds or not creds.valid or not set(SCOPES).issubset(set(creds.scopes or [])):
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            else:
                creds = None
                
            if not creds:
                if not os.path.exists(creds_path):
                    return None, f"Error: credentials.json not found in {base_dir}"
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
        return creds, None

    def create_empty_form(self, topic_id: str):
        """Create an empty Google Form for the topic."""
        creds, err = self.get_classroom_creds()
        if err:
            self.classroom_progress.append(f"⚠️ {err}")
            yield
            return

        service = build('forms', 'v1', credentials=creds)
        for i, t in enumerate(self.my_topics):
            if t["id"] == topic_id:
                title = t.get("quiz_title", "Module Quiz")
                self.classroom_progress.append(f"📄 Creating empty Google Form: '{title}'...")
                yield
                
                try:
                    form_body = {"info": {"title": title}}
                    form = service.forms().create(body=form_body).execute()
                    form_id = form.get("formId")
                    self.my_topics[i]["quiz_form_id"] = form_id
                    self.classroom_progress.append(f"✅ Form created! ID: {form_id[:10]}...")
                    yield
                except Exception as e:
                    self.classroom_progress.append(f"⚠️ Failed to create form: {str(e)[:40]}")
                    yield
                break

    def generate_form_with_quiz(self, topic_id: str):
        """Populate Google Form with quiz items from text area."""
        creds, err = self.get_classroom_creds()
        if err:
            self.classroom_progress.append(f"⚠️ {err}")
            yield
            return

        service = build('forms', 'v1', credentials=creds)
        for topic in self.my_topics:
            if topic["id"] == topic_id:
                form_id = topic.get("quiz_form_id")
                if not form_id:
                    self.classroom_progress.append("⚠️ Please create an empty form first!")
                    yield
                    return

                quiz_items_text = topic.get("quiz", "")
                try:
                    quiz_data = json.loads(quiz_items_text)
                except Exception:
                    self.classroom_progress.append("⚠️ Quiz items are not valid JSON. Please generate first.")
                    yield
                    return

                # Ensure it's a list
                if not isinstance(quiz_data, list):
                    quiz_data = [quiz_data]

                self.classroom_progress.append(f"📝 Populating Form {form_id[:10]} with {len(quiz_data)} questions...")
                yield

                requests = [
                    {
                        "updateSettings": {
                            "settings": {"quizSettings": {"isQuiz": True}},
                            "updateMask": "quizSettings.isQuiz"
                        }
                    }
                ]

                # Add each question
                for index, q_item in enumerate(quiz_data):
                    question = q_item.get("question", "Question Text")
                    options = q_item.get("options", ["Option 1", "Option 2"])
                    correct_index = q_item.get("correct_index", 0)
                    correct_answer = options[correct_index] if correct_index < len(options) else options[0]

                    requests.append({
                        "createItem": {
                            "item": {
                                "title": question,
                                "questionItem": {
                                    "question": {
                                        "grading": {
                                            "pointValue": 1,
                                            "correctAnswers": {"answers": [{"value": correct_answer}]}
                                        },
                                        "choiceQuestion": {
                                            "type": "RADIO",
                                            "options": [{"value": opt} for opt in options]
                                        }
                                    }
                                }
                            },
                            "location": {"index": index}
                        }
                    })

                try:
                    service.forms().batchUpdate(formId=form_id, body={"requests": requests}).execute()
                    self.classroom_progress.append("🎉 Form updated with quiz items!")
                    yield
                except Exception as e:
                    self.classroom_progress.append(f"⚠️ BatchUpdate failed: {str(e)[:40]}")
                    yield
                break

    def confirm_classroom(self):
        """Open the consent dialog."""
        self.show_classroom_dialog = True
        self.classroom_progress = []
        yield

    def cancel_classroom(self):
        """Discharge the consent dialog."""
        self.show_classroom_dialog = False

    def add_to_google_classroom(self):
        self.is_loading = True
        self.classroom_course_url = ""
        self.classroom_progress = ["💾 Auto-saving current course state to local database..."]
        yield
        
        try:
            # Step 0: Auto-save local draft
            self._internal_save()
            self.classroom_progress.append("✅ Local draft secured.")
            self.classroom_progress.append("🔌 Initializing Google Workspace secure connection...")
            yield
            
            creds, err = self.get_classroom_creds()
            if err:
                self.classroom_progress.append(f"⚠️ {err}")
                self.is_loading = False
                yield
                return
                
            service = build('classroom', 'v1', credentials=creds)
            
            self.classroom_progress.append("✅ Authenticated securely with Google Classroom.")
            yield
            
            course_name_parsed = self.course_name if self.course_name.strip() else 'Untitled Curriculum Course'
            self.classroom_progress.append(f"📦 Provisioning parent Google Course: '{course_name_parsed}'...")
            yield
            
            course_body = {
                'name': course_name_parsed,
                'descriptionHeading': self.course_author if self.course_author.strip() else 'AI Curriculum Builder',
                'description': self.course_description if self.course_description.strip() else 'Generated Course via Curriculum Builder',
                'ownerId': 'me',
                'courseState': 'PROVISIONED' # Reverted to PROVISIONED as personal accounts cannot create ACTIVE courses via API
            }
            
            course = service.courses().create(body=course_body).execute()
            course_id = course.get('id')
            self.classroom_course_url = course.get('alternateLink', '')
            course_teacher_folder = course.get('teacherFolder', {}).get('id')
            
            drive_service = build('drive', 'v3', credentials=creds)
            
            self.classroom_progress.append(f"🎓 Course Successfully Initialized! Course ID: {course_id}")
            self.classroom_progress.append("🔄 Mapping Curriculum Topics into Google Classroom structure...")
            yield
            
            # Helper to sanitize URLs
            def sanitize_url(url):
                u = url.strip()
                if not u: return None
                if not (u.startswith('http://') or u.startswith('https://')):
                    return 'https://' + u
                return u

            # Create Topics (Headers) in the generated classroom
            used_topic_names = {}
            index = 1
            for topic in self.my_topics:
                raw_title = topic['name'] if topic['name'].strip() else 'Unnamed Topic'
                
                # Handle Duplicate Topic Names
                topic_title = raw_title
                if topic_title in used_topic_names:
                    used_topic_names[topic_title] += 1
                    topic_title = f"{topic_title} ({used_topic_names[topic_title]})"
                    self.classroom_progress.append(f"  ℹ️ Duplicate topic name found. Renaming to '{topic_title}'")
                else:
                    used_topic_names[topic_title] = 1
                self.classroom_progress.append(f"  👉 Generating module header: {topic_title}...")
                yield
                
                topic_body = {
                    'name': topic_title
                }
                created_topic = service.courses().topics().create(courseId=course_id, body=topic_body).execute()
                classroom_topic_id = created_topic.get('topicId')
                
                # Build list of materials (URLs first)
                materials_list = []
                topic_urls = topic.get("urls", "")
                if topic_urls:
                    # Support both real newlines and escaped newlines
                    for url in topic_urls.replace('\\n', '\n').split('\n'):
                        s_url = sanitize_url(url)
                        if s_url:
                            materials_list.append({
                                'link': {'url': s_url}
                            })
                            
                # Handle Google Drive Folder and File Uploads
                attached_files_str = topic.get("attached_files", "")
                if attached_files_str and course_teacher_folder:
                    attached_files = json.loads(attached_files_str)
                    if attached_files:
                        self.classroom_progress.append(f"  📁 Creating Drive folder for topic: {topic_title}...")
                        yield
                        folder_metadata = {
                            'name': topic_title,
                            'mimeType': 'application/vnd.google-apps.folder',
                            'parents': [course_teacher_folder]
                        }
                        drive_folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
                        topic_folder_id = drive_folder.get('id')
                        
                        self.classroom_progress.append(f"  ⬆️ Uploading {len(attached_files)} files to Drive...")
                        yield
                        
                        for file_path in attached_files:
                            if os.path.exists(file_path):
                                filename = os.path.basename(file_path)
                                file_metadata = {'name': filename, 'parents': [topic_folder_id]}
                                media = MediaFileUpload(file_path, resumable=True)
                                uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                                
                                materials_list.append(
                                    {
                                        'driveFile': {
                                            'driveFile': {
                                                'id': uploaded_file.get('id')
                                            },
                                            'shareMode': 'VIEW'
                                        }
                                    }
                                )
                                
                # Create Material item (Header + URLs + Description)
                self.classroom_progress.append("  🔗 Publishing Topic Materials & Description...")
                yield
                topic_content = topic.get("content", "").strip()
                material_body = {
                    'title': f"{topic_title}",
                    'description': topic_content if topic_content else f"Resources and information for {topic_title}.",
                    'topicId': classroom_topic_id,
                    'materials': materials_list,
                    'state': 'PUBLISHED'
                }
                try:
                    service.courses().courseWorkMaterials().create(courseId=course_id, body=material_body).execute()
                except Exception as mat_e:
                    # Log more detail if possible
                    err_msg = str(mat_e)
                    if "Requested entity was not found" in err_msg:
                        err_msg = "Topic ID not found yet (latency)"
                    self.classroom_progress.append(f"  ⚠️ Failed to publish materials: {err_msg[:40]}...")
                    yield
                    
                # Handle Topic Assessments
                assessment_type = topic.get("assessment_type", "None")
                if assessment_type == "Project":
                    self.classroom_progress.append(f"  📝 Creating Project Assignment for {topic_title}...")
                    yield
                    
                    project_materials = []
                    project_url = sanitize_url(topic.get("project_link", ""))
                    if project_url:
                        project_materials.append({'link': {'url': project_url}})
                        
                    project_body = {
                        'title': f"{topic_title} Project",
                        'description': topic.get("project_details", ""),
                        'topicId': classroom_topic_id,
                        'workType': 'ASSIGNMENT',
                        'state': 'PUBLISHED',
                        'materials': project_materials
                    }
                    try:
                        service.courses().courseWork().create(courseId=course_id, body=project_body).execute()
                    except Exception as proj_e:
                        self.classroom_progress.append(f"  ⚠️ Failed to create Project: {str(proj_e)[:40]}...")
                        yield
                                            
                elif assessment_type == "Test":
                    self.classroom_progress.append(f"  📝 Creating Test Question for {topic_title}...")
                    yield
                    test_materials = []
                    test_url = sanitize_url(topic.get("test_link", ""))
                    if test_url:
                        test_materials.append({'link': {'url': test_url}})
                        
                    test_question = topic.get("test_question", "").strip()
                    if not test_question:
                        test_question = f"{topic_title} Question"
                        
                    test_description = topic.get("test_description", "").strip()
                        
                    test_body = {
                        'title': test_question,
                        'description': test_description,
                        'topicId': classroom_topic_id,
                        'workType': 'SHORT_ANSWER_QUESTION',
                        'state': 'PUBLISHED',
                        'materials': test_materials
                    }
                    try:
                        service.courses().courseWork().create(courseId=course_id, body=test_body).execute()
                    except Exception as test_e:
                        self.classroom_progress.append(f"  ⚠️ Failed to create Test: {str(test_e)[:40]}...")
                        yield
                    
                elif assessment_type == "Quiz":
                    self.classroom_progress.append(f"  📝 Creating Quiz Question for {topic_title}...")
                    yield
                    
                    quiz_materials = []
                    form_id = topic.get("quiz_form_id")
                    if form_id:
                        form_url = f"https://docs.google.com/forms/d/{form_id}/edit"
                        quiz_materials.append({'link': {'url': form_url}})
                        
                    quiz_content = topic.get("quiz", "").strip()
                    quiz_body = {
                        'title': f"Quiz: {topic_title}",
                        'description': quiz_content if quiz_content else f"Please complete the quiz for {topic_title}.",
                        'topicId': classroom_topic_id,
                        'workType': 'SHORT_ANSWER_QUESTION',
                        'state': 'PUBLISHED',
                        'materials': quiz_materials
                    }
                    try:
                        service.courses().courseWork().create(courseId=course_id, body=quiz_body).execute()
                    except Exception as quiz_e:
                        self.classroom_progress.append(f"  ⚠️ Failed to create Quiz: {str(quiz_e)[:40]}...")
                        yield
                                
                index += 1
                
            self.classroom_progress.append(f"🎉 Architecture Complete! Synchronized {index - 1} topics perfectly.")
            yield
            
        except Exception as e:
            self.classroom_progress.append(f"❌ API CRITICAL ERROR: {str(e)}")
            print(f"Failed to add to classroom: {e}")
            yield
            
        self.is_loading = False


def render_search_result(result: dict[str, str]):
    return rx.box(
        rx.vstack(
            rx.heading(result["module_name"], size="4", color="blue.600"),
            rx.hstack(
                rx.cond(
                    result["course_url"].to_string().contains("coursera"),
                    rx.image(src="/coursera.webp", height="20px", width="auto", object_fit="contain"),
                    rx.cond(
                        result["course_url"].to_string().contains("microsoft"),
                        rx.image(src="/msft.png", height="20px", width="20px", object_fit="contain")
                    )
                ),
                rx.text(f"From Course - {result['course_slug']}", font_weight="bold", size="2"),
                align_items="center",
                spacing="2"
            ),
            rx.text(result["description"], size="1", color="gray.600"),
            rx.cond(
                result["units"] != "",
                rx.el.details(
                    rx.el.summary("Expand for module units", style={"cursor": "pointer", "fontSize": "0.875rem", "fontWeight": "600", "color": "#3182ce"}),
                    rx.box(
                        rx.text(result["units"], size="2", style={"whiteSpace": "pre-wrap"}),
                        padding="3",
                        background_color="gray.50",
                        border_radius="md",
                        margin_top="2"
                    )
                )
            ),
            rx.hstack(
                rx.link(
                    rx.button(
                        "Go to Course",
                        size="1",
                        background_color="navy",
                        color="white",
                        width="100%"
                    ),
                    href=result["course_url"],
                    is_external=True,
                    width="50%",
                    text_decoration="none"
                ),
                rx.button(
                    "Add to Builder", 
                    on_click=lambda: State.add_searched_topic(result),
                    size="1",
                    color_scheme="green",
                    width="50%"
                ),
                width="100%",
                spacing="2"
            ),
            align_items="start",
            spacing="2"
        ),
        class_name="w-full bg-white p-6 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all mb-4"
    )


def render_builder_topic(topic: dict[str, str]):
    return rx.box(
        rx.vstack(
            # Header
            rx.hstack(
                rx.input(
                    value=topic["name"],
                    on_change=lambda val: State.update_topic_name(topic["id"], val),
                    placeholder="Topic Name",
                    font_weight="bold",
                    width="100%"
                ),
                rx.icon_button(
                    rx.icon(tag="delete"),
                    on_click=lambda: State.remove_topic(topic["id"]),
                    color_scheme="red",
                    variant="ghost"
                ),
                width="100%"
            ),
            # Content
            rx.text_area(
                value=topic["content"],
                on_change=lambda val: State.update_topic_content(topic["id"], val),
                placeholder="Topic Content / Description...",
                min_height="80px",
                width="100%"
            ),
            
            # URL List
            rx.text("Resource URLs", size="2", font_weight="bold", color="gray.600"),
            rx.text_area(
                value=topic["urls"],
                on_change=lambda val: State.update_topic_urls(topic["id"], val),
                placeholder="List URLs here (one per line)...",
                height="60px",
                width="100%"
            ),
            
            rx.divider(margin_y="2"),
            
            # Assessments Dropdown
            rx.hstack(
                rx.text("Assessment:", size="2", font_weight="bold", color="gray.600"),
                rx.select(
                    ["None", "Quiz", "Project", "Test"],
                    value=topic["assessment_type"],
                    on_change=lambda val: State.update_topic_assessment_type(topic["id"], val),
                    size="2",
                    width="200px"
                ),
                width="100%", align_items="center"
            ),
            
            # Conditional Assessment Fields
            rx.cond(
                topic["assessment_type"] == "Quiz",
                rx.vstack(
                    rx.hstack(
                        rx.input(value=topic["quiz_title"], on_change=lambda val: State.update_topic_quiz_title(topic["id"], val), placeholder="Quiz Title", size="2", flex="1"),
                        rx.button("Create Empty Form", on_click=lambda: State.create_empty_form(topic["id"]), size="1", color_scheme="blue"),
                        width="100%", spacing="2"
                    ),
                    rx.button("Generate with LearnLM ✨", on_click=lambda: State.generate_quiz(topic["id"]), size="1", color_scheme="purple"),
                    rx.text_area(value=topic["quiz"], on_change=lambda val: State.update_topic_quiz(topic["id"], val), placeholder="Quiz JSON items...", size="2", width="100%", min_height="120px"),
                    rx.button("Generate Google Form with Quiz", on_click=lambda: State.generate_form_with_quiz(topic["id"]), size="1", color_scheme="green"),
                    width="100%", align_items="start"
                )
            ),
            rx.cond(
                topic["assessment_type"] == "Project",
                rx.vstack(
                    rx.text_area(value=topic["project_details"], on_change=lambda val: State.update_topic_project(topic["id"], val), placeholder="Instructions", size="2", width="100%", min_height="80px"),
                    rx.input(value=topic["project_link"], on_change=lambda val: State.update_topic_project_link(topic["id"], val), placeholder="Project Link (URL)", size="2", width="100%"),
                    width="100%", align_items="start"
                )
            ),
            rx.cond(
                topic["assessment_type"] == "Test",
                rx.vstack(
                    rx.input(value=topic["test_question"], on_change=lambda val: State.update_topic_test_question(topic["id"], val), placeholder="Short Question", size="2", width="100%"),
                    rx.text_area(value=topic["test_description"], on_change=lambda val: State.update_topic_test_description(topic["id"], val), placeholder="Description", size="2", width="100%", height="60px"),
                    rx.input(value=topic["test_link"], on_change=lambda val: State.update_topic_test_link(topic["id"], val), placeholder="URL Link", size="2", width="100%"),
                    width="100%", align_items="start"
                )
            ),

            rx.cond(
                topic["source"] != "Manual",
                rx.hstack(
                    rx.cond(
                        topic["urls"].to_string().contains("coursera"),
                        rx.image(src="/coursera.webp", height="20px", width="auto", object_fit="contain"),
                        rx.cond(
                            topic["urls"].to_string().contains("microsoft"),
                            rx.image(src="/msft.png", height="20px", width="20px", object_fit="contain"),
                            rx.text(topic["source"], size="1", font_weight="bold", color="gray.700")
                        )
                    ),
                    margin_top="3",
                    align_items="center",
                    spacing="2"
                )
            ),
            rx.divider(margin_y="2"),
            rx.hstack(
                rx.cond(
                    topic["attached_files"] != "",
                    rx.text("Files attached for upload ✅", size="2", color="green.600", font_weight="bold"),
                    rx.text("No files attached", size="2", color="gray.500")
                ),
                rx.spacer(),
                rx.button(
                    "Attach Files",
                    on_click=lambda: State.set_upload_target(topic["id"]),
                    size="1",
                    color_scheme="blue",
                    variant="soft"
                ),
                width="100%",
                align_items="center"
            ),
            width="100%",
            spacing="2"
        ),
        class_name="w-full bg-white p-6 rounded-2xl border border-gray-100 shadow-sm mb-4 border-l-4 border-l-green-500",
    )


def course_builder_page() -> rx.Component:
    return dashboard_layout(
        rx.box(
        # File Upload Modal
        rx.cond(
            State.upload_target_topic_id != "",
            rx.box(
                rx.vstack(
                    rx.heading("Upload Files for Topic", size="5"),
                    rx.text("Select files to attach. They will be uploaded to a dedicated Google Drive folder for this topic when you publish the course.", size="2", color="gray.600"),
                    rx.upload(
                        rx.vstack(
                            rx.icon(tag="upload", size=32),
                            rx.text("Click or drag and drop files here"),
                            align_items="center",
                            spacing="2",
                        ),
                        id="topic_file_uploader",
                        multiple=True,
                        padding="6",
                        border="2px dashed",
                        border_color="gray.300",
                        border_radius="md",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.button("Cancel", on_click=lambda: State.set_upload_target(""), color_scheme="gray", variant="soft"),
                        rx.button("Attach Selected Files", on_click=State.handle_topic_upload(rx.upload_files(upload_id="topic_file_uploader")), color_scheme="blue"),
                        width="100%",
                        justify_content="end",
                        spacing="3"
                    ),
                    padding="6", background_color="white", border_radius="xl", width=["90%", "500px"], box_shadow="lg", spacing="4"
                ),
                position="fixed", top="0", left="0", width="100vw", height="100vh",
                background_color="rgba(0,0,0,0.6)", z_index="10000",
                display="flex", align_items="center", justify_content="center"
            )
        ),

        # Dialog Modal
        rx.cond(
            State.show_classroom_dialog,
            rx.box(
                rx.vstack(
                    rx.heading("System Authorization Required", size="5", margin_bottom="2"),
                    rx.text("You are about to launch a real Course on your Google Classroom domain via OAuth 2.0."),
                    rx.divider(margin_y="2"),
                    rx.text("Proposed Course Name: ", rx.cond(State.course_name != "", State.course_name, "Untitled Curriculum Builder Course"), font_weight="bold"),
                    rx.text("Total Topics Attached: ", State.my_topics.length(), font_weight="bold"),
                    
                    # Log Array inside the Modal
                    rx.cond(
                        State.classroom_progress.length() > 0,
                        rx.box(
                            rx.vstack(
                                rx.foreach(
                                    State.classroom_progress,
                                    lambda msg: rx.text(msg, font_family="monospace", size="2", color="gray.800")
                                ),
                                align_items="start",
                                spacing="1"
                            ),
                            padding="3", background_color="gray.100", border_radius="md",
                            border="1px solid", border_color="gray.300",
                            width="100%", margin_y="3", max_height="200px", overflow_y="auto"
                        )
                    ),
                    
                    # Final Success Button
                    rx.cond(
                        State.classroom_course_url != "",
                        rx.hstack(
                            rx.text("✅ Successfully provisioned Classroom!", color="green.600", font_weight="bold"),
                            rx.link(
                                rx.button("Launch Classroom Space", size="2", color_scheme="green", variant="solid"),
                                href=State.classroom_course_url,
                                is_external=True
                            ),
                            padding="4", background_color="green.50", border_radius="md", width="100%", justify_content="center"
                        )
                    ),
                    
                    rx.spacer(),
                    rx.hstack(
                        rx.button(
                            rx.cond(State.classroom_course_url != "", "Close", "❌ Cancel"), 
                            on_click=State.cancel_classroom, color_scheme="gray", variant="soft", size="3"
                        ),
                        rx.cond(
                            State.classroom_course_url == "",
                            rx.button(
                                "✅ Approve & Initialize", 
                                on_click=State.add_to_google_classroom, 
                                is_loading=State.is_loading,
                                color_scheme="green", size="3"
                            )
                        ),
                        width="100%",
                        justify_content="end"
                    ),
                    padding="6",
                    background_color="white",
                    border_radius="xl",
                    width=["90%", "600px"],
                    box_shadow="0 25px 50px -12px rgba(0, 0, 0, 0.25)",
                    spacing="3"
                ),
                position="fixed", top="0", left="0", width="100vw", height="100vh",
                background_color="rgba(0,0,0,0.6)", z_index="9999",
                display="flex", align_items="center", justify_content="center"
            )
        ),
    
        rx.heading("Platform: Build Your Own Course", size="8", margin_bottom="1rem", text_align="center"),
        
        rx.flex(
            # LEFT SIDE: Course Builder
            rx.box(
                rx.vstack(
                    rx.box(
                        rx.heading("Course Details", class_name="text-lg font-bold text-gray-900 mb-4"),
                        rx.vstack(
                            rx.input(placeholder="Course Name", value=State.course_name, on_change=State.set_course_name, width="100%"),
                            rx.input(placeholder="Author Name", value=State.course_author, on_change=State.set_course_author, width="100%"),
                            rx.text_area(placeholder="General Course Outline or Description...", value=State.course_description, on_change=State.set_course_description, width="100%"),
                            width="100%"
                        ),
                        width="100%",
                        margin_bottom="2"
                    ),
                    rx.box(height="1.5rem"),
                    rx.divider(border_color="gray.300", border_width="1px"),
                    rx.box(height="1.5rem"),
                    rx.vstack(
                        rx.hstack(
                            rx.heading("Curriculum Topics", class_name="text-lg font-bold text-gray-900"),
                            rx.spacer(),
                            rx.button(rx.icon("plus", class_name="mr-2 h-4 w-4"), "Add Blank Topic", on_click=State.add_blank_topic, size="2", color_scheme="blue"),
                            width="100%",
                            align_items="center"
                        ),
                        
                        rx.cond(
                            State.my_topics.length() > 0,
                            rx.vstack(
                                rx.foreach(
                                    State.my_topics,
                                    render_builder_topic
                                ),
                                width="100%"
                            ),
                            rx.box(
                                rx.text("No topics added yet. Add a blank one or search for modules!", class_name="text-gray-500 font-medium text-sm text-center"),
                                class_name="w-full bg-gray-50 p-6 rounded-2xl border border-dashed border-gray-200 mt-2"
                            )
                        ),
                        
                        rx.divider(margin_y="4"),
                        
                        # Bottom Action Buttons
                        rx.hstack(
                            rx.spacer(),
                            rx.button(
                                "Save Course", 
                                on_click=State.save_course, 
                                color_scheme="blue",
                                size="3"
                            ),
                            rx.button(
                                rx.icon(tag="graduation-cap", class_name="mr-2"),
                                "Add to Google Classroom", 
                                on_click=State.confirm_classroom,
                                color_scheme="green",
                                variant="soft",
                                size="3"
                            ),
                            width="100%",
                            spacing="3"
                        ),
                        
                        width="100%",
                        spacing="3"
                    ),
                    width="100%",
                    spacing="0"
                ),
                class_name="w-full bg-white p-6 rounded-2xl border border-gray-100 shadow-sm",
                flex="1",
                height="fit-content"
            ),
            
            # RIGHT SIDE: Database Search
            rx.box(
                rx.heading("Explore Modules Database", class_name="text-lg font-bold text-gray-900 mb-4"),
                rx.form(
                    rx.hstack(
                        rx.vstack(
                            rx.text("Search query", size="1", color="transparent", font_weight="bold"),
                            rx.box(
                                rx.icon("search", class_name="h-4 w-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"),
                                rx.input(
                                    placeholder="Search topics...",
                                    value=State.search_query,
                                    on_change=State.set_search_query,
                                    class_name="pl-10",
                                    width="100%"
                                ),
                                class_name="relative w-full"
                            ),
                            width="100%",
                            flex="2",
                            spacing="1"
                        ),
                        rx.vstack(
                            rx.text("Data Source", size="1", font_weight="bold", color="gray.500"),
                            rx.select(
                                ["All", "Coursera", "Microsoft Learn"],
                                value=State.search_source,
                                on_change=State.set_search_source,
                                size="2",
                                width="140px"
                            ),
                            spacing="1",
                            align_items="start"
                        ),
                        rx.button(
                            "Clear",
                            type="button",
                            on_click=State.clear_search,
                            color_scheme="gray",
                            variant="soft"
                        ),
                        rx.button(
                            "Search", 
                            type="submit",
                            is_loading=State.is_loading,
                            color_scheme="blue"
                        ),
                        width="100%",
                        align_items="end",
                        spacing="3"
                    ),
                    on_submit=State.perform_search,
                    width="100%",
                    margin_bottom="6"
                ),
                rx.box(height="1.5rem"),
                rx.divider(border_color="gray.300", border_width="1px"),
                rx.box(height="1.5rem"),
                rx.cond(
                    State.is_loading,
                    rx.center(rx.spinner(size="3"), padding="10", width="100%"),
                    rx.cond(
                        State.results.length() > 0,
                        rx.vstack(
                            rx.foreach(
                                State.results,
                                render_search_result
                            ),
                            width="100%"
                        ),
                        rx.text("Start typing to discover existing course modules...", class_name="text-gray-500 font-medium text-sm text-center block mt-4")
                    )
                ),
                class_name="w-full bg-white p-6 rounded-2xl border border-gray-100 shadow-sm",
                flex="1",
                height="fit-content"
            ),
            
            width="100%",
            spacing="8",
            flex_direction=["column", "column", "row"],  # Responsive layout
            align_items="flex-start"
        ),
        padding="6",
        width="100%",
        max_width="100%"
        )
    )

def index() -> rx.Component:
    return rx.box(
        # Top Navigation / Account Bar
        rx.box(
            rx.cond(
                State.user_info.contains("name"),
                rx.hstack(
                    rx.avatar(src=State.user_info["picture"], size="2", radius="full", border="2px solid white"),
                    rx.text(f"Welcome, {State.user_info['name']}", font_weight="700", color="gray.800"),
                    rx.button("Logout", on_click=State.logout, size="2", color_scheme="red", variant="soft", radius="full"),
                    spacing="4",
                    align_items="center"
                ),
                rx.button(
                    rx.icon(tag="chrome", size=18),
                    "Expert Login",
                    on_click=State.login_with_google,
                    color_scheme="blue",
                    variant="solid",
                    radius="full",
                    size="3",
                    box_shadow="lg",
                    _hover={"transform": "scale(1.05)", "box_shadow": "xl"},
                    transition="all 0.2s"
                )
            ),
            width="100%",
            display="flex",
            justify_content="flex-end",
            padding="6",
            position="absolute",
            top="0",
            z_index="100"
        ),
        
        rx.center(
            rx.vstack(
                # Hero Content
                rx.vstack(
                    rx.el.h1(
                        "#LearningCommunity",
                        class_name="text-6xl md:text-8xl font-black tracking-tighter mb-2 text-center bg-clip-text text-transparent bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 animate-gradient-x w-full",
                        style={"lineHeight": "1.1", "textAlign": "center"}
                    ),
                    rx.el.h2(
                        "#CommunityLearning",
                        class_name="text-2xl md:text-3xl font-bold text-center text-gray-800 mb-6 tracking-tight w-full",
                        style={"textAlign": "center"}
                    ),
                    rx.el.p(
                        "Educate your community, Share your knowledge & experience, Monetize from what you built!",
                        class_name="text-lg md:text-xl font-medium text-gray-500 max-w-[600px] text-center mb-12 w-full",
                        style={"textAlign": "center"}
                    ),
                    align_items="center",
                    justify_content="center",
                    text_align="center",
                    width="100%",
                    spacing="0",
                    padding_top="8rem",
                    padding_bottom="4rem",
                    class_name="animate-in fade-in slide-in-from-bottom-8 duration-1000 w-full flex flex-col items-center"
                ),
                
                # Glassmorphic Main Container
                rx.box(
                    rx.vstack(
                        rx.el.section(feature_grid(), class_name="w-full mb-12"),
                        rx.el.section(chat_interface(), class_name="w-full"),
                        spacing="0",
                        width="100%"
                    ),
                    class_name="max-w-[850px] mx-auto w-full px-8 py-12 bg-white/80 backdrop-blur-xl border border-white/20 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.1)] rounded-[3rem] mb-24 relative overflow-hidden",
                    style={"boxShadow": "0 20px 50px rgba(0,0,0,0.05)"}
                ),
                
                spacing="0",
                width="100%"
            ),
            width="100%"
        ),
        
        # Background Elements
        rx.box(
            class_name="fixed top-0 left-0 w-full h-full -z-10",
            style={
                "background": "radial-gradient(circle at 0% 0%, rgba(59, 130, 246, 0.05) 0%, transparent 50%), radial-gradient(circle at 100% 100%, rgba(147, 51, 234, 0.05) 0%, transparent 50%), #f8fafc"
            }
        ),
        
        min_h="100vh",
        position="relative",
        background_color="gray.50",
        font_family="'Inter', sans-serif"
    )


@rx.page(route="/callback", on_load=State.handle_callback)
def callback() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.spinner(size="3"),
            rx.text("Authenticating...")
        ),
        height="100vh"
    )

app = rx.App(
    theme=rx.theme(appearance="light", accent_color="blue"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap",
            rel="stylesheet",
        ),
        rx.el.style("""
            .custom-scrollbar::-webkit-scrollbar {
                width: 6px;
            }
            .custom-scrollbar::-webkit-scrollbar-track {
                background: transparent;
            }
            .custom-scrollbar::-webkit-scrollbar-thumb {
                background: #e5e7eb;
                border-radius: 10px;
            }
            .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                background: #d1d5db;
            }
        """),
    ],
)
app.add_page(index, route="/", on_load=DashboardState.on_load)

app.add_page(
    dashboard_page,
    route="/dashboard",
    on_load=[DashboardState.on_load, DashboardState.set_active_dashboard],
)
app.add_page(
    courses_page,
    route="/courses",
    on_load=[DashboardState.on_load, DashboardState.set_active_courses],
)
app.add_page(
    settings_page,
    route="/settings",
    on_load=[DashboardState.on_load, DashboardState.set_active_settings],
)
app.add_page(
    course_builder_page,
    route="/course-builder",
    on_load=[DashboardState.on_load, DashboardState.set_active_courses],
)

# --- Production Static File Serving ---
# If we are running on DigitalOcean and have a built frontend, serve it directly from the backend!
import os
# --- Internal OAuth Proxy ---
# Forward oauth2 callbacks from the single public port to the internal Bot web server
from fastapi import Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.exceptions import HTTPException
import requests
import os

@app.api.get("/oauth2callback")
async def oauth2callback_proxy(request: Request):
    try:
        url = f"http://127.0.0.1:8081/oauth2callback?{request.url.query}"
        resp = requests.get(url, timeout=5)
        return HTMLResponse(content=resp.text, status_code=resp.status_code)
    except Exception as e:
        return HTMLResponse(content=f"Error forwarding OAuth to Bot: {e}", status_code=500)

# --- Production Static File Serving ---
# If we are running on DigitalOcean and have a built frontend, serve it directly from the backend!
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".web", "_static")

@app.api.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    # Only serve static files if the directory exists (production mode)
    if not os.path.exists(static_dir):
        return HTMLResponse("404 Not Found (Static dir missing)", status_code=404)
        
    path = request.url.path
    if path == "/":
        path = "/index.html"
    elif not path.endswith(".html") and "." not in path.split("/")[-1]:
        path += ".html"
        
    file_path = os.path.join(static_dir, path.lstrip("/"))
    if os.path.exists(file_path):
        return FileResponse(file_path)
    
    index_path = os.path.join(static_dir, path.lstrip("/"), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
        
    not_found_page = os.path.join(static_dir, "404.html")
    if os.path.exists(not_found_page):
        return FileResponse(not_found_page, status_code=404)
        
    return HTMLResponse("404 Not Found", status_code=404)
