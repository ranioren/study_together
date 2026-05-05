import discord
from discord.ext import commands
import datetime
import os
import io
import asyncio
from core import database
from PIL import Image, ImageDraw, ImageFont
from bot.analytics.tracker import log_analytics, check_streaks

TOPIC_CYCLE_MINUTES = 8

def generate_timeline_text(cycle_minutes):
    cycle_seconds = cycle_minutes * 60
    events = [
        {"name": "Pre-Course Reminder (General)", "time_str": f"T-{int((cycle_seconds*0.05)//60)}:{(int(cycle_seconds*0.05)%60):02d}", "emoji": "⏰"},
        {"name": "Enrollment Closes & Course Starts", "time_str": "T+0:00", "emoji": "🏁"},
        {"name": "Topic Material Drops", "time_str": "T+0:00", "emoji": "📚"},
        {"name": "Promotion Reminder (DM)", "time_str": f"T+{int((cycle_seconds*0.15)//60)}:{(int(cycle_seconds*0.15)%60):02d}", "emoji": "📣"},
        {"name": "Manager Report (70%)", "time_str": f"T+{int((cycle_seconds*0.70)//60)}:{(int(cycle_seconds*0.70)%60):02d}", "emoji": "📊"},
        {"name": "Prep Next Week Materials", "time_str": f"T+{int((cycle_seconds*0.75)//60)}:{(int(cycle_seconds*0.75)%60):02d}", "emoji": "⚙️"},
        {"name": "Weekly Quiz Posted", "time_str": f"T+{int((cycle_seconds*0.80)//60)}:{(int(cycle_seconds*0.80)%60):02d}", "emoji": "🧠"},
        {"name": "Manager Report & Quiz Win (90%)", "time_str": f"T+{int((cycle_seconds*0.90)//60)}:{(int(cycle_seconds*0.90)%60):02d}", "emoji": "🏆"},
        {"name": "Next Cycle / Topic Begins", "time_str": f"T+{int(cycle_minutes)}:00", "emoji": "🔄"}
    ]

    lines = [f"**📅 The Course Rhythm ({cycle_minutes}-Minute Cycle)**"]
    for i, ev in enumerate(events):
        lines.append(f"{ev['emoji']} **{ev['time_str']}** - {ev['name']}")
        if i < len(events) - 1:
            lines.append(" ┃")
    return "\n".join(lines)

def generate_timeline_image(cycle_minutes):
    cycle_seconds = cycle_minutes * 60
    
    events = [
        {"name": "Pre-Course Reminder", "time_str": f"T-{int((cycle_seconds*0.05)//60)}:{(int(cycle_seconds*0.05)%60):02d}"},
        {"name": "Course & Topic Starts", "time_str": "T+0:00"},
        {"name": "Promotion Reminder", "time_str": f"T+{int((cycle_seconds*0.15)//60)}:{(int(cycle_seconds*0.15)%60):02d}"},
        {"name": "Manager Report (70%)", "time_str": f"T+{int((cycle_seconds*0.70)//60)}:{(int(cycle_seconds*0.70)%60):02d}"},
        {"name": "Prep Next Week", "time_str": f"T+{int((cycle_seconds*0.75)//60)}:{(int(cycle_seconds*0.75)%60):02d}"},
        {"name": "Weekly Quiz Posted", "time_str": f"T+{int((cycle_seconds*0.80)//60)}:{(int(cycle_seconds*0.80)%60):02d}"},
        {"name": "Quiz Win & Final Report", "time_str": f"T+{int((cycle_seconds*0.90)//60)}:{(int(cycle_seconds*0.90)%60):02d}"},
        {"name": "Next Cycle Begins", "time_str": f"T+{int(cycle_minutes)}:00"}
    ]
    
    width = 800
    height = 120 + len(events) * 60
    
    img = Image.new('RGB', (width, height), color=(43, 45, 49))
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("arial.ttf", 28)
        font_text = ImageFont.truetype("arial.ttf", 22)
        font_time = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font_title = font_text = font_time = ImageFont.load_default()
        
    title_text = f"Course Rhythm & Schedule ({cycle_minutes}-Minute Cycle)"
    draw.text((30, 30), title_text, font=font_title, fill=(255, 255, 255))
    
    start_y = 100
    end_y = height - 50
    draw.line([(100, start_y), (100, end_y)], fill=(114, 137, 218), width=6)
    
    for i, ev in enumerate(events):
        y = start_y + (i * 60)
        draw.ellipse([(90, y - 10), (110, y + 10)], fill=(88, 101, 242), outline=(255, 255, 255), width=2)
        draw.text((130, y - 12), ev['time_str'], font=font_time, fill=(153, 170, 181))
        draw.text((230, y - 14), ev['name'], font=font_text, fill=(255, 255, 255))
        
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

TOPIC_CYCLE_MINUTES = 8

class CourseCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def setup_admin(self, ctx):
        """Creates a private channel for course administration and setup."""
        if ctx.guild is None:
            await ctx.send("This command must be run in a server.")
            return
            
        if not ctx.author.guild_permissions.administrator and ctx.author.id != self.bot.owner_id:
            await ctx.send("You need Administrator permissions to run this command.")
            return

        existing_channel = discord.utils.get(ctx.guild.text_channels, name="course-admin")
        if existing_channel:
            await ctx.send(f"An admin channel already exists: {existing_channel.mention}")
            return

        try:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            admin_channel = await ctx.guild.create_text_channel(
                name="course-admin",
                overwrites=overwrites,
                reason="Created private channel for course administration."
            )
            
            embed = discord.Embed(
                title="🔒 Course Administration",
                description=(
                    "Welcome to your private course administration channel.\n\n"
                    "Since setup commands like `!start_course` display sensitive server information and course lists, "
                    "it is highly recommended to run them here.\n\n"
                    "**Next Steps:**\n"
                    "1. Run `!auth_google` to link your Google Classroom account.\n"
                    "2. Run `!start_course` to choose a course and prepare it for announcements."
                ),
                color=discord.Color.dark_theme()
            )
            await admin_channel.send(embed=embed)
            await ctx.send(f"✅ Created private admin channel: {admin_channel.mention}")
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to create channels in this server.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command()
    async def auth_google(self, ctx):
        """Send a DM to the server owner to authorize Google Classroom."""
        if ctx.guild is None:
            await ctx.send("This command must be run in a server.")
            return
            
        if not ctx.author.guild_permissions.administrator and ctx.author.id != self.bot.owner_id:
            await ctx.send("You need Administrator permissions to run this command.")
            return
            
        try:
            auth_url = self.bot.classroom_manager.get_auth_url(ctx.guild.id, user_id=ctx.author.id)
            await ctx.author.send(
                f"**Google Classroom Setup for {ctx.guild.name}**\n"
                "To link your server to Google Classroom, please click the link below to authorize the bot:\n"
                f"<{auth_url}>\n\n"
                "Once authorized, you can run `!start_course` in your server's `#course-admin` channel to keep it private."
            )
            
            warning = ""
            if ctx.channel.name != "course-admin":
                warning = " *(Tip: It's safer to run setup commands like `!start_course` in a private channel like `#course-admin`)*"
                
            await ctx.send(f"I've sent you a DM with instructions on how to authenticate Google Classroom.{warning}")
        except FileNotFoundError:
            await ctx.send("The bot administrator has not configured Google OAuth credentials yet.")
        except discord.Forbidden:
            await ctx.send("I couldn't send you a DM. Please check your privacy settings.")

    @commands.command()
    async def start_course(self, ctx):
        """Admin command to list courses and select an active one."""
        if ctx.guild is None:
            await ctx.send("With multi-tenant setup, `!start_course` must be run in your server, not a DM.")
            return
            
        is_authorized = False
        if ctx.author.id == self.bot.owner_id:
            is_authorized = True
        elif hasattr(ctx.author, 'guild_permissions') and ctx.author.guild_permissions.administrator:
            is_authorized = True

        if not is_authorized:
            await ctx.send("You do not have permission to use this command.")
            return

        courses = self.bot.classroom_manager.list_courses(ctx.guild.id)
        if not courses:
            await ctx.send("No courses found or not authenticated. Run `!auth_google` first.")
            return

        warning = ""
        if ctx.channel.name != "course-admin":
             warning = "⚠️ **Warning: You are running this in a public channel.** Your course list is visible to all members here.\n\n"

        embed = discord.Embed(
            title="Available Courses", 
            description=f"{warning}Reply with the number of the course you want to start.", 
            color=discord.Color.blue()
        )
        for idx, c in enumerate(courses):
            embed.add_field(name=f"{idx + 1}. {c['name']}", value=f"ID: {c['id']}", inline=False)
            
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            selection_idx = int(msg.content) - 1
            if 0 <= selection_idx < len(courses):
                selected_course = courses[selection_idx]
                
                # Active course is saved to the bot cache (db persistence happens during announce)
                self.bot.active_course_cache[ctx.guild.id] = selected_course
                scope_msg = "Course data successfully fetched. Use `!announce_course` in #general to begin enrollment!"
                
                course_id = selected_course['id']
                guild_id = ctx.guild.id
                try:
                    students = self.bot.classroom_manager.get_course_students(guild_id, course_id)
                    total_students = len(students) if students else 0
                    assignments = self.bot.classroom_manager.get_course_work(guild_id, course_id)
                    total_assignments = len(assignments) if assignments else 0
                    materials = self.bot.classroom_manager.get_course_work_materials(guild_id, course_id)
                    total_weeks = len(materials) if materials else 0
                except Exception as e:
                    total_students, total_assignments, total_weeks = 0, 0, 0
                    print(f"Stats fetch error: {e}")

                confirm_embed = discord.Embed(
                    title=f"✅ Course Selected: {selected_course['name']}",
                    description=scope_msg,
                    color=discord.Color.green()
                )
                
                confirm_embed.add_field(name="Classroom Stats", value=f"**Students Enrolled:** {total_students}\n**Total Weeks/Topics:** {total_weeks}\n**Total Assignments:** {total_assignments}", inline=False)
                
                timeline_text = generate_timeline_text(TOPIC_CYCLE_MINUTES)
                confirm_embed.add_field(name="Timeline Preview", value=timeline_text, inline=False)
                
                image_bytes = generate_timeline_image(TOPIC_CYCLE_MINUTES)
                file = discord.File(fp=image_bytes, filename="timeline.png")
                confirm_embed.set_image(url="attachment://timeline.png")

                await ctx.send(embed=confirm_embed, file=file)
            else:
                await ctx.send("Invalid selection number.")
        except asyncio.TimeoutError:
             await ctx.send("Timed out waiting for a response.")
        except ValueError:
             await ctx.send("Please enter a valid number.")
        except Exception as e:
             import traceback
             traceback.print_exc()
             await ctx.send(f"An error occurred: {e}")

    @commands.command()
    async def announce_course(self, ctx):
        """Fetch and announce the course, creating the channel immediately."""
        if ctx.guild is None:
            await ctx.send("❌ This command must be run inside a server channel, not in a Direct Message.")
            return
            
        # Pull from memory staged courses first
        staged = getattr(self.bot, 'staged_courses', {}).get(ctx.author.id)
        
        # Check if already active in DB
        db_config = database.get_server_config(ctx.guild.id)
        
        if staged:
            course = staged
            database.set_server_active_course(ctx.guild.id, course['id'], course['name'], course.get('alternateLink', ''))
            # Move to cache
            self.bot.active_course_cache[ctx.guild.id] = course
            # Clear stage
            del self.bot.staged_courses[ctx.author.id]
        elif db_config and db_config['active_course_id']:
            course = self.bot.active_course_cache.get(ctx.guild.id)
            if not course:
                 # Fallback to recreate a partial course object from DB if cache missed
                 course = {'id': db_config['active_course_id'], 'name': db_config['active_course_name'], 'alternateLink': db_config['active_course_link']}
                 self.bot.active_course_cache[ctx.guild.id] = course
        else:
            await ctx.send("No active course selected for this server! Use `!start_course` first.")
            return

        embed = discord.Embed(
            title=f"📚 Welcome to {course['name']}!",
            description="We are starting a new cohort soon. Here is a preview of the topics!",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Classroom Link", value=f"[Go to Course]({course.get('alternateLink')})", inline=False)
        
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
        
        await ctx.send("*React with ✅ to join the course and receive instructions!*")
        
        now = datetime.datetime.now(datetime.timezone.utc)
        enroll_end = now + datetime.timedelta(minutes=1, seconds=30)
        database.update_enrollment_end_time(ctx.guild.id, enroll_end)
        
        raw_course_name = course['name']
        safe_course_name = raw_course_name.lower().replace(" ", "-")
        channel_name = f"{safe_course_name}-{now.strftime('%b-%Y').lower()}"

        guild = ctx.guild
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            cohort_channel = await guild.create_text_channel(
                name=channel_name, 
                overwrites=overwrites,
                reason=f"Cohort channel created from announcement"
            )
            database.set_cohort_channel(ctx.guild.id, cohort_channel.id)
            print(f"Created new cohort channel {channel_name} for Server {guild.name}")
            
            welcome_embed = discord.Embed(
                title=f"🏫 Welcome to {course['name']}!",
                description="This is the main channel for this cohort. Here is how this course works:",
                color=discord.Color.blue()
            )
            
            schedule_info = (
                f"• **Weekly Material**: New topics drop every {TOPIC_CYCLE_MINUTES} minutes.\n"
                "• **Quizzes**: A 5-question quiz will be posted near the end of the week.\n"
                "• **Practice**: You can use `!quiz` in this channel or via DM to get a practice question anytime!\n"
                "• **Questions**: Use `!ask <your question>` in this channel or via DM to get AI-powered answers based on the material."
            )
            welcome_embed.add_field(name="Course Schedule & Features", value=schedule_info, inline=False)
            welcome_embed.set_footer(text="Wait for the enrollment period to end, and the first week will begin!")
            
            await cohort_channel.send(embed=welcome_embed)
            
            timeline_text = generate_timeline_text(TOPIC_CYCLE_MINUTES)
            timeline_embed = discord.Embed(
                title="⏱️ Course Schedule Rhythm",
                description=f"Here is a breakdown of what happens in each {TOPIC_CYCLE_MINUTES}-minute cycle:\n\n{timeline_text}",
                color=discord.Color.blue()
            )
            await cohort_channel.send(embed=timeline_embed)
            
            await ctx.send(f"Channel {cohort_channel.mention} created! Enrollment window closes in 1.5 minutes.")
            
        except discord.Forbidden:
             await ctx.send("I don't have permission to modify channels in the server! Please contact an admin.")
             print(f"Error: Missing permissions to modify channels in {guild.name}")

    @commands.command()
    async def quiz(self, ctx):
        """Phase 3 RAG: Allows a student to request a practice question in DMs"""
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Please send me `!quiz` in a Direct Message to practice!")
            return
            
        is_owner = (ctx.author.id == self.bot.owner_id)
        
        # In DM context, find a guild where this user is enrolled
        target_guild_id = None
        for guild_id, roster in self.bot.pending_cohort_roster.items():
            if ctx.author.id in roster:
                target_guild_id = guild_id
                break
                
        if not target_guild_id and is_owner:
            # If owner, fallback to first active course
            if self.bot.active_course:
                target_guild_id = list(self.bot.active_course.keys())[0]

        if not target_guild_id or (not self.bot.active_course.get(target_guild_id) and not database.get_server_config(target_guild_id)):
            await ctx.send("You must be fully enrolled in an active course to request practice quizzes.")
            return
            
        course = self.bot.active_course.get(target_guild_id)
        if not course:
             db_config = database.get_server_config(target_guild_id)
             if db_config:
                 course = {'id': db_config['active_course_id'], 'name': db_config['active_course_name'], 'alternateLink': db_config['active_course_link']}
                 self.bot.active_course_cache[target_guild_id] = course
             else:
                 return # Shouldn't happen based on above check
                 
        course_id = course['id']
        
        current_week_index = 0
        cohort_ch_id = self.bot.active_cohort_channel_id.get(target_guild_id)
        if cohort_ch_id and cohort_ch_id in self.bot.course_progress:
            current_week_index = max(0, self.bot.course_progress[cohort_ch_id] - 1)
            
        await ctx.send("🤖 *Thinking of a good question based on this week's material...*")
        
        fallback_text = self.bot.get_full_material_text(target_guild_id, course_id, current_week_index)
             
        material_text = self.bot.quiz_manager.get_material(course_id, current_week_index, fallback_text=fallback_text)
        
        import asyncio
        loop = asyncio.get_running_loop()
        practice_data = await loop.run_in_executor(None, self.bot.quiz_manager.generate_practice_question, material_text)
        
        if not practice_data:
            await ctx.send("Sorry, I had trouble generating a question right now. Try again shortly!")
            return
            
        q_embed = discord.Embed(
            title="📝 Practice Question",
            description=practice_data['question'],
            color=discord.Color.green()
        )
        
        view = discord.ui.View(timeout=120)
        
        async def make_dm_callback(opt_index, correct_idx):
            async def btn_callback(interaction: discord.Interaction):
                is_correct = (opt_index == correct_idx)
                ch_name = ctx.channel.name if hasattr(ctx.channel, "name") else "DM"
                guild_id = self.bot.guilds[0].id if self.bot.guilds else None
                log_analytics(guild_id, interaction.user.id, "PracticeQuiz", ch_name, "N/A", is_correct)
                await check_streaks(guild_id, ctx.channel, interaction.user.id)
                if is_correct:
                    await interaction.response.send_message("✅ **Correct!** Great job. Use `!quiz` to practice another one.", ephemeral=False)
                else:
                     correct_label = chr(65 + correct_idx)
                     await interaction.response.send_message(f"❌ **Incorrect.** The correct answer was **{correct_label}**. Keep practicing with `!quiz`!", ephemeral=False)
                    
                for item in view.children:
                    item.disabled = True
                await interaction.message.edit(view=view)
                
            return btn_callback
            
        labels = ["A", "B", "C", "D"]
        for opt_idx, opt_text in enumerate(practice_data['options']):
             btn_label = f"{labels[opt_idx]}: {opt_text}"
             if len(btn_label) > 80:
                 btn_label = btn_label[:77] + "..."
                 
             btn = discord.ui.Button(label=btn_label, style=discord.ButtonStyle.secondary, custom_id=f"dmquiz_{opt_idx}")
             btn.callback = await make_dm_callback(opt_idx, practice_data['correct_index'])
             view.add_item(btn)
             
        await ctx.send(embed=q_embed, view=view)

    @commands.command()
    async def ask(self, ctx, *, question: str):
        """Phase 3 RAG: Ask a question about the current weekly material."""
        is_owner = (ctx.author.id == self.bot.owner_id)
        
        current_week_index = 0
        target_guild_id = None
        
        if isinstance(ctx.channel, discord.DMChannel):
            # Try to resolve guild from roster
            for guild_id, roster in self.bot.pending_cohort_roster.items():
                if ctx.author.id in roster:
                    target_guild_id = guild_id
                    break
                    
            if not target_guild_id and is_owner:
                if self.bot.active_course:
                    target_guild_id = list(self.bot.active_course.keys())[0]
                    
            if not target_guild_id:
                await ctx.send("You must be fully enrolled in an active course to ask questions via DM.")
                return
            
            cohort_ch_id = self.bot.active_cohort_channel_id.get(target_guild_id)
            if cohort_ch_id and cohort_ch_id in self.bot.course_progress:
                current_week_index = max(0, self.bot.course_progress[cohort_ch_id] - 1)
        else:
            target_guild_id = ctx.guild.id
            if ctx.channel.id in self.bot.course_progress:
                current_week_index = max(0, self.bot.course_progress[ctx.channel.id] - 1)
            else:
                 if is_owner:
                     cohort_ch_id = self.bot.active_cohort_channel_id.get(target_guild_id)
                     if cohort_ch_id and cohort_ch_id in self.bot.course_progress:
                         current_week_index = max(0, self.bot.course_progress[cohort_ch_id] - 1)
                 else:
                     await ctx.send("Please use `!ask` inside your cohort channel or in a Direct Message with me.")
                     return
                     
        if not target_guild_id or (not self.bot.active_course.get(target_guild_id) and not database.get_server_config(target_guild_id)):
            await ctx.send("No active course is running right now to ask questions about.")
            return
            
        course = self.bot.active_course.get(target_guild_id)
        if not course:
             db_config = database.get_server_config(target_guild_id)
             course = {'id': db_config['active_course_id'], 'name': db_config['active_course_name'], 'alternateLink': db_config['active_course_link']}
             self.bot.active_course_cache[target_guild_id] = course
             
        course_id = course['id']
                 
        thinking_msg = await ctx.send("🤔 *Reading the material to find your answer...*")
        
        fallback_text = self.bot.get_full_material_text(target_guild_id, course_id, current_week_index)
             
        material_text = self.bot.quiz_manager.get_material(course_id, current_week_index, fallback_text=fallback_text)
        
        import asyncio
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(None, self.bot.quiz_manager.answer_question, question, material_text)
        
        ch_name = ctx.channel.name if hasattr(ctx.channel, "name") else "DM"
        guild_id = self.bot.guilds[0].id if self.bot.guilds else None
        log_analytics(guild_id, ctx.author.id, "AskQuestion", ch_name, "N/A", "")
        await check_streaks(guild_id, ctx.channel, ctx.author.id)
        
        embed = discord.Embed(
            title="Question Answered",
            description=answer,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Based on Week {current_week_index + 1} material.")
        
        await thinking_msg.edit(content=None, embed=embed)

    @commands.command()
    async def report(self, ctx):
        """Admin command to get an on-demand course status report."""
        if ctx.guild is None:
            await ctx.send("❌ This command must be run inside a server channel, not in a Direct Message.")
            return
            
        is_authorized = False
        if ctx.author.id == self.bot.owner_id:
            is_authorized = True
        elif hasattr(ctx.author, 'guild_permissions') and ctx.author.guild_permissions.administrator:
            is_authorized = True

        if not is_authorized:
            await ctx.send("You do not have permission to use this command.")
            return

        guild_id = ctx.guild.id
        db_config = database.get_server_config(guild_id)
        if not db_config or not db_config['active_course_id']:
            await ctx.send("No active course selected for this server! Use `!start_course` first.")
            return

        course_id = db_config['active_course_id']
        course_name = db_config['active_course_name']
        
        msg = await ctx.send("📊 *Generating status report...*")
        
        try:
            students = self.bot.classroom_manager.get_course_students(guild_id, course_id)
            total_students = len(students) if students else 0
            assignments = self.bot.classroom_manager.get_course_work(guild_id, course_id)
            
            embed = discord.Embed(
                title=f"📊 Course Report: {course_name}",
                description=f"Current status of the course enrollment and participation.",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            
            roster = self.bot.pending_cohort_roster.get(guild_id, set())
            
            embed.add_field(name="Total Enrolled Students", value=str(total_students), inline=True)
            embed.add_field(name="Onboarded via Discord", value=str(len(roster)), inline=True)
            
            cohort_ch_id = self.bot.active_cohort_channel_id.get(guild_id)
            
            if cohort_ch_id and cohort_ch_id in self.bot.course_progress:
                current_week = self.bot.course_progress[cohort_ch_id]
                embed.add_field(name="Current Week", value=f"Week {current_week}", inline=True)
            
            if assignments:
                assignment_info = ""
                for assign in assignments[:3]:
                    submissions = self.bot.classroom_manager.get_student_submissions(guild_id, course_id, coursework_id=assign['id'], states=["TURNED_IN", "RETURNED"])
                    count = len(submissions) if submissions else 0
                    assignment_info += f"• **{assign['title']}**: {count}/{total_students} turned in\n"
                
                embed.add_field(name="Recent Assignments", value=assignment_info or "No assignments found.", inline=False)

            if cohort_ch_id and (cohort_ch_id, current_week - 1) in self.bot.weekly_scores:
                quiz_results = self.bot.weekly_scores[(cohort_ch_id, current_week - 1)]
                if quiz_results:
                    sorted_scores = sorted(quiz_results.items(), key=lambda x: x[1], reverse=True)
                    quiz_info = "\n".join([f"• <@{uid}>: {score} points" for uid, score in sorted_scores[:5]])
                    embed.add_field(name=f"Last Week's Quiz Results (Week {current_week - 1})", value=quiz_info, inline=False)
            
            await msg.edit(content=None, embed=embed)
            
        except Exception as e:
            await msg.edit(content=f"Error generating report: {e}")

    @commands.command(aliases=['engage'])
    async def engagement(self, ctx, member: discord.Member = None):
        """Admin command to view engagement analytics for a specific user or everyone."""
        is_authorized = False
        if ctx.author.id == self.bot.owner_id:
            is_authorized = True
        elif hasattr(ctx.author, 'guild_permissions') and ctx.author.guild_permissions.administrator:
            is_authorized = True

        if not is_authorized:
            await ctx.send("You do not have permission to use this command.")
            return

        import csv
        guild_id = ctx.guild.id if ctx.guild else None
        if not guild_id:
            analytics_file = "analytics.csv"
        else:
            analytics_file = f"analytics_{guild_id}.csv"
            
        if not os.path.exists(analytics_file):
            await ctx.send("No analytics data found for this server yet.")
            return

        stats = {}
        target_users = [str(member.id)] if member else None

        try:
            with open(analytics_file, "r", encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uid = row.get("UserID", "")
                    if not uid: continue
                    if target_users and uid not in target_users:
                        continue
                    
                    if uid not in stats:
                        stats[uid] = {'WeeklyQuiz': {'total':0, 'correct':0}, 'PracticeQuiz': {'total':0, 'correct':0}, 'AskQuestion': 0}
                    
                    ev = row.get("EventType", "")
                    if ev in ['WeeklyQuiz', 'PracticeQuiz']:
                        stats[uid][ev]['total'] += 1
                        if row.get("IsCorrect", "") == "True":
                            stats[uid][ev]['correct'] += 1
                    elif ev == 'AskQuestion':
                        stats[uid][ev] += 1
                        
            embed = discord.Embed(title="📊 Engagement Analytics", color=discord.Color.purple())
            
            if not stats:
                embed.description = "No engagement data found for the specified criteria."
                await ctx.send(embed=embed)
                return
                
            if member:
                u_stats = stats.get(str(member.id))
                if u_stats:
                    desc = (
                        f"**Weekly Quizzes**: Answered: {u_stats['WeeklyQuiz']['total']}, Correct: {u_stats['WeeklyQuiz']['correct']}\n"
                        f"**Practice Quizzes**: Answered: {u_stats['PracticeQuiz']['total']}, Correct: {u_stats['PracticeQuiz']['correct']}\n"
                        f"**Questions Asked**: {u_stats['AskQuestion']}"
                    )
                    embed.add_field(name=f"User: {member.display_name}", value=desc, inline=False)
            else:
                for uid, u_stats in stats.items():
                    user_obj = self.bot.get_user(int(uid))
                    username = user_obj.name if user_obj else f"User {uid}"
                    desc = (
                        f"Weekly Quizzes: {u_stats['WeeklyQuiz']['total']} ({u_stats['WeeklyQuiz']['correct']} correct)\n"
                        f"Practice: {u_stats['PracticeQuiz']['total']} ({u_stats['PracticeQuiz']['correct']} correct)\n"
                        f"Asked: {u_stats['AskQuestion']}"
                    )
                    embed.add_field(name=username, value=desc, inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error reading analytics: {e}")

async def setup(bot):
    await bot.add_cog(CourseCommands(bot))
