import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import datetime
import requests
import re
import json
import asyncio
from aiohttp import web
from bs4 import BeautifulSoup
from classroom_manager import ClassroomManager
from quiz_manager import QuizManager
from analytics_manager import load_quiz_scores, log_user_email

# Load environment variables
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
# We no longer rely on a static COURSE_ID from .env
# COURSE_ID = os.getenv('GOOGLE_CLASSROOM_COURSE_ID')

# Configuration
TOPIC_CYCLE_MINUTES = 8

# Ensure necessary intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class CourseBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.classroom_manager = ClassroomManager()
        
        # Track weekly progress for channels. Format: {'channel_id': current_week_index}
        self.course_progress = {}
        self.processed_submissions = set()
        self.first_poll = True
        
        # Track email mapping for DMs
        self.user_emails = {} # {discord_id: 'email@gmail.com'}
        self.pending_emails = set() # {discord_id} waiting for email reply
        
        # In-memory session staging and caching
        self.staged_courses = {} # {owner_id: Dict of {id, name, link}}
        self.pending_cohort_roster = {} # {guild_id: Set of discord user IDs}
        self.active_course_cache = {} # Cache instead of querying DB every time for name/id
        self.quiz_manager = QuizManager()
        self.pending_owner_material = {} # {owner_id: (course_id, week_index)}
        self.weekly_scores = load_quiz_scores() # {(channel_id, week_index): {user_id: score}}
        self.active_quiz_messages = {} # {message_id: {'correct_index': int, 'channel_id': int, 'week_index': int}}
        self.reported_quiz_winners = set() # {(channel_id, week_index)}
        self.active_quizzes = {} # {(channel_id, week_index): quiz_data}
        self.quiz_responses = {} # {(channel_id, week_index): {q_num: {user_id: opt_index}}}
        
        # New State for Pre-Course Reminder
        self.pre_start_reminder_sent = {} # {guild_id: bool}

    def get_full_material_text(self, guild_id, course_id, week_index):
        materials = self.classroom_manager.get_course_work_materials(guild_id, course_id)
        if not materials or week_index >= len(materials):
            return "General course material"
            
        mat = materials[week_index]
        text = f"{mat.get('title', '')} - {mat.get('description', '')}\n"
        
        # Check for attached Drive files
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
        import database
        database.init_db()
        print("Database initialized.")
        
        # Load Cogs
        await self.load_extension('cogs.course_tasks')
        await self.load_extension('cogs.course_commands')
            
        app_info = await self.application_info()
        if app_info.team:
            self.owner_id = app_info.team.owner_id
        else:
            self.owner_id = app_info.owner.id
        print(f"Logged in as {self.user} (ID: {self.user.id}), Owner: {self.owner_id}")
        
        # Start the background web server for OAuth
        self.loop.create_task(self.start_web_server())

bot = CourseBot()


@bot.event
async def on_guild_join(guild):
    import csv
    
    server_id = guild.id
    analytics_file = f"analytics_{server_id}.csv"
    users_file = f"users_{server_id}.csv"
    
    try:
        # Only create if they don't exist, we don't want to overwrite if re-invited
        if not os.path.exists(analytics_file):
            with open(analytics_file, "w", newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "UserID", "EventType", "CourseName", "Detail", "IsCorrect"])
            print(f"Created {analytics_file} for new guild {guild.name}.")
        
        if not os.path.exists(users_file):
            with open(users_file, "w", newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["UserID", "Username", "Email"])
            print(f"Created {users_file} for new guild {guild.name}.")
    except Exception as e:
        print(f"Error creating CSVs for guild {guild.name}: {e}")

    welcome_message = (
        f"**Welcome to Study Together!** Thanks for adding me to **{guild.name}**.\n\n"
        "Here is what you can do to get started:\n"
        "1. Please go to any channel where you can manage course admin tasks and type `!setup_admin` to create a private admin channel.\n"
        "2. Inside the private `#course-admin` channel, type `!auth_google` to link your Google Classroom account.\n"
        "3. Once linked, you can use `!start_course` in `#course-admin` to choose a course and prepare it for announcements.\n\n"
        "I've also initialized dedicated analytics tracking just for your server!"
    )

    owner = guild.owner
    if owner:
        try:
            await owner.send(welcome_message)
            print(f"Sent welcome DM to owner {owner.name} of guild {guild.name}")
        except discord.Forbidden:
            print(f"Could not send DM to {owner.name}. They might have DMs disabled.")


@bot.event
async def on_raw_reaction_add(payload):
    """Phase 2: Listen for reactions and send DM."""
    # Ignore reactions from the bot itself
    if payload.user_id == bot.user.id:
        return

    # Check if the reaction is the join checkmark
    if str(payload.emoji) == "✅":
        guild = bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        member = guild.get_member(payload.user_id)
        if not member:
            return
            
        if not bot.active_course.get(guild.id) or not bot.enrollment_end_time.get(guild.id):
            return # Reaction to an old message or bot restarted
            
        # 4. Late Enrollment Check (After the Window Closes)
        now = datetime.datetime.now(datetime.timezone.utc)
        if now > bot.enrollment_end_time[guild.id]:
            try:
                await member.send("Hey, too late. Next time!")
            except discord.Forbidden:
                pass
            return

        # Fetch topics (Materials titles) from the course
        materials = bot.classroom_manager.get_course_work_materials(bot.active_course[guild.id]['id'])
        topics = [m.get('title', 'Untitled') for m in materials] if materials else ["No topics found."]
        topics_list = "\n".join([f"- {t}" for t in topics])

        try:
            # Send DM
            embed = discord.Embed(
                title="🎓 Welcome to the Course Onboarding!",
                description="We're excited to have you join. Here is the syllabus we will cover:",
                color=discord.Color.green()
            )
            embed.add_field(name="Course Topics", value=topics_list, inline=False)
            embed.add_field(name="Next Steps", value=f"Do you agree to the course requirements for **{guild.name}**? If so, please type **'I agree'** in this chat.", inline=False)
            
            await member.send(embed=embed)
            print(f"Sent onboarding DM to {member.name}")
        except discord.Forbidden:
            print(f"Could not send DM to {member.name}. They might have DMs disabled.")

@bot.event
async def on_message(message):
    """Phases 3 & 4: Listen for 'I agree' in DMs and add to/create cohort channel."""
    # Process commands first so this doesn't block !announce_course
    await bot.process_commands(message)
    
    # Ignore bot messages
    if message.author == bot.user:
        return
        
    if isinstance(message.channel, discord.DMChannel):
        
        # Check if we are waiting for material from the owner
        if message.author.id == bot.owner_id and bot.pending_owner_material.get(bot.owner_id):
            course_id, week_index = bot.pending_owner_material[bot.owner_id]
            
            content_to_save = message.content.strip()
            
            # Check for attachments (.txt, .md)
            if message.attachments:
                for attachment in message.attachments:
                    if attachment.filename.endswith(('.txt', '.md', '.csv')):
                        try:
                            file_bytes = await attachment.read()
                            content_to_save = file_bytes.decode('utf-8')
                            await message.channel.send(f"📄 Read text from attachment: `{attachment.filename}`")
                            break
                        except Exception as e:
                            await message.channel.send(f"Could not read attachment: {e}")
            
            # Check if it's a URL
            elif content_to_save.startswith("http://") or content_to_save.startswith("https://"):
                url = content_to_save.split()[0] # Get just the url if there's trailing text
                await message.channel.send(f"🔗 Attempting to extract text from URL: {url}")
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    # Extract text and remove excessive whitespace
                    extracted_text = soup.get_text(separator=' ', strip=True)
                    content_to_save = extracted_text
                    await message.channel.send("✅ Successfully scraped website text!")
                except Exception as e:
                    await message.channel.send(f"⚠️ Failed to scrape URL: {e}. I will use the raw URL text instead, but it might not work well.")
            
            if not content_to_save:
                content_to_save = "General course material"
                
            bot.quiz_manager.save_material(course_id, week_index, content_to_save)
            del bot.pending_owner_material[bot.owner_id]
            await message.channel.send(f"✅ Material saved for Week {week_index + 1}. I will use this to generate the quizzes!")
            return
            
        # Check for Phase 3.5: User providing their email
        if message.author.id in bot.pending_emails:
            # We must assume the guild context since it's a DM and the user responded
            # If the user is only in one active course across all guilds, we can find it.
            target_guild_id = None
            for guild in bot.guilds:
                if guild.id in bot.active_course and guild.id in bot.enrollment_end_time:
                    target_guild_id = guild.id
                    break
                    
            if not target_guild_id:
                await message.channel.send("I couldn't find an active course enrollment for you. Please check with an admin.")
                bot.pending_emails.remove(message.author.id)
                return
                
            provided_text = message.content.strip()
            
            # Extract email using regex
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', provided_text)
            
            if email_match:
                extracted_email = email_match.group(0).lower()
                bot.user_emails[message.author.id] = extracted_email
                bot.pending_emails.remove(message.author.id)
                if target_guild_id not in bot.pending_cohort_roster:
                    bot.pending_cohort_roster[target_guild_id] = set()
                bot.pending_cohort_roster[target_guild_id].add(message.author.id)
                
                # Log email to global tracker
                log_user_email(target_guild_id, message.author.id, message.author.name, extracted_email)
                
                # Invite to Google Classroom Course
                try:
                    bot.classroom_manager.invite_student(bot.active_course[target_guild_id]['id'], extracted_email)
                    await message.channel.send(f"📧 I've sent a Google Classroom invitation to **{extracted_email}**. Please check your inbox and accept it!")
                except Exception as e:
                    print(f"Failed to send Classroom invitation: {e}")
                    await message.channel.send(f"⚠️ I couldn't automatically invite you to Google Classroom. Please ask the instructor to add **{extracted_email}** manually.")

                # Add the user to the existing channel
                guild = bot.get_guild(target_guild_id)
                if guild:
                    member = guild.get_member(message.author.id)
                    cohort_channel_id = bot.active_cohort_channel_id.get(target_guild_id)
                    cohort_channel = bot.get_channel(cohort_channel_id) if cohort_channel_id else None
                    
                    if cohort_channel and member:
                        await cohort_channel.set_permissions(member, read_messages=True, send_messages=True)
                        print(f"Added {member.name} to cohort channel in {guild.name}")
                        
                        # Phase 4: Send the Welcome Message (Only once per user)
                        embed = discord.Embed(
                            title=f"🎉 Welcome to {bot.active_course[target_guild_id]['name']}!",
                            description=f"Hello {member.mention}! This is the private cohort channel.",
                            color=discord.Color.gold()
                        )
                        
                        schedule_text = (
                            f"• **New Material**: Dropped every {TOPIC_CYCLE_MINUTES} minutes in this channel.\n"
                            "• **Weekly Quiz**: A 5-question quiz will be posted near the end of the week.\n"
                            "• **Practice**: You can DM me `!quiz` at any time to get a practice question based on the current week's material!\n"
                            "• **Questions**: Use `!ask <your question>` in this channel or via DM to get AI-powered answers based on the material."
                        )
                        embed.add_field(name="Course Schedule & Features", value=schedule_text, inline=False)
                        embed.add_field(name="Introduce Yourself", value="Please tell us a bit about yourself and why you're taking this course!", inline=False)
                        
                        await cohort_channel.send(embed=embed)
                        await message.channel.send(f"✅ You're all set! Check out the <#{cohort_channel.id}> channel in **{guild.name}**.")
                    else:
                        await message.channel.send("There was an error finding the channel or your user account. Please contact an admin.")
                else:
                    await message.channel.send("Could not find the server. Please contact an admin.")
            else:
                await message.channel.send("That doesn't look like a valid email address. Please reply with your Google email address.")
                return 
                
        elif "i agree" in message.content.lower():
            target_guild_id = None
            for guild in bot.guilds:
                if guild.id in bot.active_course and guild.id in bot.enrollment_end_time:
                    target_guild_id = guild.id
                    break
                    
            if not target_guild_id:
                return
                
            now = datetime.datetime.now(datetime.timezone.utc)
            if now > bot.enrollment_end_time[target_guild_id]: # Double-check for late responders to the agreement phase
                await message.channel.send("Hey, too late. Next time!")
                return
            
            bot.pending_emails.add(message.author.id)
            await message.channel.send("Great! Before I add you to the course channel, please reply with the exact **Google Account Email Address** (must be a Google/Gmail account) you use for Google Classroom so I can track your submissions and notify you.")
            return



if __name__ == '__main__':
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == 'your_bot_token_here':
        print("Error: Please set DISCORD_BOT_TOKEN in your .env file")
    else:
        bot.run(DISCORD_BOT_TOKEN)
