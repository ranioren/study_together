import discord
from discord.ext import commands
import datetime
import re
import requests
from bs4 import BeautifulSoup
from core.classroom_manager import ClassroomManager
from bot.analytics.tracker import log_user_email # Will create this

class Onboarding(commands.Cog):
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Sends a welcome DM to the guild owner when the bot joins."""
        from core import database
        
        owner = guild.owner
        if not owner:
            try:
                owner = await guild.fetch_member(guild.owner_id)
            except:
                pass
                
        if owner:
            # Check if this guild already has credentials (re-join)
            has_creds = database.get_google_creds(guild.id) is not None
            
            # If not, check if the owner has authenticated on ANY other server
            if not has_creds:
                owner_creds = database.get_user_google_creds(owner.id)
                if owner_creds:
                    # Auto-save these creds for the new guild!
                    database.save_google_creds(guild.id, owner_creds, user_id=owner.id)
                    has_creds = True
                    print(f"Auto-provisioned {guild.name} with existing credentials of owner {owner.name}")
            
            try:
                embed = discord.Embed(
                    title="🎓 Welcome to Kiefer Learning!",
                    description=(
                        f"Thanks for adding me to **{guild.name}**! I'm here to help you automate your "
                        "learning communities and sync them with Google Classroom.\n\n"
                        "**To get started, follow these steps:**"
                    ),
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="1️⃣ Create Admin Space",
                    value="In your server, type `!setup_admin`. I'll create a private channel for you to manage everything.",
                    inline=False
                )
                
                if not has_creds:
                    embed.add_field(
                        name="2️⃣ Link Google Account",
                        value="In the new `#course-admin` channel, type `!auth_google` to connect your Google Classroom account.",
                        inline=False
                    )
                    next_step_num = "3️⃣"
                else:
                    embed.add_field(
                        name="✅ Google Account Connected",
                        value="I see you've already linked your Google Classroom account! You can skip the authentication step.",
                        inline=False
                    )
                    next_step_num = "2️⃣"
                    
                embed.add_field(
                    name=f"{next_step_num} Build a Course",
                    value="Visit our [Web Dashboard](http://localhost:3000) (or your hosted URL) to design your syllabus and launch it to your students!",
                    inline=False
                )
                embed.set_footer(text="I'm excited to help you teach!")
                
                await owner.send(embed=embed)
                print(f"Sent welcome DM to owner of {guild.name}: {owner.name}")
            except discord.Forbidden:
                print(f"Could not send welcome DM to owner of {guild.name}. DMs might be disabled.")

    def __init__(self, bot):
        self.bot = bot
        # Use bot's existing attributes or move them to self if appropriate
        # For now, we'll keep them on the bot instance for compatibility with other parts
        
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Phase 2: Listen for reactions and send DM."""
        if payload.user_id == self.bot.user.id:
            return

        if str(payload.emoji) == "✅":
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
                
            member = guild.get_member(payload.user_id)
            if not member:
                return
                
            active_course = getattr(self.bot, 'active_course', {}).get(guild.id)
            enrollment_end_time = getattr(self.bot, 'enrollment_end_time', {}).get(guild.id)
            
            if not active_course or not enrollment_end_time:
                return
                
            now = datetime.datetime.now(datetime.timezone.utc)
            if now > enrollment_end_time:
                try:
                    await member.send("Hey, too late. Next time!")
                except discord.Forbidden:
                    pass
                return

            materials = self.bot.classroom_manager.get_course_work_materials(active_course['id'])
            topics = [m.get('title', 'Untitled') for m in materials] if materials else ["No topics found."]
            topics_list = "\n".join([f"- {t}" for t in topics])

            try:
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

    @commands.Cog.listener()
    async def on_message(self, message):
        """Phases 3 & 4: Listen for 'I agree' in DMs and add to/create cohort channel."""
        if message.author == self.bot.user:
            return
            
        if not isinstance(message.channel, discord.DMChannel):
            return

        # Check if we are waiting for material from the owner
        if message.author.id == getattr(self.bot, 'owner_id', None) and self.bot.pending_owner_material.get(self.bot.owner_id):
            await self._handle_owner_material(message)
            return
            
        # Check for Phase 3.5: User providing their email
        if message.author.id in self.bot.pending_emails:
            await self._handle_email_provision(message)
            return
                
        elif "i agree" in message.content.lower():
            await self._handle_agreement(message)

    async def _handle_owner_material(self, message):
        course_id, week_index = self.bot.pending_owner_material[self.bot.owner_id]
        content_to_save = message.content.strip()
        
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
        
        elif content_to_save.startswith("http://") or content_to_save.startswith("https://"):
            url = content_to_save.split()[0]
            await message.channel.send(f"🔗 Attempting to extract text from URL: {url}")
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                extracted_text = soup.get_text(separator=' ', strip=True)
                content_to_save = extracted_text
                await message.channel.send("✅ Successfully scraped website text!")
            except Exception as e:
                await message.channel.send(f"⚠️ Failed to scrape URL: {e}. I will use the raw URL text instead, but it might not work well.")
        
        if not content_to_save:
            content_to_save = "General course material"
            
        self.bot.quiz_manager.save_material(course_id, week_index, content_to_save)
        del self.bot.pending_owner_material[self.bot.owner_id]
        await message.channel.send(f"✅ Material saved for Week {week_index + 1}. I will use this to generate the quizzes!")

    async def _handle_email_provision(self, message):
        target_guild_id = None
        for guild in self.bot.guilds:
            if guild.id in self.bot.active_course and guild.id in self.bot.enrollment_end_time:
                target_guild_id = guild.id
                break
                
        if not target_guild_id:
            await message.channel.send("I couldn't find an active course enrollment for you. Please check with an admin.")
            self.bot.pending_emails.remove(message.author.id)
            return
            
        provided_text = message.content.strip()
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', provided_text)
        
        if email_match:
            extracted_email = email_match.group(0).lower()
            self.bot.user_emails[message.author.id] = extracted_email
            self.bot.pending_emails.remove(message.author.id)
            if target_guild_id not in self.bot.pending_cohort_roster:
                self.bot.pending_cohort_roster[target_guild_id] = set()
            self.bot.pending_cohort_roster[target_guild_id].add(message.author.id)
            
            log_user_email(target_guild_id, message.author.id, message.author.name, extracted_email)
            
            try:
                self.bot.classroom_manager.invite_student(target_guild_id, self.bot.active_course[target_guild_id]['id'], extracted_email)
                await message.channel.send(f"📧 I've sent a Google Classroom invitation to **{extracted_email}**. Please check your inbox and accept it!")
            except Exception as e:
                print(f"Failed to send Classroom invitation: {e}")
                await message.channel.send(f"⚠️ I couldn't automatically invite you to Google Classroom. Please ask the instructor to add **{extracted_email}** manually.")

            guild = self.bot.get_guild(target_guild_id)
            if guild:
                member = guild.get_member(message.author.id)
                cohort_channel_id = self.bot.active_cohort_channel_id.get(target_guild_id)
                cohort_channel = self.bot.get_channel(cohort_channel_id) if cohort_channel_id else None
                
                if cohort_channel and member:
                    await cohort_channel.set_permissions(member, read_messages=True, send_messages=True)
                    print(f"Added {member.name} to cohort channel in {guild.name}")
                    
                    embed = discord.Embed(
                        title=f"🎉 Welcome to {self.bot.active_course[target_guild_id]['name']}!",
                        description=f"Hello {member.mention}! This is the private cohort channel.",
                        color=discord.Color.gold()
                    )
                    
                    TOPIC_CYCLE_MINUTES = getattr(self.bot, 'TOPIC_CYCLE_MINUTES', 8)
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

    async def _handle_agreement(self, message):
        target_guild_id = None
        for guild in self.bot.guilds:
            if guild.id in self.bot.active_course and guild.id in self.bot.enrollment_end_time:
                target_guild_id = guild.id
                break
                
        if not target_guild_id:
            return
            
        now = datetime.datetime.now(datetime.timezone.utc)
        if now > self.bot.enrollment_end_time[target_guild_id]:
            await message.channel.send("Hey, too late. Next time!")
            return
        
        self.bot.pending_emails.add(message.author.id)
        await message.channel.send("Great! Before I add you to the course channel, please reply with the exact **Google Account Email Address** (must be a Google/Gmail account) you use for Google Classroom so I can track your submissions and notify you.")

async def setup(bot):
    await bot.add_cog(Onboarding(bot))
