import sqlite3
c = sqlite3.connect("jobcraft.db")
c.execute("UPDATE jobs SET status='tailored' WHERE status='failed_apply'")
c.commit()
c.close()
