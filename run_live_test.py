import requests
import database
import tailor
import searcher
import os

def main():
    print("--- Running Live JobCraft Test ---")
    
    # 1. Fetch live jobs from Arbeitnow
    print("1. Fetching live developer listings from Arbeitnow...")
    try:
        r = requests.get('https://www.arbeitnow.com/api/job-board-api', timeout=15)
        if r.status_code != 200:
            print(f"Error calling Arbeitnow API: {r.status_code}")
            return
            
        data = r.json()
        raw_jobs = data.get('data', [])
    except Exception as e:
        print(f"Failed to fetch jobs: {e}")
        return

    # Filter for AI/Python/Software jobs
    target_job = None
    for rj in raw_jobs:
        title_lower = rj.get('title', '').lower()
        if 'junior' in title_lower and ('software' in title_lower or 'engineer' in title_lower or 'developer' in title_lower):
            target_job = rj
            break
            
    # Fallback to the first developer role if no junior is found
    if not target_job:
        for rj in raw_jobs:
            title_lower = rj.get('title', '').lower()
            if 'developer' in title_lower or 'engineer' in title_lower:
                target_job = rj
                break

    if not target_job:
        print("Could not find any suitable developer job listings to test with.")
        return

    print(f"Found Job: '{target_job['title']}' at '{target_job['company_name']}'")
    
    # 2. Insert into Database
    clean_desc = searcher.clean_html(target_job.get('description', ''))
    
    job_dict = {
        'key': target_job.get('url'),
        'title': target_job.get('title'),
        'company': target_job.get('company_name'),
        'description': clean_desc,
        'location': target_job.get('location', 'Remote'),
        'url': target_job.get('url'),
        'salary': 'N/A'
    }
    
    # Initialize DB in case it isn't
    database.init_db()
    
    inserted = database.add_jobs([job_dict])
    print(f"2. Database insertion done. Inserted: {inserted}")
    
    # Retrieve job ID
    conn = database.get_db_connection()
    job_row = conn.execute("SELECT id FROM jobs WHERE job_key = ?", (job_dict['key'],)).fetchone()
    conn.close()
    
    if not job_row:
        print("ERROR: Could not retrieve the job from DB.")
        return
        
    job_id = job_row['id']
    print(f"Target Job Database ID: {job_id}")
    
    # 3. Tailor resume and cover letter
    print("3. Requesting Gemini AI to tailor your resume and cover letter...")
    try:
        result = tailor.tailor_application(job_id)
        
        print("\n=== LIVE TEST RESULTS ===")
        print(f"Match Score: {result.get('match_score')}%")
        print(f"Analysis:\n{result.get('match_analysis')}")
        print("\nTailored DOCX generated and status updated in database!")
        print(f"You can download the docx file in your dashboard workspace at http://127.0.0.1:5000")
    except Exception as e:
        print(f"Tailoring failed: {e}")

if __name__ == '__main__':
    main()
