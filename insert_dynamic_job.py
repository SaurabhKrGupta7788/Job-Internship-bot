import sqlite3
import random

c = sqlite3.connect('jobs.db')
c.execute("UPDATE jobs SET status='applied'")
job_key = f"dynamic_search_{random.randint(1000, 9999)}"
c.execute("""
INSERT INTO jobs (job_key, title, company, location, url, description, status) 
VALUES (?, 'Python Developer', 'Various', 'India', 'https://www.linkedin.com/jobs/search/?keywords=Python%20Developer&location=India&f_AL=true', 'Apply to Python Developer jobs in India using Easy Apply.', 'tailored')
""", (job_key,))
c.commit()
print("Inserted dynamic search job into DB as tailored.")
