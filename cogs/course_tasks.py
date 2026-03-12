import discord
import datetime
from discord.ext import commands, tasks
import database
from analytics_manager import log_analytics, check_streaks, save_quiz_scores

TOPIC_CYCLE_MINUTES = 8

class CourseTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.minutely_activity_report.start()
        self.weekly_engagement_report.start()
        self.weekly_course_update.start()
        self.manager_report_loop.start()
        self.poll_student_submissions.start()
        self.pre_course_reminder_loop.start()

    def cog_unload(self):
        self.minutely_activity_report.cancel()
        self.weekly_engagement_report.cancel()
        self.weekly_course_update.cancel()
        self.manager_report_loop.cancel()
        self.poll_student_submissions.cancel()
        self.pre_course_reminder_loop.cancel()

    @tasks.loop(minutes=1)
    async def minutely_activity_report(self):
        import csv
        import os
            
        now = datetime.datetime.now(datetime.timezone.utc)
        one_minute_ago = now - datetime.timedelta(minutes=1)
        
        for guild in self.bot.guilds:
            analytics_file = f"analytics_{guild.id}.csv"
            if not os.path.exists(analytics_file):
                continue

            course_activity = {}
            try:
                with open(analytics_file, "r", encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        cname = row.get("CourseName", "")
                        if not cname or cname == "DM":
                            continue
                            
                        try:
                            ts = datetime.datetime.fromisoformat(row.get("Timestamp", ""))
                            if ts >= one_minute_ago:
                                if cname not in course_activity:
                                    course_activity[cname] = {'quizzes': 0, 'questions': 0}
                                    
                                ev = row.get("EventType", "")
                                if ev in ["WeeklyQuiz", "PracticeQuiz"]:
                                    course_activity[cname]['quizzes'] += 1
                                elif ev == "AskQuestion":
                                    course_activity[cname]['questions'] += 1
                        except ValueError:
                            continue
                            
                for channel in guild.text_channels:
                    cname = channel.name
                    if cname in course_activity:
                        stats = course_activity[cname]
                        if stats['quizzes'] > 0 or stats['questions'] > 0:
                            msg = f"⏱️ **Activity in the last minute:**\n- {stats['quizzes']} quizzes answered\n- {stats['questions']} questions asked"
                            await channel.send(msg)
            except Exception as e:
                print(f"Error in minutely activity report for guild {guild.id}: {e}")

    @minutely_activity_report.before_loop
    async def before_minutely_activity_report(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=TOPIC_CYCLE_MINUTES)
    async def weekly_engagement_report(self):
        import csv
        import os
            
        now = datetime.datetime.now(datetime.timezone.utc)
        cycle_ago = now - datetime.timedelta(minutes=TOPIC_CYCLE_MINUTES)
        
        for guild in self.bot.guilds:
            analytics_file = f"analytics_{guild.id}.csv"
            if not os.path.exists(analytics_file):
                continue

            course_leaders = {} 
            try:
                with open(analytics_file, "r", encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        cname = row.get("CourseName", "")
                        uid = row.get("UserID", "")
                        if not cname or cname == "DM" or not uid:
                            continue
                            
                        try:
                            ts = datetime.datetime.fromisoformat(row.get("Timestamp", ""))
                            if ts >= cycle_ago:
                                if cname not in course_leaders:
                                    course_leaders[cname] = {}
                                
                                if uid not in course_leaders[cname]:
                                    course_leaders[cname][uid] = 0
                                    
                                course_leaders[cname][uid] += 1
                        except ValueError:
                            continue
                            
                if not course_leaders:
                    continue
                    
                embed = discord.Embed(
                    title="🏆 Cycle Server Engagement Leaderboard",
                    description="Here are the most active students across this server's courses over the past cycle!",
                    color=discord.Color.gold()
                )
                
                for cname, users in course_leaders.items():
                    if users:
                        top_user_id = max(users, key=users.get)
                        top_score = users[top_user_id]
                        embed.add_field(name=f"Course: {cname}", value=f"Most Active: <@{top_user_id}> ({top_score} interactions)", inline=False)
                        
                target_channel = discord.utils.get(guild.text_channels, name="general")
                if not target_channel and guild.text_channels:
                    target_channel = guild.text_channels[0]
                    
                if target_channel:
                    await target_channel.send(embed=embed)
            except Exception as e:
                 print(f"Error in weekly engagement report for guild {guild.id}: {e}")

    @weekly_engagement_report.before_loop
    async def before_weekly_engagement_report(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=TOPIC_CYCLE_MINUTES)
    async def weekly_course_update(self):
        print("Running weekly course update...")
        
        for guild in self.bot.guilds:
            course = self.bot.active_course_cache.get(guild.id)
            if not course:
                db_config = database.get_server_config(guild.id)
                if db_config and db_config['active_course_id']:
                    course = {'id': db_config['active_course_id'], 'name': db_config['active_course_name'], 'alternateLink': db_config['active_course_link']}
                    self.bot.active_course_cache[guild.id] = course
            
            if not course:
                continue
                
            course_id = course['id']
                
            raw_course_name = course['name']
            safe_course_name = raw_course_name.lower().replace(" ", "-")
            channel_prefix = f"{safe_course_name}-"
            
            assignments = self.bot.classroom_manager.get_course_work(guild.id, course_id)
            materials = self.bot.classroom_manager.get_course_work_materials(guild.id, course_id)
            students = self.bot.classroom_manager.get_course_students(guild.id, course_id)
            
            total_students = len(students) if students else 0
            total_weeks = len(materials) if materials else 0

            for channel in guild.text_channels:
                if channel.name.startswith(channel_prefix):
                    if channel.id not in self.bot.course_progress:
                        self.bot.course_progress[channel.id] = 0

                    current_week_index = self.bot.course_progress[channel.id]
                    
                    now = datetime.datetime.now(datetime.timezone.utc)
                    enroll_end = self.bot.enrollment_end_time.get(guild.id)
                    if enroll_end and now < enroll_end:
                        print(f"Skipping week update for {channel.name} - enrollment still open.")
                        continue

                    if total_weeks == 0 or current_week_index >= total_weeks:
                        if current_week_index == total_weeks:
                            try:
                                embed = discord.Embed(
                                    title="🎓 Course Finished!",
                                    description=f"Congratulations! We have reached the end of the **{course['name']}** course material.\n\nNo more weekly information will be shared here, but you can always use `!ask` to ask questions about the material!",
                                    color=discord.Color.gold()
                                )
                                embed.add_field(name="Thank You", value="Thanks for taking part in the course! 🎉", inline=False)
                                await channel.send(embed=embed)
                                print(f"Sent completion message to {channel.name}.")
                                self.bot.course_progress[channel.id] += 1
                            except discord.Forbidden:
                                pass
                        continue 
                        
                    try:
                        embed = discord.Embed(
                            title=f"📅 Course Material - Week {current_week_index + 1}!",
                            description=f"Welcome to a new week of {course['name']}! Here is your material for this week:",
                            color=discord.Color.purple()
                        )
                        
                        if materials and current_week_index < len(materials):
                            current_material_module = materials[current_week_index]
                            embed.add_field(name="📘 This Week's Topic", value=current_material_module.get('title', 'Study Guide'), inline=False)
                        
                        if assignments:
                            assignment = assignments[current_week_index % len(assignments)]
                            assignment_text = f"[{assignment['title']}]({assignment.get('alternateLink', '')})"
                            embed.add_field(name="📝 Assignment", value=assignment_text, inline=False)
                            
                            if current_week_index > 0:
                                prev_assignment = assignments[(current_week_index - 1) % len(assignments)]
                                submissions = self.bot.classroom_manager.get_student_submissions(guild.id, course_id, coursework_id=prev_assignment['id'], states=["TURNED_IN"])
                                completed_count = len(submissions) if submissions else 0
                                completion_text = f"{completed_count} out of {total_students} students have submitted."
                                embed.add_field(name="📊 Last Week's Completion Progress", value=completion_text, inline=False)
                                
                                prev_scores = self.bot.weekly_scores.get((channel.id, current_week_index - 1), {})
                                if prev_scores:
                                    best_user_id = max(prev_scores, key=prev_scores.get)
                                    best_score = prev_scores[best_user_id]
                                    embed.add_field(name="🏆 Last Week's Quiz Master", value=f"<@{best_user_id}> answered {best_score} questions correctly!", inline=False)                            
                            
                        embed.add_field(name="Check-in", value="Does anybody have questions?", inline=False)
                        await channel.send(embed=embed)
                        print(f"Sent Week {current_week_index + 1} update to {channel.name}")
                        
                        self.bot.topic_start_time[channel.id] = datetime.datetime.now(datetime.timezone.utc)
                        self.bot.course_progress[channel.id] += 1

                    except discord.Forbidden:
                        pass
        
    @weekly_course_update.before_loop
    async def before_weekly_update(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=30)
    async def manager_report_loop(self):
        if not hasattr(self.bot, 'owner_id') or not self.bot.owner_id:
            return
            
        now = datetime.datetime.now(datetime.timezone.utc)
        cycle_seconds = TOPIC_CYCLE_MINUTES * 60
        target_duration_15 = datetime.timedelta(seconds=cycle_seconds * 0.15)
        target_duration_20 = datetime.timedelta(seconds=cycle_seconds * 0.20)
        target_duration_70 = datetime.timedelta(seconds=cycle_seconds * 0.70)
        target_duration_75 = datetime.timedelta(seconds=cycle_seconds * 0.75)
        target_duration_80 = datetime.timedelta(seconds=cycle_seconds * 0.80)
        target_duration_90 = datetime.timedelta(seconds=cycle_seconds * 0.90)
        target_duration_winner = datetime.timedelta(seconds=cycle_seconds - 30)
        
        for guild in self.bot.guilds:
            course = self.bot.active_course_cache.get(guild.id)
            if not course:
                db_config = database.get_server_config(guild.id)
                if db_config and db_config['active_course_id']:
                    course = {'id': db_config['active_course_id'], 'name': db_config['active_course_name'], 'alternateLink': db_config['active_course_link']}
                    self.bot.active_course_cache[guild.id] = course
            
            if not course:
                continue
                
            course_id = course['id']
            students = self.bot.classroom_manager.get_course_students(course_id)
            total_students = len(students) if students else 0
            assignments = self.bot.classroom_manager.get_course_work(course_id)
            
            db_config = database.get_server_config(guild.id)
            if not db_config:
                continue
                
            timing_data = database.get_topic_timing(guild.id)
            if not timing_data or not timing_data['start_time']:
                continue
                
            start_time = datetime.datetime.fromisoformat(timing_data['start_time'])
            week_index = db_config['current_week_index']
            cohort_ch_id = db_config['cohort_channel_id']
            
            if not cohort_ch_id:
                continue
                
            channel = guild.get_channel(cohort_ch_id)
            if not channel:
                continue
                
            if week_index >= 0:
                elapsed = now - start_time
                
                if week_index == 0 and elapsed >= target_duration_15 and not timing_data['reported_15']:
                    database.mark_timing_event(guild.id, 'reported_15')
                    await self.send_promotion_reminder(guild.id, course_id)
                
                if elapsed >= target_duration_20 and not timing_data['reported_20']:
                    database.mark_timing_event(guild.id, 'reported_20')
                    await self.send_engagement_reminder(guild.id, channel, week_index, start_time)

                if elapsed >= target_duration_70 and not timing_data['reported_70']:
                    database.mark_timing_event(guild.id, 'reported_70')
                    await self.send_manager_report(guild.id, course_id, assignments, week_index, total_students, guild, channel, "70% (3.5 min)")
                    
                if elapsed >= target_duration_75 and not timing_data['reported_75']:
                    database.mark_timing_event(guild.id, 'reported_75')
                    await self.request_next_week_materials(guild.id, course_id, week_index)
                    
                if elapsed >= target_duration_80 and not timing_data['reported_80']:
                    database.mark_timing_event(guild.id, 'reported_80')
                    await self.post_weekly_quiz(course_id, channel, week_index)
                    
                if elapsed >= target_duration_90 and not timing_data['reported_90']:
                    database.mark_timing_event(guild.id, 'reported_90')
                    await self.send_manager_report(guild.id, course_id, assignments, week_index, total_students, guild, channel, "90% (4.5 min)")

                if elapsed >= target_duration_90 and not timing_data['reported_90_reminder']:
                    database.mark_timing_event(guild.id, 'reported_90_reminder')
                    await self.send_quiz_reminder(guild.id, channel, week_index)

                if elapsed >= target_duration_winner and not timing_data['reported_winner']:
                    database.mark_timing_event(guild.id, 'reported_winner')
                    await self.announce_quiz_winner(channel, week_index)

    @manager_report_loop.before_loop
    async def before_manager_report_loop(self):
        await self.bot.wait_until_ready()

    async def send_engagement_reminder(self, guild_id, channel, week_index, start_time):
        import csv
        import os
        
        guild = channel.guild
        analytics_file = f"analytics_{guild.id}.csv"
        
        engaged_users = set()
        if os.path.exists(analytics_file):
            try:
                with open(analytics_file, "r", encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        cname = row.get("CourseName", "")
                        ev = row.get("EventType", "")
                        uid_str = row.get("UserID", "")
                        
                        if cname != channel.name:
                            continue
                        if ev not in ["AskQuestion", "PracticeQuiz"]:
                            continue
                            
                        try:
                            ts = datetime.datetime.fromisoformat(row.get("Timestamp", ""))
                            if ts >= start_time:
                                if uid_str:
                                    engaged_users.add(int(uid_str))
                        except ValueError:
                            continue
            except Exception as e:
                print(f"Error reading analytics for engagement reminder: {e}")
                
        for member in channel.members:
            if member.bot:
                continue
            if member.id not in engaged_users:
                try:
                    embed = discord.Embed(
                        title="👋 Just checking in!",
                        description=f"Hi {member.mention}, I noticed you haven't asked any questions or requested a practice quiz for this week's topic in **{self.bot.active_course[guild_id]['name']}**.\n\n"
                                    f"Take advantage of my capabilities! You can ask me questions using `!ask <question>` or request a quick quiz using `!quiz`. I'm here to help you learn! 📚",
                        color=discord.Color.blue()
                    )
                    await member.send(embed=embed)
                    print(f"Sent engagement reminder to {member.name}")
                except discord.Forbidden:
                    pass

    async def send_quiz_reminder(self, guild_id, channel, week_index):
        scores = self.bot.weekly_scores.get((channel.id, week_index), {})
        responded_users = set(scores.keys())
        
        for member in channel.members:
            if member.bot:
                continue
            if member.id not in responded_users:
                try:
                    embed = discord.Embed(
                        title="⏰ Weekly Quiz Reminder!",
                        description=f"Hi {member.mention}, the weekly quiz for **{self.bot.active_course[guild_id]['name']}** is closing soon, and I noticed you haven't answered it yet!\n\n"
                                    f"Please head back to the <#{channel.id}> channel and submit your answers before time runs out. Good luck! 🍀",
                        color=discord.Color.gold()
                    )
                    await member.send(embed=embed)
                    print(f"Sent weekly quiz reminder to {member.name}")
                except discord.Forbidden:
                    pass

    async def send_promotion_reminder(self, guild_id, course_id):
        try:
            owner = await self.bot.fetch_user(self.bot.owner_id)
            if owner:
                course = self.bot.active_course.get(guild_id)
                if not course:
                    return
                course_name = course['name']
                course_link = course.get('alternateLink', 'No link available')
                
                embed = discord.Embed(
                    title="📢 Reminder: Promote Your Course!",
                    description=f"Your course **{course_name}** has just started its first week! Promote it now to drive great engagement.",
                    color=discord.Color.green()
                )
                
                materials = self.bot.classroom_manager.get_course_work_materials(course_id)
                topics = [m.get('title', 'Untitled') for m in materials] if materials else ["General Topics"]
                topics_str = ", ".join(topics)
                if len(topics_str) > 1024:
                    topics_str = topics_str[:1020] + "..."
                
                embed.add_field(name="What it's about / Topics added", value=topics_str if topics_str else "No specific topics.", inline=False)
                embed.add_field(name="Course Link", value=f"[Go to Course]({course_link})", inline=False)
                
                await owner.send(embed=embed)
                print(f"Sent promotion reminder for {course_name} (Week 1)")
        except discord.Forbidden:
            pass

    async def send_manager_report(self, guild_id, course_id, assignments, week_index, total_students, guild, channel, interval_name):
        if assignments:
            assignment = assignments[week_index % len(assignments)]
            submissions = self.bot.classroom_manager.get_student_submissions(course_id, coursework_id=assignment['id'], states=["TURNED_IN", "RETURNED"])
            
            report_lines = [f"**Report for {self.bot.active_course[guild_id]['name']} (Week {week_index + 1}) - {interval_name} mark**"]
            report_lines.append(f"Assignment: {assignment['title']}")
            report_lines.append(f"Completion: {len(submissions)} out of {total_students} submitted/graded.")
            
            grades = []
            for sub in submissions:
                if 'assignedGrade' in sub:
                    grades.append(f"User {sub.get('userId')}: {sub['assignedGrade']}")
            if grades:
                report_lines.append("\n**Grades:**\n" + "\n".join(grades))
            
            try:
                owner = await self.bot.fetch_user(self.bot.owner_id)
                if owner:
                    quiz_results = self.bot.weekly_scores.get((channel.id, week_index), {})
                    if quiz_results:
                        sorted_scores = sorted(quiz_results.items(), key=lambda x: x[1], reverse=True)
                        quiz_summary = "\n**Quiz Results:**\n" + "\n".join([f"User {uid}: {score} points" for uid, score in sorted_scores[:5]])
                        report_lines.append(quiz_summary)

                    await owner.send("\n".join(report_lines))
                    print(f"Sent {interval_name} manager report for {channel.name} week {week_index + 1}")
            except discord.Forbidden:
                pass

    async def request_next_week_materials(self, guild_id, course_id, current_week_index):
        next_week = current_week_index + 1
        materials = self.bot.classroom_manager.get_course_work_materials(course_id)
        
        if not materials or next_week >= len(materials):
            return
            
        next_material = materials[next_week]
        course_name = self.bot.active_course[guild_id]['name']
        
        try:
            owner = await self.bot.fetch_user(self.bot.owner_id)
            if owner:
                self.bot.pending_owner_material[owner.id] = (course_id, next_week)
                
                embed = discord.Embed(
                    title="📅 Course Content Advisory",
                    description=f"Course: **{course_name}**\nI'm beginning to prepare the material for next week's quizzes!",
                    color=discord.Color.blue()
                )
                
                embed.add_field(name="Next Week's Topic", value=next_material.get('title', f"Week {next_week+1}"), inline=False)
                embed.add_field(name="Optional Override", value="If you have specific text or a website you'd like me to use *instead* of the Classroom description, just reply to this DM with the text, a URL, or a file upload.", inline=False)
                
                await owner.send(embed=embed)
                print(f"Requested materials for week {next_week + 1} from owner.")
        except discord.Forbidden:
            pass

    async def post_weekly_quiz(self, course_id, channel, week_index):
        fallback_text = self.bot.get_full_material_text(course_id, week_index)
             
        material_text = self.bot.quiz_manager.get_material(course_id, week_index, fallback_text=fallback_text)
        
        await channel.send("🤖 *Generating this week's quiz questions based on the material...*")
        
        import asyncio
        loop = asyncio.get_running_loop()
        quiz_data = await loop.run_in_executor(None, self.bot.quiz_manager.generate_weekly_quiz, material_text)
        
        if not quiz_data:
            await channel.send("Failed to generate the quiz for this week. Please try again later.")
            return
            
        self.bot.active_quizzes[(channel.id, week_index)] = quiz_data
            
        embed = discord.Embed(
            title=f"🧠 Week {week_index + 1} Quiz Time!",
            description="Test your knowledge on this week's material. Answer carefully!",
            color=discord.Color.gold()
        )
        await channel.send(embed=embed)
        
        for q_num, item in enumerate(quiz_data):
            q_embed = discord.Embed(
                title=f"Question {q_num + 1}/5",
                description=item['question'],
                color=discord.Color.blue()
            )
            
            view = discord.ui.View(timeout=120)
            
            async def make_callback(opt_index, correct_idx, ch_id, w_idx, q_number):
                async def btn_callback(interaction: discord.Interaction):
                    user_id = interaction.user.id
                    
                    if (ch_id, w_idx) not in self.bot.weekly_scores:
                        self.bot.weekly_scores[(ch_id, w_idx)] = {}
                    if user_id not in self.bot.weekly_scores[(ch_id, w_idx)]:
                        self.bot.weekly_scores[(ch_id, w_idx)][user_id] = 0
                        
                    is_correct = (opt_index == correct_idx)
                    
                    if (ch_id, w_idx) not in self.bot.quiz_responses:
                        self.bot.quiz_responses[(ch_id, w_idx)] = {}
                    if q_number not in self.bot.quiz_responses[(ch_id, w_idx)]:
                        self.bot.quiz_responses[(ch_id, w_idx)][q_number] = {}
                        
                    self.bot.quiz_responses[(ch_id, w_idx)][q_number][user_id] = opt_index
                    
                    channel_obj = interaction.client.get_channel(ch_id)
                    guild_id = channel_obj.guild.id if channel_obj and hasattr(channel_obj, "guild") else None
                    ch_name = channel_obj.name if channel_obj else f"channel-{ch_id}"
                    if is_correct:
                        self.bot.weekly_scores[(ch_id, w_idx)][user_id] += 1
                        save_quiz_scores(self.bot.weekly_scores)
                        log_analytics(guild_id, user_id, "WeeklyQuiz", ch_name, f"Week {w_idx+1} Q{q_number+1}", True)
                    else:
                        log_analytics(guild_id, user_id, "WeeklyQuiz", ch_name, f"Week {w_idx+1} Q{q_number+1}", False)
                        
                    await interaction.response.defer()
                    await check_streaks(guild_id, channel_obj, user_id)
                        
                return btn_callback

            labels = ["A", "B", "C", "D"]
            for opt_idx, opt_text in enumerate(item['options']):
                 btn_label = f"{labels[opt_idx]}: {opt_text}"
                 if len(btn_label) > 80:
                     btn_label = btn_label[:77] + "..."
                     
                 btn = discord.ui.Button(label=btn_label, style=discord.ButtonStyle.primary, custom_id=f"quiz_{week_index}_{q_num}_{opt_idx}")
                 btn.callback = await make_callback(opt_idx, item['correct_index'], channel.id, week_index, q_num)
                 view.add_item(btn)
                 
            await channel.send(embed=q_embed, view=view)

    async def announce_quiz_winner(self, channel, week_index):
        scores = self.bot.weekly_scores.get((channel.id, week_index), {})
        
        if not scores:
            await channel.send(f"🏁 **Week {week_index + 1} Quiz Summary**: No answers were submitted this week!")
            return

        best_user_id = max(scores, key=scores.get)
        best_score = scores[best_user_id]
        winners = [uid for uid, score in scores.items() if score == best_score]
        
        embed = discord.Embed(
            title=f"🏆 Week {week_index + 1} Quiz Results!",
            description="The weekly quiz period has ended. Here are our top performers!",
            color=discord.Color.gold()
        )
        
        if len(winners) > 1:
            winner_mentions = ", ".join([f"<@{uid}>" for uid in winners])
            embed.add_field(name="Winners (Tie!)", value=f"{winner_mentions} all answered {best_score} questions correctly! 🥇", inline=False)
        else:
            embed.add_field(name="Winner", value=f"<@{best_user_id}> is the Quiz Master with {best_score} correct answers! 🥇", inline=False)

        await channel.send(embed=embed)
        print(f"Announced quiz winner for {channel.name} week {week_index + 1}")
        
        quiz_data = self.bot.active_quizzes.get((channel.id, week_index))
        responses = self.bot.quiz_responses.get((channel.id, week_index), {})
        
        if quiz_data:
            res_embed = discord.Embed(
                title=f"📊 Question-by-Question Results",
                description="Here's how everyone answered:",
                color=discord.Color.purple()
            )
            
            for q_num, q_item in enumerate(quiz_data):
                correct_idx = q_item['correct_index']
                correct_label = chr(65 + correct_idx)
                
                q_responses = responses.get(q_num, {})
                answer_summary = []
                if not q_responses:
                    answer_summary.append("*No answers for this question.*")
                else:
                    for uid, opt_idx in q_responses.items():
                        u_label = f"<@{uid}>"
                        o_label = chr(65 + opt_idx)
                        mark = "✅" if opt_idx == correct_idx else "❌"
                        answer_summary.append(f"{u_label}: {o_label} {mark}")
                
                res_text = "\n".join(answer_summary)
                if len(res_text) > 1024:
                    res_text = res_text[:1020] + "..."
                
                field_name = f"Q{q_num+1}: {q_item['question'][:197]}"
                field_value = f"**Correct Answer: {correct_label}**\n{res_text}"
                res_embed.add_field(name=field_name, value=field_value, inline=False)
                
            await channel.send(embed=res_embed)

    @tasks.loop(minutes=5)
    async def poll_student_submissions(self):
        print("Polling for new student submissions...")
        
        for guild in self.bot.guilds:
            course = self.bot.active_course_cache.get(guild.id)
            if not course:
                db_config = database.get_server_config(guild.id)
                if db_config and db_config['active_course_id']:
                    course = {'id': db_config['active_course_id'], 'name': db_config['active_course_name'], 'alternateLink': db_config['active_course_link']}
                    self.bot.active_course_cache[guild.id] = course
            
            if not course:
                continue
                
            course_id = course['id']
                
            assignments = self.bot.classroom_manager.get_course_work(guild.id, course_id)
            assignment_map = {aw['id']: aw for aw in assignments} if assignments else {}
            
            students = self.bot.classroom_manager.get_course_students(guild.id, course_id)
            student_map = {}
            if students:
                for s in students:
                    profile = s.get('profile', {})
                    email = profile.get('emailAddress', '')
                    student_map[s.get('userId')] = email
                
            submissions = self.bot.classroom_manager.get_student_submissions(guild.id, course_id, coursework_id="-", states=["TURNED_IN"])
            
            if not submissions:
                continue
                
            for sub in submissions:
                try:
                    cw_id = sub.get('courseWorkId')
                    assignment = assignment_map.get(cw_id, {})
                    title = assignment.get('title', 'Unknown Assignment')
                    work_type = assignment.get('workType', 'ASSIGNMENT')
                    
                    classroom_user_id = sub.get('userId')
                    classroom_email = student_map.get(classroom_user_id)
                    
                    if not classroom_email:
                        continue 
                    
                    matched_discord_id = None
                    for d_id, d_email in self.bot.user_emails.items():
                        if d_email.lower() == classroom_email.lower():
                            matched_discord_id = d_id
                            break
                            
                    if not matched_discord_id:
                        continue 
                        
                    target_user = guild.get_member(matched_discord_id)
                    
                    if not target_user:
                        continue 
                    
                    embed_title = "📝 Student Submission Received"
                    embed_desc = "We've received your completed work!"
                    
                    if work_type == 'SHORT_ANSWER_QUESTION' or work_type == 'MULTIPLE_CHOICE_QUESTION':
                        embed_title = "❓ Question Answered!"
                        embed_desc = "Your answer has been recorded."
                    elif work_type == 'ASSIGNMENT':
                        embed_title = "📝 Assignment Submitted!"
                        embed_desc = "We've successfully received your assignment."
                    
                    embed = discord.Embed(
                        title=embed_title,
                        description=embed_desc,
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Item", value=title, inline=False)
                    if 'alternateLink' in sub:
                        embed.add_field(name="Link", value=f"[View Submission of your work]({sub['alternateLink']})", inline=False)
                        
                    await target_user.send(embed=embed)
                    print(f"Sent DM submission alert for {title} to {target_user.name}")
                except discord.Forbidden:
                    pass

    @poll_student_submissions.before_loop
    async def before_poll_student_submissions(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=10)
    async def pre_course_reminder_loop(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        
        for guild in self.bot.guilds:
            db_config = database.get_server_config(guild.id)
            if not db_config or not db_config['active_course_id'] or not db_config['enrollment_end_time'] or not db_config['cohort_channel_id']:
                continue
                
            if db_config.get('pre_start_reminder_sent', False):
                continue
                
            # Calculate 5% of topic cycle time (in seconds)
            cycle_seconds = TOPIC_CYCLE_MINUTES * 60
            five_percent_seconds = cycle_seconds * 0.05
            
            enrollment_end = datetime.datetime.fromisoformat(db_config['enrollment_end_time'])
            reminder_time = enrollment_end - datetime.timedelta(seconds=five_percent_seconds)
            
            if now >= reminder_time:
                # Update DB to mark as sent
                conn = database.get_connection()
                c = conn.cursor()
                c.execute('UPDATE server_config SET pre_start_reminder_sent = TRUE WHERE guild_id = %s', (guild.id,))
                conn.commit()
                conn.close()
                
                cohort_ch_id = db_config['cohort_channel_id']
                cohort_channel = self.bot.get_channel(cohort_ch_id)
                if not cohort_channel:
                    continue
                    
                # Count members in the cohort channel (excluding bots)
                member_count = sum(1 for member in cohort_channel.members if not member.bot)
                
                target_channel = discord.utils.get(guild.text_channels, name="general")
                if not target_channel and guild.text_channels:
                     target_channel = guild.text_channels[0]
                     
                if target_channel:
                    course_name = db_config['active_course_name']
                    embed = discord.Embed(
                        title="⏰ Course Starting Soon!",
                        description=f"The new cohort for **{course_name}** is about to begin!\n\nWe currently have **{member_count}** students ready in the new course channel.",
                        color=discord.Color.gold()
                    )
                    try:
                        await target_channel.send(embed=embed)
                        print(f"Sent pre-course reminder to {target_channel.name} in {guild.name} with {member_count} students ready.")
                    except discord.Forbidden:
                        pass

    @pre_course_reminder_loop.before_loop
    async def before_pre_course_reminder_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(CourseTasks(bot))
