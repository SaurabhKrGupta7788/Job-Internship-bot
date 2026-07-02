import os
import json
import database
import generator
import tailor

def run_mock_test():
    print("--- Starting JobCraft Mock Test ---")
    
    # 1. Initialize DB
    print("1. Initializing database...")
    database.init_db()
    
    # 2. Seed a mock job in database
    print("2. Seeding a mock job listing...")
    mock_jobs = [
        {
            'key': 'mock_job_123',
            'title': 'Senior Python Developer',
            'company': 'InnovateTech Systems',
            'description': 'Looking for a Senior Python Developer with experience in Flask, SQLite, and automated script creation. Must write clean, documented code and collaborate with cross-functional teams.',
            'location': 'Remote',
            'salary': '₹1,200,000 - ₹1,800,000'
        }
    ]
    inserted = database.add_jobs(mock_jobs)
    print(f"   Seeded {inserted} job(s).")
    
    # 3. Retrieve profile and job
    profile = database.get_profile()
    conn = database.get_db_connection()
    job = conn.execute("SELECT * FROM jobs WHERE job_key = 'mock_job_123'").fetchone()
    conn.close()
    
    if not job:
        print("ERROR: Mock job not seeded correctly.")
        return
        
    print(f"3. Simulating Gemini resume tailoring for job ID: {job['id']}...")
    
    # Mocking Gemini's tailored output
    base_resume = json.loads(profile['base_resume'])
    
    # Customize summary and bullet points slightly to match description
    tailored_resume = base_resume.copy()
    tailored_resume['summary'] = "Results-driven Senior Python Developer with 3+ years of experience building scalable web applications. Proficient in Python, Flask, and SQLite. Experienced in automating workflow scripts and database management, matching InnovateTech's engineering standards."
    
    # Tailor first job experience highlights
    tailored_resume['experience'][0]['highlights'] = [
        "Developed and maintained RESTful APIs using Flask and SQLite, aligning with InnovateTech's backend requirements.",
        "Automated database management and backup scripts using Python, improving manual task efficiency by 25%.",
        "Collaborated with cross-functional teams to design interactive reporting dashboards."
    ]
    
    mock_match_score = 92
    mock_match_analysis = "* Strong match in Python, Flask, and SQLite\n* Matches requirements for automation and clean code\n* Solid background in collaborative team setups"
    mock_cover_letter = f"""Dear Hiring Manager at InnovateTech Systems,

I am writing to express my strong interest in the Senior Python Developer position. With over 3 years of hands-on experience building backend APIs using Flask and optimizing SQLite databases, I am confident in my ability to contribute to InnovateTech Systems.

In my previous roles, I have focused heavily on automated scripting and database reliability, which aligns perfectly with your job description. I look forward to the opportunity to discuss how my skills can benefit your engineering team.

Sincerely,
{base_resume.get('name', 'Your Name')}"""

    # Generate html resume representation
    html_resume = tailor.generate_resume_html(tailored_resume)
    
    # Generate tailored DOCX file
    output_docx_path = os.path.join(os.path.dirname(__file__), "output", "Resume_InnovateTech_Systems_Senior_Python_Developer.docx")
    generator.create_docx_resume(tailored_resume, output_docx_path)
    
    # Save tailoring results to DB
    database.update_job_tailoring(
        job_id=job['id'],
        match_score=mock_match_score,
        match_analysis=mock_match_analysis,
        cover_letter=mock_cover_letter,
        tailored_resume_html=html_resume,
        tailored_resume_docx_path=output_docx_path
    )
    
    print("4. Updating job status to 'tailored'...")
    
    # Check updated job in DB
    updated_job = database.get_job(job['id'])
    print("\n--- Test Verification ---")
    print(f"Job Title: {updated_job['title']}")
    print(f"Status: {updated_job['status']}")
    print(f"Match Score: {updated_job['match_score']}%")
    print(f"DOCX Generated: {os.path.exists(updated_job['tailored_resume_docx_path'])}")
    print(f"HTML Resume Preview Length: {len(updated_job['tailored_resume_html'])} chars")
    print("Mock Test Finished Successfully!")

if __name__ == '__main__':
    run_mock_test()
