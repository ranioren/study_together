import os
import os.path

# Relax token scope matching to avoid oauthlib errors when Google returns slightly different but functionally equivalent scopes
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    "https://www.googleapis.com/auth/classroom.rosters",            # Upgraded for invitations
    "https://www.googleapis.com/auth/classroom.profile.emails",     # To match student emails
    "https://www.googleapis.com/auth/drive.readonly"                # Added to read attached Drive docs
]

class ClassroomManager:
    def __init__(self, credentials_path="credentials.json", token_path="token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.service = None
        self.drive_service = None

    def authenticate(self):
        """Authenticates the user and creates the service."""
        from google.auth.exceptions import RefreshError
        
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except RefreshError:
                    print("Token expired or revoked. Deleting and re-authenticating...")
                    os.remove(self.token_path)
                    self.creds = None
            
            if not self.creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"'{self.credentials_path}' not found. Please follow README.md to create it.")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                # Force user consent to ensure we get the correct scopes
                self.creds = flow.run_local_server(port=0, prompt='consent')
            
                # Save the credentials for the next run
                with open(self.token_path, "w") as token:
                    token.write(self.creds.to_json())

        try:
            self.service = build("classroom", "v1", credentials=self.creds)
            self.drive_service = build("drive", "v3", credentials=self.creds)
            print("Authentication successful.")
        except HttpError as error:
            print(f"An error occurred during authentication: {error}")
            self.service = None
            self.drive_service = None

    def list_courses(self):
        """Lists the user's courses."""
        if not self.service:
            print("Service not authenticated. Call authenticate() first.")
            return []

        try:
            results = self.service.courses().list(pageSize=10).execute()
            courses = results.get("courses", [])

            if not courses:
                print("No courses found.")
                return []
            
            return courses
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

    def get_course_work(self, course_id):
        """Gets course work for a specific course."""
        if not self.service:
            print("Service not authenticated. Call authenticate() first.")
            return []
        
        try:
            results = self.service.courses().courseWork().list(
                courseId=course_id,
                courseWorkStates=["PUBLISHED", "DRAFT", "DELETED"]
            ).execute()
            course_work = results.get("courseWork", [])
            return course_work
        except HttpError as error:
             print(f"An error occurred retrieving course work: {error}")
             return []

    def get_course_work_materials(self, course_id):
        """Gets course work materials for a specific course."""
        if not self.service:
            print("Service not authenticated. Call authenticate() first.")
            return []
        
        try:
            results = self.service.courses().courseWorkMaterials().list(courseId=course_id).execute()
            materials = results.get("courseWorkMaterial", [])
            return materials
        except HttpError as error:
             print(f"An error occurred retrieving course materials: {error}")
             return []

    def get_student_submissions(self, course_id, coursework_id="-", states=None):
        """Gets student submissions for a specific course and coursework."""
        if not self.service:
            print("Service not authenticated. Call authenticate() first.")
            return []
        
        try:
            kwargs = {
                "courseId": course_id,
                "courseWorkId": coursework_id
            }
            if states:
                kwargs["states"] = states
                
            results = self.service.courses().courseWork().studentSubmissions().list(**kwargs).execute()
            submissions = results.get("studentSubmissions", [])
            return submissions
        except HttpError as error:
             print(f"An error occurred retrieving student submissions: {error}")
             return []

    def get_course_students(self, course_id):
        """Gets all students enrolled in a specific course."""
        if not self.service:
            print("Service not authenticated. Call authenticate() first.")
            return []
            
        try:
            results = self.service.courses().students().list(courseId=course_id).execute()
            students = results.get("students", [])
            return students
        except HttpError as error:
             print(f"An error occurred retrieving students: {error}")
             if error.resp.status == 403:
                 print("Check if the correct scopes are enabled and token.json is updated.")
             return []

    def invite_student(self, course_id, email):
        """Invites a student to the course via email."""
        if not self.service:
            print("Service not authenticated. Call authenticate() first.")
            return None

        try:
            invitation = {
                'userId': email,
                'courseId': course_id,
                'role': 'STUDENT'
            }
            invitation = self.service.invitations().create(body=invitation).execute()
            print(f"Invitation sent to {email}")
            return invitation
        except HttpError as error:
            print(f"An error occurred sending invitation: {error}")
            return None

    def get_drive_file_text(self, file_id):
        """Downloads a Google Doc from Drive as plain text."""
        if not self.drive_service:
            print("Drive service not authenticated.")
            return ""
        
        try:
            import io
            from googleapiclient.http import MediaIoBaseDownload
            
            # Export Google Docs to text. If it's a PDF this will fail and we'll catch it.
            request = self.drive_service.files().export_media(fileId=file_id, mimeType='text/plain')
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            return fh.getvalue().decode('utf-8')
        except HttpError as error:
            print(f"Error fetching or exporting Drive file {file_id}. Note: We currently only support text export for Google Docs. {error}")
            return ""

if __name__ == "__main__":
    # Test execution
    manager = ClassroomManager()
    try:
        manager.authenticate()
        courses = manager.list_courses()
        for course in courses:
            print(f"Course: {course['name']} (ID: {course['id']})")
    except Exception as e:
        print(f"Error: {e}")
