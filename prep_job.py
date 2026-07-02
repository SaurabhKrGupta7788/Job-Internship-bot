import sqlite3
c = sqlite3.connect('jobs.db')
c.execute("UPDATE jobs SET status='applied'")
c.execute("UPDATE jobs SET status='tailored' WHERE id=293")
c.commit()
print("Job 293 has been set up as the only tailored job for the next test.")
