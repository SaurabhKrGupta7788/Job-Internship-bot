import os
import threading
from flask import Flask, render_template, jsonify, request, send_file
import database
import searcher
import tailor
import tracker
import scheduler
import json

app = Flask(__name__)
app.secret_key = "jobcraft_secret_key_local_dev"

# Ensure database is initialized
database.init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/api/profile', methods=['GET'])
def get_profile():
    profile = database.get_profile()
    return jsonify(profile)

@app.route('/api/profile', methods=['POST'])
def save_profile():
    data = request.json
    database.update_profile(
        full_name=data.get('full_name', ''),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        base_resume=data.get('base_resume', ''),
        keywords=data.get('keywords', ''),
        country=data.get('country', 'in'),
        location=data.get('location', 'remote')
    )
    return jsonify({"success": True, "message": "Profile updated successfully."})

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    status = request.args.get('status')
    job_type = request.args.get('job_type')
    jobs = database.get_jobs(status=status, job_type=job_type, limit=100)
    return jsonify(jobs)

@app.route('/api/jobs/<int:job_id>', methods=['GET'])
def get_job(job_id):
    job = database.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)

@app.route('/api/jobs/<int:job_id>/status', methods=['POST'])
def update_job_status(job_id):
    data = request.json
    status = data.get('status')
    if status not in ['new', 'ignored', 'tailored', 'applied', 'interview', 'rejected']:
        return jsonify({"error": "Invalid status"}), 400
    
    database.update_job_status(job_id, status)
    return jsonify({"success": True, "message": f"Job status updated to {status}."})

# Global state flags for background engines
SEARCH_ACTIVE = False
TAILORING_ACTIVE = False

@app.route('/api/jobs/status', methods=['GET'])
def get_engine_status():
    return jsonify({
        "search_active": SEARCH_ACTIVE,
        "tailoring_active": TAILORING_ACTIVE
    })

@app.route('/api/jobs/toggle-search', methods=['POST'])
def toggle_search():
    global SEARCH_ACTIVE
    if SEARCH_ACTIVE:
        SEARCH_ACTIVE = False
        return jsonify({"success": True, "message": "Job search stopping...", "active": False})
    
    data = request.json or {}
    custom_location = data.get('location')

    SEARCH_ACTIVE = True
    def bg_search():
        global SEARCH_ACTIVE
        try:
            if custom_location:
                # Override profile location for this run
                import searcher
                profile = database.get_profile()
                keywords = profile.get('keywords') if profile else None
                country = profile.get('country') if profile else None
                jobs = searcher.search_jobspy_jobs(keywords=keywords, country=country, location=custom_location)
                if jobs:
                    database.add_jobs(jobs)
            else:
                searcher.run_job_search()
        except Exception as e:
            print(f"Background job search failed: {e}")
        finally:
            SEARCH_ACTIVE = False
            
    thread = threading.Thread(target=bg_search)
    thread.start()
    return jsonify({"success": True, "message": "Job search started.", "active": True})

@app.route('/api/jobs/toggle-tailor', methods=['POST'])
def toggle_tailor():
    global TAILORING_ACTIVE
    if TAILORING_ACTIVE:
        TAILORING_ACTIVE = False
        return jsonify({"success": True, "message": "Auto-tailoring stopping...", "active": False})

    TAILORING_ACTIVE = True
    def bg_tailor():
        global TAILORING_ACTIVE
        try:
            import database, tailor, time
            conn = database.get_db_connection()
            new_jobs = conn.execute("SELECT id FROM jobs WHERE status = 'new'").fetchall()
            conn.close()
            
            print(f"Flask Auto-Tailor: Processing {len(new_jobs)} jobs in background...")
            for r in new_jobs:
                if not TAILORING_ACTIVE:
                    print("Auto-tailoring stopped manually.")
                    break
                    
                try:
                    time.sleep(4) # Throttle to respect Gemini free tier limit (15 RPM)
                    
                    if not TAILORING_ACTIVE: break # Check again after sleep
                    tailor.tailor_application(r['id'])
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "quota" in error_msg.lower():
                        print(f"Rate limit hit! Sleeping for 65 seconds before continuing...")
                        for _ in range(65):
                            if not TAILORING_ACTIVE: break
                            time.sleep(1)
                            
                        if not TAILORING_ACTIVE: break
                        try:
                            tailor.tailor_application(r['id']) # Retry once after sleeping
                        except Exception as retry_e:
                            print(f"Retry failed for Job ID {r['id']}: {retry_e}")
                    else:
                        print(f"Tailoring failed for Job ID {r['id']}: {e}")
        except Exception as e:
            print(f"Background auto-tailor failed: {e}")
        finally:
            TAILORING_ACTIVE = False

    thread = threading.Thread(target=bg_tailor)
    thread.start()
    return jsonify({"success": True, "message": "Auto-tailoring started.", "active": True})

@app.route('/api/jobs/status/tailor', methods=['GET'])
def status_tailor():
    global TAILORING_ACTIVE
    return jsonify({"active": TAILORING_ACTIVE})

APPLYING_ACTIVE = False

@app.route('/api/jobs/toggle-apply', methods=['POST'])
def toggle_apply():
    global APPLYING_ACTIVE
    if APPLYING_ACTIVE:
        APPLYING_ACTIVE = False
        return jsonify({"success": True, "message": "Auto-applying stopping...", "active": False})

    APPLYING_ACTIVE = True
    def bg_apply():
        global APPLYING_ACTIVE
        try:
            import applier
            import asyncio
            while APPLYING_ACTIVE:
                asyncio.run(applier.run_application_loop(limit=1))
                import time
                for _ in range(15):
                    if not APPLYING_ACTIVE: break
                    time.sleep(1)
        except Exception as e:
            print(f"Background auto-apply failed: {e}")
        finally:
            APPLYING_ACTIVE = False

    thread = threading.Thread(target=bg_apply)
    thread.start()
    return jsonify({"success": True, "message": "Auto-applying started.", "active": True})

@app.route('/api/jobs/status/apply', methods=['GET'])
def status_apply():
    global APPLYING_ACTIVE
    return jsonify({"active": APPLYING_ACTIVE})

@app.route('/api/jobs/<int:job_id>/tailor', methods=['POST'])
def tailor_job(job_id):
    try:
        result = tailor.tailor_application(job_id)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            return jsonify({"success": False, "error": "Gemini free-tier rate limit reached (15 requests per minute). The background bot is likely processing jobs. Please wait 15-30 seconds and try clicking again."}), 429
            
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": error_msg}), 500

@app.route('/api/jobs/<int:job_id>/outreach', methods=['POST'])
def trigger_outreach(job_id):
    try:
        import outreach, os
        job = database.get_job(job_id)
        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404
            
        if not job.get('tailored_resume_docx_path'):
            return jsonify({"success": False, "error": "You must tailor the job before sending outreach so the custom resume and cover letter can be attached."}), 400
            
        data = request.json or {}
        recruiter_email = data.get('recruiter_email', '').strip()
        recruiter_name = data.get('recruiter_name', '').strip()
        
        # 1. Fallback 1: Extract from description
        if not recruiter_email:
            recruiter_email = outreach.extract_email_from_text(job.get('description', ''))
            
        # 2. Fallback 2: Guess HR
        if not recruiter_email:
            domain = outreach.clean_company_name_for_domain(job.get('company', 'Unknown'))
            recruiter_email = f"hr@{domain}"
            
        # Generate Messages
        _, subject, body = outreach.generate_outreach_messages(job_id, recruiter_name or "Hiring Manager")
        if not subject or not body:
            return jsonify({"success": False, "error": "Failed to generate email content via Gemini."}), 500
            
        # Find Attachments
        resume_path = job.get('tailored_resume_docx_path')
        # Reconstruct Cover Letter path (replace Resume_ with CoverLetter_ and .docx with .txt)
        dir_name = os.path.dirname(resume_path)
        base_name = os.path.basename(resume_path)
        cl_base = base_name.replace("Resume_", "CoverLetter_").replace(".docx", ".txt")
        cl_path = os.path.join(dir_name, cl_base)
        
        attachments = [resume_path]
        if os.path.exists(cl_path):
            attachments.append(cl_path)
            
        # Send
        success, msg = outreach.send_cold_email(recruiter_email, subject, body, attachment_paths=attachments)
        
        if success:
            return jsonify({"success": True, "message": f"Successfully sent outreach email to {recruiter_email} with attachments."})
        else:
            return jsonify({"success": False, "error": msg}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/jobs/<int:job_id>/download/docx', methods=['GET'])
def download_docx(job_id):
    job = database.get_job(job_id)
    if not job or not job.get('tailored_resume_docx_path'):
        return jsonify({"error": "Tailored DOCX not found. Please run tailoring first."}), 404
        
    docx_path = job.get('tailored_resume_docx_path')
    if not os.path.exists(docx_path):
        return jsonify({"error": "DOCX file does not exist on disk."}), 404
        
    return send_file(
        docx_path, 
        as_attachment=True, 
        download_name=os.path.basename(docx_path)
    )

@app.route('/api/tracker/status', methods=['GET'])
def get_tracker_status():
    is_scheduled = scheduler.is_task_scheduled()
    profile = database.get_profile()
    
    # Check if email config is present
    from config import EMAIL_ADDRESS, EMAIL_PASSWORD
    email_configured = bool(EMAIL_ADDRESS and EMAIL_PASSWORD)
    
    return jsonify({
        "is_scheduled": is_scheduled,
        "email_configured": email_configured,
        "run_log_exists": os.path.exists(os.path.join(os.path.dirname(__file__), "scheduler_run.log"))
    })

@app.route('/api/tracker/schedule', methods=['POST'])
def schedule_tracker():
    data = request.json or {}
    time_str = data.get('time', '10:00')
    interval = int(data.get('interval', 2))
    
    success, message = scheduler.schedule_task(time_str=time_str, interval_days=interval)
    return jsonify({"success": success, "message": message})

@app.route('/api/tracker/unschedule', methods=['POST'])
def unschedule_tracker():
    success, message = scheduler.unschedule_task()
    return jsonify({"success": success, "message": message})

@app.route('/api/tracker/sync', methods=['POST'])
def sync_emails():
    # Sync emails in a background thread
    def bg_sync():
        try:
            tracker.get_recruiter_emails()
        except Exception as e:
            print(f"Background email sync failed: {e}")
            
    thread = threading.Thread(target=bg_sync)
    thread.start()
    return jsonify({"success": True, "message": "Email check started in background."})

@app.route('/api/follow_ups', methods=['GET'])
def get_follow_ups():
    fups = database.get_follow_ups()
    return jsonify(fups)

@app.route('/api/inbox', methods=['GET'])
def get_inbox():
    emails = database.get_job_inbox()
    return jsonify(emails)

@app.route('/api/inbox/reply', methods=['POST'])
def draft_reply():
    data = request.json
    subject = data.get('subject', '')
    body_text = data.get('body_text', '')
    
    from config import GEMINI_API_KEY
    import google.generativeai as genai
    
    if not GEMINI_API_KEY:
        return jsonify({"success": False, "error": "Gemini API Key not configured."}), 400
        
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-flash-lite-latest")
        
        prompt = f"""
        You are a highly professional, polite AI assistant helping a job seeker draft a reply to an email from a recruiter/employer.
        
        Original Email Subject: {subject}
        Original Email Body:
        {body_text[:2000]}
        
        Draft a polite, concise, and professional reply. Do not include [Your Name] placeholders if possible, just write the body of the reply. Keep it under 150 words.
        """
        
        resp = model.generate_content(prompt)
        return jsonify({"success": True, "draft": resp.text})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/inbox/send', methods=['POST'])
def send_inbox_reply():
    data = request.json
    to_email = data.get('to_email')
    subject = data.get('subject')
    body = data.get('body')
    in_reply_to_id = data.get('message_id')
    
    from config import EMAIL_ADDRESS, EMAIL_PASSWORD
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return jsonify({"success": False, "error": "Email credentials not configured in .env"}), 400
        
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import re
    
    match = re.search(r'<([^>]+)>', to_email)
    actual_to = match.group(1) if match else to_email
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = actual_to
    
    if not subject.lower().startswith('re:'):
        subject = 'Re: ' + subject
    msg['Subject'] = subject
    
    if in_reply_to_id:
        msg['In-Reply-To'] = in_reply_to_id
        msg['References'] = in_reply_to_id
        
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return jsonify({"success": True, "message": "Reply sent successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Playwright Automator Endpoints ---
automator_thread = None
is_automator_running = False

@app.route('/api/automator/start', methods=['POST'])
def start_automator():
    global automator_thread, is_automator_running
    if is_automator_running:
        return jsonify({"success": False, "message": "Automated agent is already running."})
        
    import automator
    
    def run_bg():
        global is_automator_running
        is_automator_running = True
        try:
            automator.run_automator(limit=5)
        except Exception as e:
            print(f"Automator exception: {e}")
        finally:
            is_automator_running = False
            
    automator_thread = threading.Thread(target=run_bg)
    automator_thread.start()
    return jsonify({"success": True, "message": "Automated agent launched. Opening browser window..."})

@app.route('/api/automator/status', methods=['GET'])
def get_automator_status():
    global is_automator_running
    log_content = ""
    log_path = os.path.join(os.path.dirname(__file__), "automator.log")
    
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log_content = f.read()
        except Exception as e:
            log_content = f"Error reading logs: {e}"
            
    return jsonify({
        "is_running": is_automator_running,
        "logs": log_content
    })

if __name__ == '__main__':
    # Initialize output directory
    from config import PORT
    print(f"Starting local server at http://127.0.0.1:{PORT}")
    app.run(host='127.0.0.1', port=PORT, debug=True)
