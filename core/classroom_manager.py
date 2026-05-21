import os
import os.path
import json
from . import database

# Relax token scope matching to avoid oauthlib errors when Google returns slightly different but functionally equivalent scopes
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
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
    def __init__(self, credentials_path="config/credentials.json"):
        self.credentials_path = credentials_path

    def get_services(self, guild_id):
        """Authenticates and returns the Classroom and Drive services for a specific guild."""
        from google.auth.exceptions import RefreshError
        
        creds_data = database.get_google_creds(guild_id)
        if not creds_data:
            print(f"No Google credentials found for guild {guild_id}.")
            return None, None
            
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
        
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Save the refreshed credentials back to the database
                    database.save_google_creds(guild_id, json.loads(creds.to_json()))
                except RefreshError:
                    print(f"Token expired or revoked for guild {guild_id}. Need re-authentication.")
                    return None, None
            else:
                return None, None

        try:
            service = build("classroom", "v1", credentials=creds)
            drive_service = build("drive", "v3", credentials=creds)
            return service, drive_service
        except HttpError as error:
            print(f"An error occurred creating services for guild {guild_id}: {error}")
            return None, None

    def list_courses(self, guild_id):
        """Lists the user's courses."""
        service, _ = self.get_services(guild_id)
        if not service:
            return []

        try:
            results = service.courses().list(pageSize=10).execute()
            courses = results.get("courses", [])

            if not courses:
                print("No courses found.")
                return []
            
            return courses
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

    def get_course_work(self, guild_id, course_id):
        """Gets course work for a specific course."""
        service, _ = self.get_services(guild_id)
        if not service:
            return []
        
        try:
            results = service.courses().courseWork().list(
                courseId=course_id,
                courseWorkStates=["PUBLISHED", "DRAFT", "DELETED"]
            ).execute()
            course_work = results.get("courseWork", [])
            return course_work
        except HttpError as error:
             print(f"An error occurred retrieving course work: {error}")
             return []

    def get_course_work_materials(self, guild_id, course_id):
        """Gets course work materials for a specific course."""
        service, _ = self.get_services(guild_id)
        if not service:
            return []
        
        try:
            results = service.courses().courseWorkMaterials().list(courseId=course_id).execute()
            materials = results.get("courseWorkMaterial", [])
            return materials
        except HttpError as error:
             print(f"An error occurred retrieving course materials: {error}")
             return []

    def get_student_submissions(self, guild_id, course_id, coursework_id="-", states=None):
        """Gets student submissions for a specific course and coursework."""
        service, _ = self.get_services(guild_id)
        if not service:
            return []
        
        try:
            kwargs = {
                "courseId": course_id,
                "courseWorkId": coursework_id
            }
            if states:
                kwargs["states"] = states
                
            results = service.courses().courseWork().studentSubmissions().list(**kwargs).execute()
            submissions = results.get("studentSubmissions", [])
            return submissions
        except HttpError as error:
             print(f"An error occurred retrieving student submissions: {error}")
             return []

    def get_course_students(self, guild_id, course_id):
        """Gets all students enrolled in a specific course."""
        service, _ = self.get_services(guild_id)
        if not service:
            return []
            
        try:
            results = service.courses().students().list(courseId=course_id).execute()
            students = results.get("students", [])
            return students
        except HttpError as error:
             print(f"An error occurred retrieving students: {error}")
             if error.resp.status == 403:
                 print("Check if the correct scopes are enabled and token.json is updated.")
             return []

    def invite_student(self, guild_id, course_id, email):
        """Invites a student to the course via email."""
        service, _ = self.get_services(guild_id)
        if not service:
            return None

        try:
            invitation = {
                'userId': email,
                'courseId': course_id,
                'role': 'STUDENT'
            }
            invitation = service.invitations().create(body=invitation).execute()
            print(f"Invitation sent to {email}")
            return invitation
        except HttpError as error:
            print(f"An error occurred sending invitation: {error}")
            return None

    def get_drive_file_text(self, guild_id, file_id):
        """Downloads a Google Doc from Drive as plain text."""
        _, drive_service = self.get_services(guild_id)
        if not drive_service:
            return ""
        
        try:
            import io
            from googleapiclient.http import MediaIoBaseDownload
            
            # Export Google Docs to text. If it's a PDF this will fail and we'll catch it.
            request = drive_service.files().export_media(fileId=file_id, mimeType='text/plain')
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            return fh.getvalue().decode('utf-8')
        except HttpError as error:
            print(f"Error fetching or exporting Drive file {file_id}. Note: We currently only support text export for Google Docs. {error}")
            return ""

    def get_auth_url(self, guild_id, user_id=None):
        """Generate the OAuth2 consent URL for a guild owner to link their account."""
        base_url = os.environ.get('APP_URL', 'http://localhost:3000')
        redirect_uri = f"{base_url}/oauth2callback"
        
        from core.oauth_helper import get_google_flow
        flow = get_google_flow(
            self.credentials_path,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        # We pass guild_id (and optionally user_id) as state
        state_str = f"{guild_id}:{user_id}" if user_id else str(guild_id)
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state_str
        )
        return auth_url
        
    def exchange_code(self, guild_id, code, user_id=None):
        """Exchange the auth code for tokens and save to DB."""
        base_url = os.environ.get('APP_URL', 'http://localhost:3000')
        redirect_uri = f"{base_url}/oauth2callback"
        
        from core.oauth_helper import get_google_flow
        flow = get_google_flow(
            self.credentials_path,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        try:
            flow.fetch_token(code=code)
            creds = flow.credentials
            database.save_google_creds(guild_id, json.loads(creds.to_json()), user_id=user_id)
            return True
        except Exception as e:
            print(f"Error exchanging OAuth code for guild {guild_id}: {e}")
            return False
