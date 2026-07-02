import os
import time
import json
import datetime
import asyncio
from browser_use import Agent, Browser, ChatGoogle
import database
import config

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "automator.log")

def log_progress(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {msg}"
    try:
        print(formatted)
    except UnicodeEncodeError:
        print(formatted.encode('ascii', 'replace').decode('ascii'))
    with open(os.path.join(os.path.dirname(__file__), "automator.log"), "a", encoding="utf-8") as f:
        f.write(formatted + "\n")

async def run_application_loop(limit=1):
    """
    Finds tailored jobs and physically applies to them using browser-use Agent.
    """
    log_progress("Starting JobCraft Applier Worker (Agentic)...")
    
    conn = database.get_db_connection()
    jobs_to_apply = conn.execute("SELECT * FROM jobs WHERE status = 'tailored' LIMIT ?", (limit,)).fetchall()
    
    if not jobs_to_apply:
        log_progress("No 'tailored' jobs found waiting for application.")
        conn.close()
        return 0

    log_progress(f"Found {len(jobs_to_apply)} tailored jobs to apply to.")
    
    api_key = getattr(config, 'GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY'))
    if not api_key:
        log_progress("ERROR: GEMINI_API_KEY not found in config.")
        conn.close()
        return 0
        
    llm = ChatGoogle(
        model="gemini-2.5-flash",
        api_key=api_key,
    )
    
    # Bulletproof rate limit handler
    original_ainvoke = llm.ainvoke
    async def delayed_ainvoke(*args, **kwargs):
        log_progress("   [Rate Limit Handler] Waiting 15 seconds to respect Gemini Free Tier limits...")
        await asyncio.sleep(15)
        return await original_ainvoke(*args, **kwargs)
    llm.ainvoke = delayed_ainvoke
    
    # Use saved LinkedIn login session if available
    if os.path.exists("./chrome_profile"):
        log_progress("   [Authentication] Found saved LinkedIn profile! Agent will be logged in.")
        browser = Browser(headless=False, user_data_dir="./chrome_profile")
    else:
        log_progress("   [Authentication] No chrome profile found. Agent will browse anonymously.")
        browser = Browser(headless=False)
    
    applied_count = 0
    
    for job in jobs_to_apply:
        job_id = job['id']
        url = job['url']
        company = job['company']
        
        profile = conn.execute("SELECT base_resume FROM profile LIMIT 1").fetchone()
        resume_text = profile['base_resume'] if profile else "No resume data provided."
        
        resume_docx = job['tailored_resume_docx_path']
        upload_instruction = ""
        if resume_docx:
            # Format path for browser-use (use double backslashes or raw string)
            resume_docx_clean = resume_docx.replace('\\', '/')
            upload_instruction = f"CRITICAL: You MUST explicitly click 'Upload Resume' (or the equivalent button to upload a file) and upload the file located exactly at: {resume_docx_clean}\nDo not rely on pre-filled default resumes. You must ensure this specific document is uploaded."

        log_progress(f"Applying to Job ID {job_id}: {company}")
        
        prompt = f"""
        You are an autonomous job application agent. 
        Your task is to navigate to this job posting: {url}
        If there is an 'Easy Apply' or 'Apply Now' button, click it.
        Fill out the application form accurately using the following resume data:
        
        {resume_text[:2000]} # Truncated for token limit
        
        {upload_instruction}
        
        Navigate through all steps and submit the application.
        Do not spend more than 10 steps on this.
        """
        
        try:
            agent = Agent(
                task=prompt,
                llm=llm,
                browser=browser,
                generate_gif=f"agent_job_{job_id}.gif"
            )
            
            result = await agent.run()
            
            # result is an AgentHistoryList. Check if it's successful
            if not result.is_successful():
                log_progress(f"   Agent finished but wasn't successful.")
                database.update_job_status(job_id, 'failed_apply')
            else:
                log_progress(f"   SUCCESS! Completed application for '{company}'.")
                database.update_job_status(job_id, 'applied')
                applied_count += 1
            
        except Exception as e:
            database.update_job_status(job_id, 'failed_apply')
            log_progress(f"   Failed to apply to Job ID {job_id}: {e}. Marked as failed_apply.")
            
    try:
        await browser.close()
    except Exception:
        pass
    conn.close()
    return applied_count

if __name__ == "__main__":
    asyncio.run(run_application_loop())
