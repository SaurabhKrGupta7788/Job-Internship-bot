import os
import sys
import time
import sqlite3
import subprocess
import urllib.request
import pytest
import nest_asyncio
nest_asyncio.apply()

# Spawns mock Flask server on port 5001
@pytest.fixture(scope="session", autouse=True)
def mock_server():
    server_path = os.path.join(os.path.dirname(__file__), "mock_server", "server.py")
    process = subprocess.Popen([sys.executable, server_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for the server to spin up dynamically (timeout 5s)
    start_time = time.time()
    success = False
    while time.time() - start_time < 5.0:
        try:
            with urllib.request.urlopen("http://localhost:5001/health") as response:
                if response.status == 200:
                    success = True
                    break
        except Exception:
            time.sleep(0.1)
            
    if not success:
        # If server failed, terminate it and raise error
        process.terminate()
        stdout, stderr = process.communicate()
        stdout_str = stdout.decode() if stdout else "None (DEVNULL)"
        stderr_str = stderr.decode() if stderr else "None (DEVNULL)"
        raise RuntimeError(
            f"Mock Flask server failed to start on port 5001.\n"
            f"STDOUT: {stdout_str}\n"
            f"STDERR: {stderr_str}"
        )
    
    yield
    
    # Terminate server after tests finish
    process.terminate()
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()

# Sets up an isolated test database
@pytest.fixture(scope="function")
def test_db():
    # We must add the parent directory to sys.path to import database and config
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        
    import config
    import database
    
    # Save original DB paths
    orig_config_db = config.DB_PATH
    orig_database_db = database.DB_PATH
    
    test_db_path = os.path.join(parent_dir, "test_jobs.db")
    
    # Set config and database paths to the test DB
    config.DB_PATH = test_db_path
    database.DB_PATH = test_db_path
    
    # Clean up prior test DB file if present
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass
            
    # Initialize DB using app logic
    database.init_db()
    
    # Seed the profile with test data
    conn = sqlite3.connect(test_db_path)
    conn.execute("""
    UPDATE profile
    SET full_name = 'Test Candidate',
        email = 'test@example.com',
        phone = '+19999999999',
        base_resume = '{"name": "Test Candidate"}',
        keywords = 'python developer',
        country = 'us',
        location = 'remote'
    WHERE id = 1
    """)
    conn.commit()
    conn.close()
    
    yield test_db_path
    
    # Restore original paths
    config.DB_PATH = orig_config_db
    database.DB_PATH = orig_database_db
    
    # Clean up test DB file after test runs
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass
