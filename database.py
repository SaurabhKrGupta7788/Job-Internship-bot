import sqlite3
import datetime
from config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create profile table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY,
        full_name TEXT,
        email TEXT,
        phone TEXT,
        base_resume TEXT, -- Stores JSON or Markdown representation of base resume
        keywords TEXT,    -- Comma-separated target keywords
        country TEXT,     -- Country code (in, us, gb, etc.)
        location TEXT     -- Preferred location
    )
    """)
    
    # Create jobs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_key TEXT UNIQUE,
        title TEXT,
        company TEXT,
        description TEXT,
        location TEXT,
        url TEXT,
        salary TEXT,
        status TEXT DEFAULT 'new', -- 'new', 'ignored', 'tailored', 'applied', 'interview', 'rejected'
        match_score INTEGER DEFAULT 0,
        match_analysis TEXT,
        cover_letter TEXT,
        tailored_resume_html TEXT,
        tailored_resume_docx_path TEXT,
        date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        date_applied TIMESTAMP,
        job_type TEXT DEFAULT 'job', -- 'job' or 'internship'
        site TEXT -- The source of the job posting
    )
    """)
    
    # Auto-migration for existing DBs
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN job_type TEXT DEFAULT 'job'")
    except sqlite3.OperationalError:
        pass # Column likely already exists
        
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN site TEXT")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    try:
        cursor.execute("ALTER TABLE follow_ups ADD COLUMN category TEXT DEFAULT 'other'")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    try:
        cursor.execute("ALTER TABLE follow_ups ADD COLUMN action_needed BOOLEAN DEFAULT 0")
        cursor.execute("ALTER TABLE follow_ups ADD COLUMN action_steps TEXT")
        cursor.execute("ALTER TABLE follow_ups ADD COLUMN important_links TEXT")
    except sqlite3.OperationalError:
        pass # Column likely already exists
        
    try:
        cursor.execute("ALTER TABLE follow_ups ADD COLUMN is_spam BOOLEAN DEFAULT 0")
        cursor.execute("ALTER TABLE follow_ups ADD COLUMN message_id TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE job_inbox ADD COLUMN is_spam BOOLEAN DEFAULT 0")
        cursor.execute("ALTER TABLE job_inbox ADD COLUMN message_id TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Create follow_ups table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS follow_ups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        date_received TIMESTAMP,
        sender TEXT,
        subject TEXT,
        snippet TEXT,
        category TEXT DEFAULT 'other',
        action_needed BOOLEAN DEFAULT 0,
        action_steps TEXT,
        important_links TEXT,
        status TEXT DEFAULT 'unread',
        FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
    )
    """)

    # Create job_inbox table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_inbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_received TIMESTAMP,
        sender TEXT,
        subject TEXT,
        snippet TEXT,
        body_text TEXT,
        category TEXT DEFAULT 'other',
        status TEXT DEFAULT 'unread'
    )
    """)
    
    # Seed default profile if none exists
    cursor.execute("SELECT COUNT(*) FROM profile")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO profile (id, full_name, email, phone, base_resume, keywords, country, location)
        VALUES (1, 'Your Name', 'your.email@example.com', '+1234567890', '', 'python developer, software engineer', 'in', 'remote')
        """)
        
    conn.commit()
    conn.close()

def get_profile():
    conn = get_db_connection()
    profile = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    return dict(profile) if profile else None

def update_profile(full_name, email, phone, base_resume, keywords, country, location):
    conn = get_db_connection()
    conn.execute("""
    UPDATE profile
    SET full_name = ?, email = ?, phone = ?, base_resume = ?, keywords = ?, country = ?, location = ?
    WHERE id = 1
    """, (full_name, email, phone, base_resume, keywords, country, location))
    conn.commit()
    conn.close()

def add_jobs(jobs_list):
    conn = get_db_connection()
    inserted_count = 0
    for job in jobs_list:
        try:
            conn.execute("""
            INSERT INTO jobs (job_key, title, company, description, location, url, salary, status, job_type, site)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
            """, (
                job.get('key'),
                job.get('title'),
                job.get('company'),
                job.get('description'),
                job.get('location'),
                job.get('url'),
                job.get('salary'),
                job.get('job_type', 'job'),
                job.get('site', 'Unknown')
            ))
            inserted_count += 1
        except sqlite3.IntegrityError:
            # Job already exists
            pass
    conn.commit()
    conn.close()
    return inserted_count

def get_jobs(status=None, job_type=None, limit=50):
    conn = get_db_connection()
    
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
        
    if job_type:
        query += " AND job_type = ?"
        params.append(job_type)
        
    query += " ORDER BY date_found DESC LIMIT ?"
    params.append(limit)
    
    jobs = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [dict(job) for job in jobs]

def get_job(job_id):
    conn = get_db_connection()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(job) if job else None

def update_job_status(job_id, status):
    conn = get_db_connection()
    date_applied = datetime.datetime.now() if status == 'applied' else None
    
    if status == 'applied':
        conn.execute(
            "UPDATE jobs SET status = ?, date_applied = ? WHERE id = ?",
            (status, date_applied, job_id)
        )
    else:
        conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (status, job_id)
        )
    conn.commit()
    conn.close()

def update_job_tailoring(job_id, match_score, match_analysis, cover_letter, tailored_resume_html, tailored_resume_docx_path):
    conn = get_db_connection()
    conn.execute("""
    UPDATE jobs
    SET match_score = ?, match_analysis = ?, cover_letter = ?, tailored_resume_html = ?, tailored_resume_docx_path = ?, status = 'tailored'
    WHERE id = ?
    """, (match_score, match_analysis, cover_letter, tailored_resume_html, tailored_resume_docx_path, job_id))
    conn.commit()
    conn.close()

def add_follow_up(job_id, sender, subject, snippet, category='other', action_needed=False, action_steps='', important_links='', date_received=None, is_spam=False, message_id=''):
    if not date_received:
        date_received = datetime.datetime.now()
    conn = get_db_connection()
    conn.execute("""
    INSERT INTO follow_ups (job_id, sender, subject, snippet, category, action_needed, action_steps, important_links, date_received, is_spam, message_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (job_id, sender, subject, snippet, category, action_needed, action_steps, important_links, date_received, is_spam, message_id))
    conn.commit()
    conn.close()

def add_inbox_email(sender, subject, snippet, body_text, category='other', date_received=None, is_spam=False, message_id=''):
    if not date_received:
        date_received = datetime.datetime.now()
    conn = get_db_connection()
    # Check if exists
    exists = conn.execute("SELECT COUNT(*) FROM job_inbox WHERE message_id = ? OR (sender = ? AND subject = ?)", (message_id, sender, subject)).fetchone()[0]
    if exists == 0:
        conn.execute("""
        INSERT INTO job_inbox (sender, subject, snippet, body_text, category, date_received, is_spam, message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sender, subject, snippet, body_text, category, date_received, is_spam, message_id))
    conn.commit()
    conn.close()

def get_job_inbox():
    conn = get_db_connection()
    inbox = conn.execute("SELECT * FROM job_inbox WHERE is_spam = 0 ORDER BY date_received DESC").fetchall()
    conn.close()
    return [dict(e) for e in inbox]

def get_follow_ups():
    conn = get_db_connection()
    follow_ups = conn.execute("""
    SELECT f.*, j.title, j.company 
    FROM follow_ups f
    JOIN jobs j ON f.job_id = j.id
    WHERE f.is_spam = 0
    ORDER BY f.date_received DESC
    """).fetchall()
    conn.close()
    return [dict(f) for f in follow_ups]

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
