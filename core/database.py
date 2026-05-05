import psycopg2
import psycopg2.extras
import os
import json
from datetime import datetime, timezone

DB_URI = os.getenv("DATABASE_URL") or os.getenv("AIVEN_DB_URL") or "postgres://avnadmin:dummy_pass_for_github@pg-communilytics-ontheran-2746.h.aivencloud.com:21282/defaultdb?sslmode=require"

def get_connection():
    conn = psycopg2.connect(DB_URI)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Table for Server/Guild Configuration
    c.execute('''
        CREATE TABLE IF NOT EXISTS server_config (
            guild_id BIGINT PRIMARY KEY,
            active_course_id TEXT,
            active_course_name TEXT,
            active_course_link TEXT,
            enrollment_end_time TEXT,
            cohort_channel_id BIGINT,
            current_week_index INTEGER DEFAULT 0,
            pre_start_reminder_sent BOOLEAN DEFAULT FALSE
        )
    ''')

    # Table for Google OAuth Credentials
    c.execute('''
        CREATE TABLE IF NOT EXISTS server_oauth_creds (
            guild_id BIGINT PRIMARY KEY,
            user_id BIGINT,
            credentials_json TEXT
        )
    ''')
    # Ensure user_id column exists for existing tables
    try:
        c.execute("ALTER TABLE server_oauth_creds ADD COLUMN IF NOT EXISTS user_id BIGINT")
    except:
        pass
    
    # Table for tracking expected topic timing events separately per guild
    c.execute('''
        CREATE TABLE IF NOT EXISTS topic_timing (
            guild_id BIGINT PRIMARY KEY,
            start_time TEXT,
            reported_15 BOOLEAN DEFAULT FALSE,
            reported_20 BOOLEAN DEFAULT FALSE,
            reported_70 BOOLEAN DEFAULT FALSE,
            reported_75 BOOLEAN DEFAULT FALSE,
            reported_80 BOOLEAN DEFAULT FALSE,
            reported_90 BOOLEAN DEFAULT FALSE,
            reported_90_reminder BOOLEAN DEFAULT FALSE,
            reported_winner BOOLEAN DEFAULT FALSE
        )
    ''')

    # Users in the course
    c.execute('''
        CREATE TABLE IF NOT EXISTS course_users (
            guild_id BIGINT,
            discord_id BIGINT,
            google_email TEXT,
            PRIMARY KEY (guild_id, discord_id)
        )
    ''')

    # Weekly quiz scores
    c.execute('''
        CREATE TABLE IF NOT EXISTS quiz_scores (
            guild_id BIGINT,
            week_index INTEGER,
            discord_id BIGINT,
            score INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, week_index, discord_id)
        )
    ''')

    # Active Quizzes generated for the week
    c.execute('''
        CREATE TABLE IF NOT EXISTS active_quizzes (
            guild_id BIGINT,
            week_index INTEGER,
            quiz_data_json TEXT,
            PRIMARY KEY (guild_id, week_index)
        )
    ''')

    # Individual user responses to quizzes
    c.execute('''
        CREATE TABLE IF NOT EXISTS quiz_responses (
            guild_id BIGINT,
            week_index INTEGER,
            question_num INTEGER,
            discord_id BIGINT,
            selected_option_index INTEGER,
            PRIMARY KEY (guild_id, week_index, question_num, discord_id)
        )
    ''')

    conn.commit()
    conn.close()

# --- Helper functions for easier querying ---

def set_server_active_course(guild_id, course_id, course_name, course_link):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO server_config (guild_id, active_course_id, active_course_name, active_course_link)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT(guild_id) DO UPDATE SET
            active_course_id=excluded.active_course_id,
            active_course_name=excluded.active_course_name,
            active_course_link=excluded.active_course_link
    ''', (guild_id, course_id, course_name, course_link))
    conn.commit()
    conn.close()

def get_server_config(guild_id):
    conn = get_connection()
    c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    c.execute("SELECT * FROM server_config WHERE guild_id = %s", (guild_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def save_google_creds(guild_id, creds_dict, user_id=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO server_oauth_creds (guild_id, user_id, credentials_json)
        VALUES (%s, %s, %s)
        ON CONFLICT(guild_id) DO UPDATE SET
            credentials_json=excluded.credentials_json,
            user_id=excluded.user_id
    ''', (guild_id, user_id, json.dumps(creds_dict)))
    conn.commit()
    conn.close()

def get_user_google_creds(user_id):
    """Checks if a user has any Google credentials stored across any guild."""
    conn = get_connection()
    c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    c.execute("SELECT credentials_json FROM server_oauth_creds WHERE user_id = %s LIMIT 1", (user_id,))
    row = c.fetchone()
    conn.close()
    return json.loads(row['credentials_json']) if row else None

def get_google_creds(guild_id):
    conn = get_connection()
    c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    c.execute("SELECT credentials_json FROM server_oauth_creds WHERE guild_id = %s", (guild_id,))
    row = c.fetchone()
    conn.close()
    if row and row['credentials_json']:
        return json.loads(row['credentials_json'])
    return None

def get_all_active_guilds():
    conn = get_connection()
    c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    c.execute("SELECT guild_id FROM server_config WHERE active_course_id IS NOT NULL")
    rows = c.fetchall()
    conn.close()
    return [r['guild_id'] for r in rows]

def update_enrollment_end_time(guild_id, end_time_dt):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE server_config SET enrollment_end_time = %s, pre_start_reminder_sent = FALSE WHERE guild_id = %s', 
              (end_time_dt.isoformat(), guild_id))
    conn.commit()
    conn.close()

def set_cohort_channel(guild_id, channel_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE server_config SET cohort_channel_id = %s WHERE guild_id = %s', 
              (channel_id, guild_id))
    conn.commit()
    conn.close()

def add_course_user(guild_id, discord_id, google_email=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO course_users (guild_id, discord_id, google_email)
        VALUES (%s, %s, %s)
        ON CONFLICT(guild_id, discord_id) DO UPDATE SET
            google_email=COALESCE(excluded.google_email, course_users.google_email)
    ''', (guild_id, discord_id, google_email))
    conn.commit()
    conn.close()

def get_course_users(guild_id):
    conn = get_connection()
    c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    c.execute("SELECT discord_id, google_email FROM course_users WHERE guild_id = %s", (guild_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def start_new_topic(guild_id, week_index):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE server_config SET current_week_index = %s WHERE guild_id = %s', (week_index, guild_id))
    c.execute('''
        INSERT INTO topic_timing (guild_id, start_time, reported_15, reported_20, reported_70, reported_75, reported_80, reported_90, reported_90_reminder, reported_winner)
        VALUES (%s, %s, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE)
        ON CONFLICT(guild_id) DO UPDATE SET
            start_time=excluded.start_time,
            reported_15=FALSE, reported_20=FALSE, reported_70=FALSE, reported_75=FALSE, 
            reported_80=FALSE, reported_90=FALSE, reported_90_reminder=FALSE, reported_winner=FALSE
    ''', (guild_id, now))
    conn.commit()
    conn.close()

def get_topic_timing(guild_id):
    conn = get_connection()
    c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    c.execute("SELECT * FROM topic_timing WHERE guild_id = %s", (guild_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def mark_timing_event(guild_id, event_column):
    # event_column should be one of the reported_* columns
    allowed_cols = ['reported_15', 'reported_20', 'reported_70', 'reported_75', 'reported_80', 'reported_90', 'reported_90_reminder', 'reported_winner']
    if event_column not in allowed_cols:
         return
    conn = get_connection()
    c = conn.cursor()
    # Safe string formatting because allowed_cols is strictly checked
    c.execute(f"UPDATE topic_timing SET {event_column} = TRUE WHERE guild_id = %s", (guild_id,))
    conn.commit()
    conn.close()

# Keep memory dict for things we don't care to persist between restarts if they are short lived
# e.g pending owner materials, pending emails
