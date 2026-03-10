import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import datetime
import requests
import re
import json
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
        
        # New State for Course Enrollment
        self.active_course = None  # Dict of {id, name, link}
        self.enrollment_end_time = None # datetime (timezone aware)
        self.active_cohort_channel_id = None
        self.pending_cohort_roster = set() # Set of discord user IDs that have fully onboarded
        
        # New State for Topic Timing
        self.topic_start_time = {} # {channel_id: datetime}
        self.reported_topics_15 = set() # {(channel_id, week_index)} - for promotion reminder
        self.reported_topics_20 = set() # {(channel_id, week_index)} - for ask/quiz reminder
        self.reported_topics_70 = set() # {(channel_id, week_index)}
        self.reported_topics_75 = set() # {(channel_id, week_index)} - for owner material DM
        self.reported_topics_80 = set() # {(channel_id, week_index)} - for posting quiz
        self.reported_topics_90 = set() # {(channel_id, week_index)}
        self.reported_topics_90_reminder = set() # {(channel_id, week_index)} - for weekly quiz reminder
        
        # New State for Quizzes
        self.quiz_manager = QuizManager()
        self.pending_owner_material = None # tuple: (course_id, week_index) to track what the owner is replying to
        self.weekly_scores = load_quiz_scores() # {(channel_id, week_index): {user_id: score}}
        self.active_quiz_messages = {} # {message_id: {'correct_index': int, 'channel_id': int, 'week_index': int}}
        self.reported_quiz_winners = set() # {(channel_id, week_index)}
        self.active_quizzes = {} # {(channel_id, week_index): quiz_data}
        self.quiz_responses = {} # {(channel_id, week_index): {q_num: {user_id: opt_index}}}
        
        # New State for Pre-Course Reminder
        self.pre_start_reminder_sent = False

    def get_full_material_text(self, course_id, week_index):
        materials = self.classroom_manager.get_course_work_materials(course_id)
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
                    doc_text = self.classroom_manager.get_drive_file_text(file_id)
                    if doc_text:
                        text += f"\n\n--- Document: {file_title} ---\n{doc_text}\n"
                        
        return text



    async def setup_hook(self):
        # Load Cogs
        await self.load_extension('cogs.course_tasks')
        await self.load_extension('cogs.course_commands')
            
        app_info = await self.application_info()
        self.owner_id = app_info.owner.id
        print(f"Logged in as {self.user} (ID: {self.user.id}), Owner: {self.owner_id}")
        print("Authenticating with Google Classroom...")
        self.classroom_manager.authenticate()
        print("Google Classroom connected!")

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
        "1. You could always check the status of your google classroom courses with `!start_course`.\n"
        "2. To setup a course, please use each topic as cycle time you want to introduce for your course.\n"
        "3. We suggest to run each course with a fast track, to see how it looks and validate data and orchestration.\n\n"
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
            
        if not bot.active_course or not bot.enrollment_end_time:
            return # Reaction to an old message or bot restarted
            
        # 4. Late Enrollment Check (After the Window Closes)
        now = datetime.datetime.now(datetime.timezone.utc)
        if now > bot.enrollment_end_time:
            try:
                await member.send("Hey, too late. Next time!")
            except discord.Forbidden:
                pass
            return

        # Fetch topics (Materials titles) from the course
        materials = bot.classroom_manager.get_course_work_materials(bot.active_course['id'])
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
            embed.add_field(name="Next Steps", value="Do you agree to the course requirements? If so, please type **'I agree'** in this chat.", inline=False)
            
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
        if message.author.id == bot.owner_id and bot.pending_owner_material:
            course_id, week_index = bot.pending_owner_material
            
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
            bot.pending_owner_material = None
            await message.channel.send(f"✅ Material saved for Week {week_index + 1}. I will use this to generate the quizzes!")
            return
            
        # Check for Phase 3.5: User providing their email
        if message.author.id in bot.pending_emails:
            provided_text = message.content.strip()
            
            # Extract email using regex
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', provided_text)
            
            if email_match:
                extracted_email = email_match.group(0).lower()
                bot.user_emails[message.author.id] = extracted_email
                bot.pending_emails.remove(message.author.id)
                bot.pending_cohort_roster.add(message.author.id)
                
                # Since this is a DM, we use the active cohort's guild
                guild = bot.guilds[0]
                guild_id = guild.id if guild else None
                
                # Log email to global tracker
                log_user_email(guild_id, message.author.id, message.author.name, extracted_email)
                
                # Invite to Google Classroom Course
                try:
                    bot.classroom_manager.invite_student(bot.active_course['id'], extracted_email)
                    await message.channel.send(f"📧 I've sent a Google Classroom invitation to **{extracted_email}**. Please check your inbox and accept it!")
                except Exception as e:
                    print(f"Failed to send Classroom invitation: {e}")
                    await message.channel.send(f"⚠️ I couldn't automatically invite you to Google Classroom. Please ask the instructor to add **{extracted_email}** manually.")

                # Add the user to the existing channel
                guild = bot.guilds[0]
                member = guild.get_member(message.author.id)
                cohort_channel = bot.get_channel(bot.active_cohort_channel_id)
                
                if cohort_channel and member:
                    await cohort_channel.set_permissions(member, read_messages=True, send_messages=True)
                    print(f"Added {member.name} to cohort channel")
                    
                    # Phase 4: Send the Welcome Message (Only once per user)
                    embed = discord.Embed(
                        title=f"🎉 Welcome to {bot.active_course['name']}!",
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
                    await message.channel.send(f"✅ You're all set! Check out the <#{cohort_channel.id}> channel.")
                else:
                    await message.channel.send("There was an error finding the channel or your user account. Please contact an admin.")
            else:
                await message.channel.send("That doesn't look like a valid email address. Please reply with your Google email address.")
                return 
                
        elif "i agree" in message.content.lower() and bot.active_course and bot.enrollment_end_time:
            now = datetime.datetime.now(datetime.timezone.utc)
            if now > bot.enrollment_end_time: # Double-check for late responders to the agreement phase
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
