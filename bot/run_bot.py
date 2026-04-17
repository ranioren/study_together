import os
from dotenv import load_dotenv
# Load environment variables early
load_dotenv()

import discord
from discord.ext import commands
import asyncio
from aiohttp import web

# Import shared managers from core
from core.classroom_manager import ClassroomManager
from core.quiz_manager import QuizManager
from core.database import init_db
from bot.analytics.tracker import load_quiz_scores

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
TOPIC_CYCLE_MINUTES = 8

# Ensure necessary intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class CourseBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.classroom_manager = ClassroomManager()
        self.quiz_manager = QuizManager()
        
        # State tracking
        self.course_progress = {}
        self.processed_submissions = set()
        self.first_poll = True
        self.user_emails = {} 
        self.pending_emails = set()
        self.staged_courses = {} 
        self.pending_cohort_roster = {} 
        self.active_course_cache = {} 
        self.pending_owner_material = {} 
        self.weekly_scores = load_quiz_scores() 
        self.active_quiz_messages = {} 
        self.reported_quiz_winners = set() 
        self.active_quizzes = {} 
        self.quiz_responses = {} 
        self.pre_start_reminder_sent = {} 
        self.active_course = {} # guild_id: course_info
        self.enrollment_end_time = {} # guild_id: datetime
        self.active_cohort_channel_id = {} # guild_id: channel_id

    def get_full_material_text(self, guild_id, course_id, week_index):
        materials = self.classroom_manager.get_course_work_materials(guild_id, course_id)
        if not materials or week_index >= len(materials):
            return "General course material"
            
        mat = materials[week_index]
        text = f"{mat.get('title', '')} - {mat.get('description', '')}\n"
        
        for m in mat.get('materials', []):
            if 'driveFile' in m:
                file_info = m['driveFile'].get('driveFile', {})
                file_id = file_info.get('id')
                file_title = file_info.get('title', 'Document')
                if file_id:
                    print(f"Extracting text from attached Drive file: {file_title}")
                    doc_text = self.classroom_manager.get_drive_file_text(guild_id, file_id)
                    if doc_text:
                        text += f"\n\n--- Document: {file_title} ---\n{doc_text}\n"
        return text

    async def oauth_callback(self, request):
        code = request.query.get("code")
        guild_id_str = request.query.get("state")
        
        if not code or not guild_id_str:
            return web.Response(text="Missing code or guild_id in callback.", status=400)
            
        try:
            guild_id = int(guild_id_str)
            success = self.classroom_manager.exchange_code(guild_id, code)
            if success:
                return web.Response(text="Authentication successful! You can close this window and return to Discord to use !start_course.")
            else:
                return web.Response(text="Failed to exchange OAuth code.", status=500)
        except Exception as e:
            return web.Response(text=f"An error occurred: {e}", status=500)

    async def start_web_server(self):
        app = web.Application()
        app.add_routes([web.get('/oauth2callback', self.oauth_callback)])
        
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        print(f"Web server started on port {port} for OAuth callbacks.")

    async def setup_hook(self):
        # Initialize Database
        init_db()
        print("Database initialized.")
        
        # Load extensions
        # Note: We use the full module path from the root
        extensions = [
            'bot.cogs.course_tasks',
            'bot.cogs.course_commands',
            'bot.interaction.onboarding'
        ]
        
        for extension in extensions:
            try:
                await self.load_extension(extension)
                print(f"Loaded extension: {extension}")
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")
            
        app_info = await self.application_info()
        if app_info.team:
            self.owner_id = app_info.team.owner_id
        else:
            self.owner_id = app_info.owner.id
        print(f"Logged in as {self.user} (ID: {self.user.id}), Owner: {self.owner_id}")
        
        # Start OAuth server
        self.loop.create_task(self.start_web_server())

bot = CourseBot()

if __name__ == '__main__':
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == 'your_bot_token_here':
        print("Error: Please set DISCORD_BOT_TOKEN in your .env file")
    else:
        bot.run(DISCORD_BOT_TOKEN)
