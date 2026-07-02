import imaplib
import email
from email.header import decode_header
import re
import datetime
from config import EMAIL_IMAP_SERVER, EMAIL_ADDRESS, EMAIL_PASSWORD, GEMINI_API_KEY
import database
import google.generativeai as genai
import json

def get_recruiter_emails():
    """
    Scans the email inbox for updates matching applied companies and log follow-ups.
    """
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Email credentials not configured. Skipping email tracker.")
        return 0

    print("Connecting to email server via IMAP...")
    try:
        # Connect to IMAP
        mail = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("inbox")
    except Exception as e:
        print(f"Failed to connect or login to IMAP: {e}")
        return 0

    # Get companies we applied to
    conn = database.get_db_connection()
    applied_jobs = conn.execute("SELECT id, company, title FROM jobs WHERE status IN ('applied', 'interview', 'tailored')").fetchall()
    conn.close()

    if not applied_jobs:
        print("No active applications to track follow-ups for.")
        mail.logout()
        return 0

    company_names = [j['company'] for j in applied_jobs]
    safe_names = [c.encode('ascii', 'replace').decode('ascii') for c in company_names]
    print(f"Tracking follow-ups for companies: {', '.join(safe_names)}")

    new_updates_count = 0

    # Search for unread emails in the last 7 days to make it efficient
    today = datetime.date.today()
    since_date = (today - datetime.timedelta(days=7)).strftime("%d-%b-%Y")
    
    # We can search for emails with subjects containing terms like 'interview', 'application', 'hiring'
    # Or search broadly for emails from the last 7 days and filter locally.
    # Searching UNSEEN is usually best.
    status, messages = mail.search(None, f'(SINCE {since_date})')
    
    if status != 'OK':
        print("Error searching mailbox.")
        mail.logout()
        return 0

    email_ids = messages[0].split()
    print(f"Found {len(email_ids)} emails to inspect from the last 7 days...")

    # Configure Gemini for email parsing
    use_gemini = bool(GEMINI_API_KEY)
    if use_gemini:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-flash-lite-latest")

    # Fetch email details
    for e_id in reversed(email_ids): # Check newest first
        # Limit to checking top 30 emails to avoid rate limits
        if new_updates_count >= 10:
            break
            
        res, msg_data = mail.fetch(e_id, '(RFC822)')
        if res != 'OK':
            continue

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Decode Subject
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")
                
                # Decode Sender
                sender, encoding = decode_header(msg["From"])[0]
                if isinstance(sender, bytes):
                    sender = sender.decode(encoding or "utf-8", errors="ignore")
                
                # Get Date
                date_str = msg["Date"]
                
                # Extract Message-ID for threading replies
                message_id = msg.get("Message-ID", "")
                
                # Extract snippet/body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disp = str(part.get('Content-Disposition'))
                        if content_type == "text/plain" and "attachment" not in content_disp:
                            try:
                                body = part.get_payload(decode=True).decode(errors="ignore")
                            except:
                                pass
                            break
                else:
                    try:
                        body = msg.get_payload(decode=True).decode(errors="ignore")
                    except:
                        pass
                
                snippet = body[:500].strip().replace('\n', ' ')

                # Check if this email matches any applied company
                matched_job = None
                for job in applied_jobs:
                    # Case insensitive match of company name in Subject, Sender, or Body snippet
                    comp_pattern = re.compile(re.escape(job['company']), re.IGNORECASE)
                    if comp_pattern.search(subject) or comp_pattern.search(sender) or comp_pattern.search(snippet):
                        matched_job = job
                        break

                if matched_job:
                    # Let's check if we already logged this follow-up
                    # Check in DB to prevent duplicates
                    conn = database.get_db_connection()
                    exists = conn.execute(
                        "SELECT COUNT(*) FROM follow_ups WHERE job_id = ? AND sender = ? AND subject = ?",
                        (matched_job['id'], sender, subject)
                    ).fetchone()[0]
                    conn.close()

                    if exists > 0:
                        continue

                    safe_sender = sender.encode('ascii', 'replace').decode('ascii')
                    safe_subject = subject.encode('ascii', 'replace').decode('ascii')
                    safe_company = matched_job['company'].encode('ascii', 'replace').decode('ascii')
                    print(f"Match found! Email from '{safe_sender}' regarding '{safe_subject}' matches company '{safe_company}'")

                    # Use Gemini to classify the reply: interview offer, rejection, follow-up query, automated acknowledgment, or spam/promo
                    status_type = "update"
                    summary_text = snippet
                    is_spam = False
                    
                    if use_gemini:
                        prompt = f"""
                        Analyze this email received from a recruiter or employer. 
                        Sender: {sender}
                        Subject: {subject}
                        Body: {snippet}

                        Classify the email into one of these categories:
                        1. "spam" (Promotional newsletters, mass marketing, courses, obvious phishing/fraud, or completely unrelated to a job application)
                        2. "acknowledgment" (automatic email saying "we received your application")
                        3. "rejection" (indicating the candidate was not selected)
                        4. "interview_invite" (inviting the candidate to a coding test, screen, or interview)
                        5. "query" (asking for salary details, notice period, or documents)
                        6. "other" (none of the above, but still a genuine job-related communication)

                        Extract the following insights:
                        - is_spam: Boolean true if the category is "spam", false otherwise.
                        - summary: A 1-sentence summary of the key message.
                        - action_needed: Boolean true if the user needs to reply, click a link, or do a test.
                        - action_steps: A brief 1-2 sentence description of what the user must do (or empty string).
                        - important_links: A comma-separated list of any important URLs (assessments, calendars) mentioned in the body (or empty string).

                        Output your response in the following JSON schema:
                        {{
                          "category": "category_name",
                          "is_spam": false,
                          "summary": "1-sentence summary",
                          "action_needed": true,
                          "action_steps": "steps",
                          "important_links": "url1, url2"
                        }}
                        """
                        try:
                            resp = model.generate_content(
                                prompt, 
                                generation_config={"response_mime_type": "application/json"}
                            )
                            analysis = json.loads(resp.text)
                            cat = analysis.get('category', 'other')
                            summary_text = analysis.get('summary', snippet[:100])
                            action_needed = analysis.get('action_needed', False)
                            action_steps = analysis.get('action_steps', '')
                            important_links = analysis.get('important_links', '')
                            is_spam = analysis.get('is_spam', False)
                            
                            # Automatically update the job state if it's an interview or rejection
                            if not is_spam:
                                if cat == "interview_invite":
                                    database.update_job_status(matched_job['id'], 'interview')
                                elif cat == "rejection":
                                    database.update_job_status(matched_job['id'], 'rejected')
                        except Exception as gemini_err:
                            print(f"Gemini email analysis failed: {gemini_err}")
                            cat = 'other'
                            action_needed = False
                            action_steps = ''
                            important_links = ''
                            is_spam = False

                    database.add_follow_up(
                        job_id=matched_job['id'],
                        sender=sender,
                        subject=subject,
                        snippet=summary_text,
                        category=cat,
                        action_needed=action_needed,
                        action_steps=action_steps,
                        important_links=important_links,
                        is_spam=is_spam,
                        message_id=message_id
                    )
                    new_updates_count += 1
                else:
                    # If not matched to a specific applied job, check if it is generally job related
                    job_keywords = ["job", "career", "hiring", "interview", "application", "opportunity", "resume", "talent"]
                    if any(k in subject.lower() or k in snippet.lower() for k in job_keywords):
                        
                        # Use Gemini to quickly filter out spam/promo for general job inbox
                        is_spam = False
                        if use_gemini:
                            prompt = f"""
                            You are a spam filter for a job seeker's inbox.
                            Sender: {sender}
                            Subject: {subject}
                            Body snippet: {snippet}
                            
                            Determine if this email is genuine recruiter outreach/job communication, OR if it is spam/marketing/newsletter/fraud.
                            Return JSON: {{"is_spam": true/false}}
                            """
                            try:
                                resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                                analysis = json.loads(resp.text)
                                is_spam = analysis.get('is_spam', False)
                            except:
                                pass
                                
                        # Catch general job related emails in inbox cache
                        database.add_inbox_email(
                            sender=sender,
                            subject=subject,
                            snippet=snippet[:250],
                            body_text=body,
                            category='other',
                            is_spam=is_spam,
                            message_id=message_id
                        )

    mail.logout()
    print(f"Email check complete. Found and logged {new_updates_count} new follow-up updates.")
    return new_updates_count

if __name__ == "__main__":
    get_recruiter_emails()
