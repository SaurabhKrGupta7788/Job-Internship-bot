import os
import sqlite3
import requests

def test_health_check():
    """Verify mock server health endpoint is responding."""
    r = requests.get("http://localhost:5001/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_test_db_fixture(test_db):
    """Verify test database fixture initializes and seeds profile correctly."""
    assert os.path.exists(test_db)
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, email, phone FROM profile WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == 'Test Candidate'
    assert row[1] == 'test@example.com'
    assert row[2] == '+19999999999'

def test_playwright_linkedin_modal(page):
    """Verify playwright can navigate mock LinkedIn and open/interact with the Easy Apply modal."""
    page.goto("http://localhost:5001/linkedin/jobs/view/123")
    assert page.title() == "Mock LinkedIn Job View"
    
    # Verify job title and company are present
    assert page.locator(".jobs-unified-top-card__job-title").text_content().strip() == "Senior Python Developer"
    assert page.locator(".jobs-unified-top-card__company-name").text_content().strip() == "InnovateTech Systems"
    
    # Easy Apply button should be visible; click it
    apply_btn = page.locator(".jobs-apply-button")
    assert apply_btn.is_visible()
    apply_btn.click()
    
    # Modal should open
    page.wait_for_selector("#easyApplyModal")
    assert page.locator("#easyApplyModal").is_visible()
    
    # Fill step 1 and proceed
    page.fill("input[name='city']", "Remote")
    page.click("#step-1 .next-btn")
    
    # Step 2 should now be visible
    page.wait_for_selector("#step-2")
    assert page.locator("#step-2").is_visible()

def test_playwright_workday_wizard(page):
    """Verify Workday multi-page wizard flow and navigation."""
    resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "dummy_resume.pdf"))
    with open(resume_path, "wb") as f:
        f.write(b"dummy pdf content")
        
    try:
        page.goto("http://localhost:5001/workday/apply/1")
        assert "Step 1" in page.title()
        
        # Fill and submit step 1
        page.fill("#input-firstName", "Jane")
        page.fill("#input-lastName", "Doe")
        page.fill("#input-email", "jane.doe@example.com")
        page.click("button[data-automation-id='bottom-navigation-next-button']")
        
        # Wait for step 2 URL and page title
        page.wait_for_url("**/workday/apply/2")
        assert "Step 2" in page.title()
        assert page.locator("#resume-upload").is_visible()
        
        # Fill step 2 title, upload resume, and proceed
        page.fill("#input-jobTitle", "Python Automator")
        page.set_input_files("#resume-upload", resume_path)
        page.click("button[data-automation-id='bottom-navigation-next-button']")
        
        # Wait for step 3 URL and page title
        page.wait_for_url("**/workday/apply/3")
        assert "Step 3" in page.title()
        
        # Submit the form
        page.click("button[data-automation-id='bottom-navigation-submit-button']")
        
        # Wait for submission redirect / result
        page.wait_for_url("**/workday/submit")
        
        # Verify result content
        body_text = page.locator("body").text_content()
        assert "Workday application submitted" in body_text
    finally:
        if os.path.exists(resume_path):
            try:
                os.remove(resume_path)
            except OSError:
                pass

def test_playwright_greenhouse_form(page):
    """Verify Greenhouse single page long form load and structure."""
    page.goto("http://localhost:5001/greenhouse/apply")
    assert "Greenhouse Mock" in page.title()
    
    # Verify input fields exist and are visible
    assert page.locator("#resume_upload").is_visible()
    assert page.locator("#first_name").is_visible()
    assert page.locator("#last_name").is_visible()
    assert page.locator("#email").is_visible()
    assert page.locator("#phone").is_visible()
    assert page.locator("#job_application_answers_attributes_0_text_value").is_visible()
    assert page.locator("#job_application_answers_attributes_1_value").is_visible()

def test_automator_import():
    """Verify automator can be imported and run_automator exists."""
    import sys
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        
    import automator
    assert hasattr(automator, "run_automator")
    assert callable(automator.run_automator)
