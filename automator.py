import os
import sys
import time
import json
import re
from playwright.sync_api import sync_playwright
import database
import tailor
import outreach

# Setup log file path
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "automator.log")

def log_progress(message):
    """Writes progress message to console and automator.log for Flask to read."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted_msg + "\n")

def clear_logs():
    """Clears the automator log file."""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

def run_automator(limit=3):
    """
    Launches browser, navigates LinkedIn, applies to Easy Apply jobs,
    and sends automated outreach emails to recruiters.
    """
    clear_logs()
    log_progress("Starting JobCraft Automated Agent...")
    
    profile = database.get_profile()
    if not profile or not profile.get('base_resume'):
        log_progress("ERROR: Profile or base resume is not set. Please update settings first.")
        return
        
    keywords_list = [k.strip() for k in profile['keywords'].split(',') if k.strip()]
    location = profile.get('location', 'remote')
    country = profile.get('country', 'in')
    
    if not keywords_list:
        log_progress("ERROR: No search keywords found in your profile.")
        return

    # Use a local folder to store user browser cookies/cache
    user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_data")
    os.makedirs(user_data_dir, exist_ok=True)
    
    log_progress("Launching Chromium browser context...")
    
    with sync_playwright() as p:
        # Launch persistent context so user stays logged in
        # We start in non-headless mode initially so user can see it
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, # Must be False so user can log in / see forms
            channel="msedge", # Changed from chrome to msedge as requested
            args=["--start-maximized"],
            no_viewport=True,
            slow_mo=800 # Slightly slowed down more to mimic human behavior
        )
        
        page = context.pages[0]
        
        # 1. Login Verification
        log_progress("Checking LinkedIn login state...")
        page.goto("https://www.linkedin.com/feed/", timeout=60000)
        time.sleep(3) # Wait for redirects to settle
        
        # Check if we are redirected to a login or checkpoint page
        if "login" in page.url or "checkpoint" in page.url or "signup" in page.url or not page.locator(".global-nav").is_visible():
            log_progress("ACTION REQUIRED: You are not logged in to LinkedIn.")
            log_progress("Please enter your credentials in the open browser window now.")
            
            # Wait up to 5 minutes (300 seconds) for user to log in manually
            logged_in = False
            for i in range(150):
                time.sleep(2)
                # Once we get to feed or standard jobs feed without login checkpoints
                if "feed" in page.url or ("jobs" in page.url and "login" not in page.url and "checkpoint" not in page.url):
                    logged_in = True
                    break
            
            if not logged_in:
                log_progress("ERROR: Login timeout. Please try again.")
                context.close()
                return
            else:
                log_progress("Login verified successfully!")
        else:
            log_progress("Already logged in to LinkedIn.")

        # 2. Iterate through search keywords
        jobs_applied_count = 0
        
        for kw in keywords_list:
            if jobs_applied_count >= limit:
                break
                
            log_progress(f"Searching for Easy Apply jobs: '{kw}' in '{location}'...")
            
            # Encode URL parameters
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={re.sub(r' ', '%20', kw)}&location={re.sub(r' ', '%20', location)}&f_AL=true"
            page.goto(search_url, timeout=60000)
            
            # Wait for domcontentloaded instead of networkidle to avoid getting stuck
            page.wait_for_load_state("domcontentloaded")
            time.sleep(4) # Human-like pause while jobs load
            
            # Human-like scrolling behavior to trigger lazy loading and bypass basic bot detection
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 600)")
                time.sleep(1.5)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(2)
            
            # Find job cards
            # LinkedIn job cards are list elements containing jobs-search-results__list-item
            job_cards = page.locator(".jobs-search-results__list-item, .job-card-container").all()
            log_progress(f"Found {len(job_cards)} job cards on current page.")
            
            for idx, card in enumerate(job_cards):
                if jobs_applied_count >= limit:
                    break
                    
                try:
                    # Click on card to load detail pane
                    card.scroll_into_view_if_needed()
                    card.click()
                    time.sleep(2) # Wait for details pane to render
                    
                    # Extract Job Details
                    # Job Title
                    title_elem = page.locator(".jobs-unified-top-card__job-title, .jobs-details-top-card__job-title").first
                    if not title_elem.is_visible():
                        continue
                    title = title_elem.inner_text().strip()
                    
                    # Company
                    company_elem = page.locator(".jobs-unified-top-card__company-name, .jobs-details-top-card__company-name").first
                    company = company_elem.inner_text().strip() if company_elem.is_visible() else "Unknown"
                    
                    # Job Key/ID from URL
                    current_url = page.url
                    job_key_match = re.search(r'currentJobId=(\d+)', current_url)
                    job_key = job_key_match.group(1) if job_key_match else current_url
                    
                    log_progress(f"Inspecting lead: '{title}' at '{company}'...")

                    # Check if already processed
                    conn = database.get_db_connection()
                    existing = conn.execute("SELECT id, status FROM jobs WHERE job_key = ?", (job_key,)).fetchone()
                    conn.close()
                    
                    if existing:
                        if existing['status'] in ['applied', 'ignored', 'interview']:
                            log_progress(f"   Skipping. Already {existing['status']}.")
                            continue
                        job_id = existing['id']
                    else:
                        # Fetch Description
                        desc_elem = page.locator("#job-details, .jobs-description__content").first
                        description = desc_elem.inner_text().strip() if desc_elem.is_visible() else ""
                        
                        # Add to Database
                        job_dict = {
                            'key': job_key,
                            'title': title,
                            'company': company,
                            'description': description,
                            'location': location,
                            'url': f"https://www.linkedin.com/jobs/view/{job_key}/",
                            'salary': 'N/A'
                        }
                        database.add_jobs([job_dict])
                        
                        conn = database.get_db_connection()
                        job_id = conn.execute("SELECT id FROM jobs WHERE job_key = ?", (job_key,)).fetchone()['id']
                        conn.close()

                    # 3. Check for Easy Apply button
                    # Selector can be jobs-apply-button or class that says Easy Apply
                    apply_btn = page.locator("button.jobs-apply-button").first
                    if not apply_btn.is_visible():
                        log_progress("   No 'Easy Apply' button available for this listing. Skipping.")
                        database.update_job_status(job_id, 'ignored')
                        continue
                        
                    # 4. Tailor Resume for this Job
                    log_progress(f"   Tailoring your resume for '{company}' using Gemini...")
                    try:
                        tailor.tailor_application(job_id)
                    except Exception as e:
                        log_progress(f"   AI Tailoring failed: {e}. Using base resume as fallback.")
                    
                    # Fetch tailored docx path from database
                    job_data = database.get_job(job_id)
                    resume_file_path = job_data.get('tailored_resume_docx_path')
                    
                    if not resume_file_path or not os.path.exists(resume_file_path):
                        log_progress("   ERROR: Tailored resume file not found on disk. Skipping apply.")
                        continue

                    # 5. Execute Easy Apply modal clicks
                    log_progress("   Triggering 'Easy Apply' flow...")
                    apply_btn.click()
                    time.sleep(2)
                    
                    # Handle multi-step dialog
                    max_steps = 10
                    success = False
                    
                    for step in range(max_steps):
                        # Check if submit button is visible
                        submit_btn = page.locator("button:has-text('Submit application'), button:has-text('Submit')").first
                        next_btn = page.locator("button:has-text('Next'), button:has-text('Review')").first
                        
                        # Handle uploading resume if file upload input is visible
                        file_input = page.locator("input[type='file']").first
                        if file_input.is_visible():
                            log_progress("   Uploading tailored DOCX resume...")
                            file_input.set_input_files(resume_file_path)
                            time.sleep(2)

                        # Answer standard questions if input fields are present
                        # Find text input fields and select fields
                        inputs = page.locator("input[type='text'], select").all()
                        for inp in inputs:
                            if inp.is_visible() and not inp.input_value():
                                # Get label or question text
                                # Try finding parent text or preceding label
                                question_text = "years of experience"
                                try:
                                    question_text = inp.evaluate("el => el.closest('.jobs-easy-apply-form-section__grouping').innerText")
                                except:
                                    pass
                                
                                # Basic heuristic for common questions
                                if "experience" in question_text.lower() or "years" in question_text.lower():
                                    inp.fill("3") # Default to 3 years matching your resume
                                elif "city" in question_text.lower() or "location" in question_text.lower():
                                    inp.fill(location)
                                elif "notice" in question_text.lower():
                                    inp.fill("Immediate")
                                elif inp.evaluate("el => el.tagName") == "SELECT":
                                    # Select first option
                                    inp.select_option(index=1)
                        
                        if submit_btn.is_visible():
                            import config
                            if getattr(config, 'DRY_RUN', False):
                                log_progress("   [DRY RUN] Skipping final submit click.")
                                dismiss_btn = page.locator("button[aria-label='Dismiss']").first
                                if dismiss_btn.is_visible():
                                    dismiss_btn.click()
                                    confirm_cancel = page.locator("button:has-text('Discard')").first
                                    if confirm_cancel.is_visible():
                                        confirm_cancel.click()
                                success = False
                                break
                            log_progress("   Submitting application form on LinkedIn...")
                            submit_btn.click()
                            time.sleep(3)
                            success = True
                            
                            # Close the confirmation modal if it appears
                            close_btn = page.locator("button[aria-label='Dismiss'], button:has-text('Done')").first
                            if close_btn.is_visible():
                                close_btn.click()
                            break
                        elif next_btn.is_visible():
                            next_btn.click()
                            time.sleep(2)
                        else:
                            # Modal got stuck or required custom manual answers
                            log_progress("   Form requires complex answers. Closing modal to skip.")
                            dismiss_btn = page.locator("button[aria-label='Dismiss']").first
                            if dismiss_btn.is_visible():
                                dismiss_btn.click()
                                # Confirm cancel
                                confirm_cancel = page.locator("button:has-text('Discard')").first
                                if confirm_cancel.is_visible():
                                    confirm_cancel.click()
                            break

                    if success:
                        database.update_job_status(job_id, 'applied')
                        jobs_applied_count += 1
                        log_progress(f"   SUCCESS! Applied to '{title}' at '{company}'.")
                        
                        # 6. Recruiter Outreach
                        log_progress("   Locating recruiter details for outreach...")
                        recruiter_name = "Hiring Manager"
                        
                        # Try finding recruiter name on page
                        recruiter_elem = page.locator(".jobs-poster__name, .jobs-details-top-card__hiring-manager-name").first
                        if recruiter_elem.is_visible():
                            recruiter_name = recruiter_elem.inner_text().strip()
                            log_progress(f"   Found Job Poster: {recruiter_name}")
                        
                        # Generate pitch
                        log_progress("   Generating AI email pitch and LinkedIn invite...")
                        linkedin_msg, email_subject, email_body = outreach.generate_outreach_messages(job_id, recruiter_name)
                        
                        if email_body:
                            # Guess email address
                            rec_email = outreach.guess_recruiter_email(recruiter_name, company)
                            if rec_email:
                                log_progress(f"   Guessed Recruiter Email: {rec_email}")
                                log_progress("   Sending cold email outreach automatically...")
                                sent, status_msg = outreach.send_cold_email(rec_email, email_subject, email_body)
                                log_progress(f"   Email Status: {status_msg}")
                            else:
                                log_progress("   Could not guess recruiter email domain. Skipping email.")
                        else:
                            log_progress("   Outreach message generation failed.")
                    else:
                        log_progress(f"   Failed to submit Easy Apply for '{title}' (form was complex or stuck).")
                        
                except Exception as card_err:
                    log_progress(f"   Error processing job card: {card_err}")
                    continue
                    
        context.close()
        log_progress(f"Automator run complete. Successfully applied to {jobs_applied_count} jobs.")

if __name__ == '__main__':
    run_automator(limit=2)
