import database
c = database.get_db_connection()
c.execute("UPDATE jobs SET status='tailored' WHERE status='failed_apply'")
c.commit()
c.close()
