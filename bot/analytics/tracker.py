import os
import json
import csv
import datetime

def save_quiz_scores(weekly_scores):
    """Persist quiz scores to a local JSON file."""
    try:
        # Ensure directory exists
        os.makedirs("data/quizzes", exist_ok=True)
        # Convert tuple keys to strings for JSON
        serializable_scores = {f"{k[0]}|{k[1]}": v for k, v in weekly_scores.items()}
        with open("data/quizzes/quiz_scores.json", "w") as f:
            json.dump(serializable_scores, f)
    except Exception as e:
        print(f"Error saving quiz scores: {e}")

def log_analytics(guild_id, user_id, event_type, course_name, detail, is_correct):
    """Append an analytics event to a local CSV file."""
    os.makedirs("data/analytics", exist_ok=True)
    if not guild_id:
        # Fallback if unknown guild
        analytics_file = "data/analytics/analytics.csv"
    else:
        analytics_file = f"data/analytics/analytics_{guild_id}.csv"
        
    file_exists = os.path.isfile(analytics_file)
    try:
        with open(analytics_file, "a", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "UserID", "EventType", "CourseName", "Detail", "IsCorrect"])
            writer.writerow([datetime.datetime.now(datetime.timezone.utc).isoformat(), str(user_id), event_type, str(course_name), str(detail), str(is_correct)])
    except Exception as e:
        print(f"Error logging analytics: {e}")

def log_user_email(guild_id, user_id, username, email):
    """Append a user email record to a global CSV file."""
    os.makedirs("data/users", exist_ok=True)
    if not guild_id:
        users_file = "data/users/users.csv"
    else:
        users_file = f"data/users/users_{guild_id}.csv"
        
    file_exists = os.path.isfile(users_file)
    try:
        with open(users_file, "a", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["UserID", "Username", "Email"])
            writer.writerow([str(user_id), str(username), str(email)])
    except Exception as e:
        print(f"Error logging user email: {e}")

def load_quiz_scores():
    """Load quiz scores from local JSON file."""
    quiz_file = "data/quizzes/quiz_scores.json"
    if os.path.exists(quiz_file):
        try:
            with open(quiz_file, "r") as f:
                data = json.load(f)
                # Convert string keys back to tuples
                return {tuple(map(int, k.split('|'))): v for k, v in data.items()}
        except Exception as e:
            print(f"Error loading quiz scores: {e}")
    return {}

async def check_streaks(guild_id, channel, user_id):
    """Phase 8: Check daily interaction and correct answer streaks."""
    if not guild_id:
        analytics_file = "data/analytics/analytics.csv"
    else:
        analytics_file = f"data/analytics/analytics_{guild_id}.csv"
        
    if not os.path.exists(analytics_file):
        return
        
    now = datetime.datetime.now(datetime.timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    interaction_count = 0
    correct_count = 0
    
    try:
        with open(analytics_file, "r", encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row.get("UserID", "")
                if uid != str(user_id):
                    continue
                    
                try:
                    ts = datetime.datetime.fromisoformat(row.get("Timestamp", ""))
                    if ts >= start_of_day:
                        interaction_count += 1
                        if row.get("IsCorrect", "") == "True":
                            correct_count += 1
                except ValueError:
                    continue
                    
        # Notify streaks (using exact match so it only fires once per milestone per day)
        INTERACTION_STREAK = 3
        CORRECT_STREAK = 2
        
        if interaction_count == INTERACTION_STREAK:
            await channel.send(f"🔥 **Hot Streak!** <@{user_id}> has interacted with the course {INTERACTION_STREAK} times today! Keep it up!")
            
        if correct_count == CORRECT_STREAK:
            await channel.send(f"🎯 **Sharpshooter!** <@{user_id}> has answered {CORRECT_STREAK} quizzes correctly today! Excellent work!")

    except Exception as e:
         print(f"Error checking streaks: {e}")
