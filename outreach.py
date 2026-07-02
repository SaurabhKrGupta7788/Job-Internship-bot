import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
import google.generativeai as genai
from config import EMAIL_ADDRESS, EMAIL_PASSWORD, GEMINI_API_KEY
import database
import json
import re

def clean_company_name_for_domain(company_name):
    """Converts 'Labeless (Bytes & Pixels GmbH)' to 'labeless.com' or similar."""
    name = company_name.lower()
    # Remove anything in parentheses
    name = re.sub(r'\(.*?\)', '', name)
    # Remove common corporate suffixes
    suffixes = ['gmbh', 'ltd', 'pvt', 'inc', 'co', 'technologies', 'systems', 'solutions', 'limited']
    for s in suffixes:
        name = re.sub(r'\b' + s + r'\b', '', name)
    
    # Clean symbols
    name = re.sub(r'[^\w\s]', '', name).strip()
    # Replace spaces with empty string or hyphens
    domain_prefix = name.replace(' ', '')
    if not domain_prefix:
        domain_prefix = "company"
    return f"{domain_prefix}.com"

def extract_email_from_text(text):
    """Uses regex to find the first email address in a block of text."""
    if not text: return None
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else None

def guess_recruiter_email(recruiter_name, company_name):
    """Guesses recruiter email based on name and company name."""
    if not recruiter_name:
        return None
        
    domain = clean_company_name_for_domain(company_name)
    
    # Split name into first and last
    parts = [p.strip() for p in recruiter_name.lower().split() if p.strip()]
    if not parts:
        return None
        
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    
    if last:
        # standard pattern: first.last@company.com
        return f"{first}.{last}@{domain}"
    else:
        # pattern: first@company.com
        return f"{first}@{domain}"

def generate_outreach_messages(job_id, recruiter_name="Hiring Manager"):
    """
    Generates a personalized LinkedIn invite and a cold email pitch using Gemini.
    """
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY is not configured. Cannot generate outreach.")
        return None, None

    job = database.get_job(job_id)
    profile = database.get_profile()
    
    if not job or not profile:
        return None, None
        
    base_resume = json.loads(profile['base_resume'])
    
    prompt = f"""
    You are an expert career consultant. Draft a cold outreach LinkedIn connection request (strictly under 300 characters including spaces) and a short, high-impact cold email (strictly under 150 words) from the candidate to the recruiter.
    
    Candidate Name: {profile['full_name']}
    Candidate Email: {profile['email']}
    Candidate Phone: {profile['phone']}
    Candidate Resume Details (JSON): {json.dumps(base_resume, indent=2)}
    
    Recruiter Name: {recruiter_name}
    Job Title: {job['title']}
    Company: {job['company']}
    Job Description Snippet: {job['description'][:500]}
    
    Guidelines:
    1. Highlight the candidate's unique strengths, especially their national hackathon wins or research roles (KIT Germany, IITs).
    2. The LinkedIn message must be brief, polite, and immediately show fit (strictly <= 290 chars).
    3. The Email should be punchy: clear subject line, strong opening hook, brief explanation of matching skills, and a call-to-action to connect.
    
    Output your response in the following strict JSON schema:
    {{
      "linkedin_message": "LinkedIn connect message here...",
      "email_subject": "Subject Line here...",
      "email_body": "Dear [Recruiter]... [Full email text here]"
    }}
    """
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-flash-lite-latest")
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        result = json.loads(response.text)
        return result.get('linkedin_message'), result.get('email_subject'), result.get('email_body')
    except Exception as e:
        print(f"Error generating outreach messages: {e}")
        return None, None, None

def send_cold_email(to_email, subject, body, attachment_paths=None):
    """
    Sends the generated email using SMTP (Gmail).
    """
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return False, "SMTP Email credentials not configured in .env"
        
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        if attachment_paths:
            for file_path in attachment_paths:
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    msg.attach(part)
        
        # Connect to Gmail SMTP (port 587 for TLS)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        
        # Send Email
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()
        
        print(f"Outreach email successfully sent to {to_email}")
        return True, "Email sent successfully."
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False, f"SMTP Error: {str(e)}"

if __name__ == '__main__':
    # Test Email guessing
    print(guess_recruiter_email("Saurabh Kumar", "MishiPay Pvt. Ltd."))
    print(guess_recruiter_email("John", "Labeless (GmbH)"))
