import discord
from discord.ext import commands
import datetime
import os
import io
from PIL import Image, ImageDraw, ImageFont
from analytics_manager import log_analytics, check_streaks

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
    async def start_course(self, ctx):
        """Admin command to list courses and select an active one."""
        
        is_authorized = False
        if ctx.author.id == self.bot.owner_id:
            is_authorized = True
        elif hasattr(ctx.author, 'guild_permissions') and ctx.author.guild_permissions.administrator:
            is_authorized = True

        if not is_authorized:
            await ctx.send("You do not have permission to use this command.")
            return

        courses = self.bot.classroom_manager.list_courses()
        if not courses:
            await ctx.send("No courses found in Google Classroom.")
            return

        embed = discord.Embed(title="Available Courses", description="Reply with the number of the course you want to start.", color=discord.Color.blue())
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
                self.bot.active_course = selected_course
                
                course_id = selected_course['id']
                try:
                    students = self.bot.classroom_manager.get_course_students(course_id)
                    total_students = len(students) if students else 0
                    assignments = self.bot.classroom_manager.get_course_work(course_id)
                    total_assignments = len(assignments) if assignments else 0
                    materials = self.bot.classroom_manager.get_course_work_materials(course_id)
                    total_weeks = len(materials) if materials else 0
                except Exception as e:
                    total_students, total_assignments, total_weeks = 0, 0, 0
                    print(f"Stats fetch error: {e}")

                confirm_embed = discord.Embed(
                    title=f"✅ Course Selected: {selected_course['name']}",
                    description="Course data successfully fetched. Use `!announce_course` in #general to begin enrollment!",
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
        except ValueError:
             await ctx.send("Please enter a valid number.")
        except Exception as e:
             await ctx.send("Timed out or an error occurred. Please try again.")

    @commands.command()
    async def announce_course(self, ctx):
        """Fetch and announce the course, creating the channel immediately."""
        if not self.bot.active_course:
            await ctx.send("No active course selected! Use `!start_course` first to select a course.")
            return
            
        course = self.bot.active_course

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
        self.bot.enrollment_end_time = now + datetime.timedelta(minutes=1, seconds=30) 
        self.bot.pre_start_reminder_sent = False
        
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
            self.bot.active_cohort_channel_id = cohort_channel.id
            print(f"Created new cohort channel {channel_name}")
            
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
            
        if not self.bot.active_course or (not is_owner and ctx.author.id not in self.bot.pending_cohort_roster):
            await ctx.send("You must be fully enrolled in an active course to request practice quizzes.")
            return
            
        course_id = self.bot.active_course['id']
        
        current_week_index = 0
        if self.bot.active_cohort_channel_id and self.bot.active_cohort_channel_id in self.bot.course_progress:
            current_week_index = max(0, self.bot.course_progress[self.bot.active_cohort_channel_id] - 1)
            
        await ctx.send("🤖 *Thinking of a good question based on this week's material...*")
        
        fallback_text = self.bot.get_full_material_text(course_id, current_week_index)
             
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
        if not self.bot.active_course:
            await ctx.send("No active course is running right now to ask questions about.")
            return
            
        course_id = self.bot.active_course['id']
        current_week_index = 0
        is_owner = (ctx.author.id == self.bot.owner_id)
        
        if isinstance(ctx.channel, discord.DMChannel):
            if not is_owner and ctx.author.id not in self.bot.pending_cohort_roster:
                await ctx.send("You must be fully enrolled in an active course to ask questions.")
                return
            if self.bot.active_cohort_channel_id and self.bot.active_cohort_channel_id in self.bot.course_progress:
                current_week_index = max(0, self.bot.course_progress[self.bot.active_cohort_channel_id] - 1)
        else:
            if ctx.channel.id in self.bot.course_progress:
                current_week_index = max(0, self.bot.course_progress[ctx.channel.id] - 1)
            else:
                 if is_owner:
                     if self.bot.active_cohort_channel_id and self.bot.active_cohort_channel_id in self.bot.course_progress:
                         current_week_index = max(0, self.bot.course_progress[self.bot.active_cohort_channel_id] - 1)
                 else:
                     await ctx.send("Please use `!ask` inside your cohort channel or in a Direct Message with me.")
                     return
                 
        thinking_msg = await ctx.send("🤔 *Reading the material to find your answer...*")
        
        fallback_text = self.bot.get_full_material_text(course_id, current_week_index)
             
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
        is_authorized = False
        if ctx.author.id == self.bot.owner_id:
            is_authorized = True
        elif hasattr(ctx.author, 'guild_permissions') and ctx.author.guild_permissions.administrator:
            is_authorized = True

        if not is_authorized:
            await ctx.send("You do not have permission to use this command.")
            return

        if not self.bot.active_course:
            await ctx.send("No active course selected! Use `!start_course` first.")
            return

        course_id = self.bot.active_course['id']
        
        msg = await ctx.send("📊 *Generating status report...*")
        
        try:
            students = self.bot.classroom_manager.get_course_students(course_id)
            total_students = len(students) if students else 0
            assignments = self.bot.classroom_manager.get_course_work(course_id)
            
            embed = discord.Embed(
                title=f"📊 Course Report: {self.bot.active_course['name']}",
                description=f"Current status of the course enrollment and participation.",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            
            embed.add_field(name="Total Enrolled Students", value=str(total_students), inline=True)
            embed.add_field(name="Onboarded via Discord", value=str(len(self.bot.pending_cohort_roster)), inline=True)
            
            if self.bot.active_cohort_channel_id and self.bot.active_cohort_channel_id in self.bot.course_progress:
                current_week = self.bot.course_progress[self.bot.active_cohort_channel_id]
                embed.add_field(name="Current Week", value=f"Week {current_week}", inline=True)
            
            if assignments:
                assignment_info = ""
                for assign in assignments[:3]:
                    submissions = self.bot.classroom_manager.get_student_submissions(course_id, coursework_id=assign['id'], states=["TURNED_IN", "RETURNED"])
                    count = len(submissions) if submissions else 0
                    assignment_info += f"• **{assign['title']}**: {count}/{total_students} turned in\n"
                
                embed.add_field(name="Recent Assignments", value=assignment_info or "No assignments found.", inline=False)

            if (self.bot.active_cohort_channel_id, current_week - 1) in self.bot.weekly_scores:
                quiz_results = self.bot.weekly_scores[(self.bot.active_cohort_channel_id, current_week - 1)]
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
