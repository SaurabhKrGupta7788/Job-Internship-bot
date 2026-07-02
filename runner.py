import os
import sys
import datetime

# Ensure the script directory is in the path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

import searcher
import tracker
import database
import applier

def main():
    log_file = os.path.join(script_dir, "scheduler_run.log")
    
    with open(log_file, "a") as log:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"\n--- Automation Triggered at {timestamp} ---\n")
        
        try:
            # 1. Initialize DB if not exists
            database.init_db()
            
            # 2. Run Job Search
            log.write("Starting job search...\n")
            new_jobs = searcher.run_job_search()
            log.write(f"Job search finished. Added {new_jobs} new jobs.\n")
            
            # 3. Pre-tailoring new jobs
            log.write("Pre-tailoring new jobs in background...\n")
            import tailor, time
            conn = database.get_db_connection()
            new_job_rows = conn.execute("SELECT id FROM jobs WHERE status = 'new'").fetchall()
            conn.close()
            
            for row in new_job_rows:
                job_id = row['id']
                try:
                    time.sleep(4)
                    tailor.tailor_application(job_id)
                    log.write(f"   Successfully pre-tailored Job ID {job_id}\n")
                except Exception as t_err:
                    error_msg = str(t_err)
                    if "429" in error_msg or "quota" in error_msg.lower():
                        log.write(f"   Rate limit hit! Sleeping for 65s before retrying Job ID {job_id}...\n")
                        time.sleep(65)
                        try:
                            tailor.tailor_application(job_id)
                            log.write(f"   Successfully pre-tailored Job ID {job_id} on retry\n")
                        except Exception as retry_err:
                            log.write(f"   Failed to tailor Job ID {job_id} on retry: {retry_err}\n")
                    else:
                        log.write(f"   Failed to tailor Job ID {job_id}: {t_err}\n")
            
            # 3. Scan for Recruiter Emails
            log.write("Checking for follow-up emails...\n")
            new_emails = tracker.get_recruiter_emails()
            log.write(f"Email check finished. Logged {new_emails} updates.\n")
            
            # 4. Applying to tailored jobs
            log.write("Applying to tailored jobs in background...\n")
            applied_jobs = applier.run_application_loop()
            log.write(f"Successfully ran application loop. Applied to {applied_jobs} jobs.\n")
            
            log.write("Automation completed successfully.\n")
            
        except Exception as e:
            log.write(f"ERROR: Automation failed with exception: {e}\n")
            print(f"Error executing scheduled run: {e}")

if __name__ == "__main__":
    main()
