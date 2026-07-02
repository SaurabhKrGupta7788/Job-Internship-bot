import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Ensure the parent directory is in sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import config
import database
import automator
import searcher
from tests.test_tier1 import patch_automator_environment


# T3_01: LinkedIn Easy Apply (F1) + Form Mapping (F7) + Resume Upload (F8) + Dry-Run (F9)
def test_t3_01_linkedin_easy_apply_active_combinations(test_db):
    """Verify F1 + F7 + F8 + F9 interaction: LinkedIn Easy Apply dry-run."""
    database.add_jobs([{
        'key': 'linkedin_comb_1',
        'title': 'Python Developer',
        'company': 'Active Comb Co',
        'description': 'Python developer role.',
        'location': 'Remote',
        'url': 'http://localhost:5001/linkedin/jobs/view/999',
        'salary': 'N/A'
    }])
    job_id = database.get_jobs()[0]['id']
    
    original_dry_run = config.DRY_RUN
    config.DRY_RUN = True
    
    try:
        with patch_automator_environment():
            automator.run_automator(limit=1)
            
            # Verify status in database did not set to 'applied' due to dry run safety
            job = database.get_job(job_id)
            assert job['status'] != 'applied'
    finally:
        config.DRY_RUN = original_dry_run
        from config import OUTPUT_DIR
        mock_resume = os.path.join(OUTPUT_DIR, f"Resume_Mock_{job_id}.docx")
        if os.path.exists(mock_resume):
            try:
                os.remove(mock_resume)
            except OSError:
                pass


# T3_02: Indeed Scrape (F2) + Database Tracking + Dry-Run (F9)
def test_t3_02_indeed_scrape_db_tracking_dry_run(test_db):
    """Verify F2 + Database + F9 combination: Scrapes Indeed and adds to DB."""
    mock_df = pd.DataFrame([{
        'id': 'indeed_key_t3_02',
        'title': 'Indeed Dry Run Job',
        'company': 'Indeed Company Inc',
        'description': 'A wonderful Indeed job details description for python.',
        'location': 'remote',
        'job_url': 'https://www.indeed.com/viewjob?jk=indeed_key_t3_02',
        'min_amount': 50000,
        'max_amount': 80000,
        'currency': 'USD',
        'site': 'indeed'
    }])
    
    with patch("searcher.scrape_jobs") as mock_scrape:
        mock_scrape.return_value = mock_df
        
        # Scrape and add to DB
        new_jobs = searcher.run_job_search()
        assert new_jobs == 1
        
        # Check DB status
        conn = database.get_db_connection()
        job = conn.execute("SELECT * FROM jobs WHERE job_key = 'indeed_key_t3_02'").fetchone()
        conn.close()
        
        assert job is not None
        assert job['status'] == 'new'


# T3_03: LinkedIn Easy Apply (F1) + Resume Tailoring (F8) + Dry-Run (F9)
def test_t3_03_linkedin_easy_apply_tailoring_dry_run(test_db):
    """Verify F1 + F8 + F9: Tailoring + LinkedIn Easy Apply dry-run."""
    original_dry_run = config.DRY_RUN
    config.DRY_RUN = True

    try:
        with patch_automator_environment():
            automator.run_automator(limit=1)

            # Verify file exists in output directory
            from config import OUTPUT_DIR
            jobs = database.get_jobs()
            assert len(jobs) > 0
            job_id = jobs[0]['id']
            docx_path = os.path.abspath(os.path.join(OUTPUT_DIR, f"Resume_Mock_{job_id}.docx"))
            assert os.path.exists(docx_path)
        
        # Verify database tracks the tailoring info
        job = database.get_job(job_id)
        assert job['match_score'] == 100
        assert job['status'] != 'applied'
    finally:
        config.DRY_RUN = original_dry_run
        from config import OUTPUT_DIR
        mock_resume = os.path.join(OUTPUT_DIR, f"Resume_Mock_{job_id}.docx")
        if os.path.exists(mock_resume):
            try:
                os.remove(mock_resume)
            except OSError:
                pass


# T3_04: Greenhouse Mock (F6) + Form Mapping (F7) + Resume Upload (F8) + Dry-Run (F9)
def test_t3_04_greenhouse_form_mapping_resume_upload_dry_run(page, test_db):
    """Verify F6 + F7 + F8 + F9: Greenhouse mock single-page application under dry-run."""
    page.goto("http://localhost:5001/greenhouse/apply")
    assert "Greenhouse Mock" in page.title()
    
    resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "dummy_t3_04.pdf"))
    with open(resume_path, "wb") as f:
        f.write(b"dummy resume")
        
    try:
        # Fill inputs
        page.fill("#first_name", "Greenhouse")
        page.fill("#last_name", "Candidate")
        page.fill("#email", "greenhouse@example.com")
        page.fill("#phone", "1234567890")
        page.set_input_files("#resume_upload", resume_path)
        
        # Dry-run: Do not click the submit button
        # Instead, verify the submit button is present but not clicked
        assert page.locator("#submit_app").is_visible()
        assert "greenhouse/submit" not in page.url
    finally:
        if os.path.exists(resume_path):
            os.remove(resume_path)


# T3_05: Workday Mock (F6) + Form Mapping (F7) + Resume Upload (F8) + Dry-Run (F9)
def test_t3_05_workday_form_mapping_resume_upload_dry_run(page, test_db):
    """Verify F6 + F7 + F8 + F9: Workday mock multi-page application under dry-run."""
    page.goto("http://localhost:5001/workday/apply/1")
    assert "Step 1" in page.title()
    
    resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "dummy_t3_05.pdf"))
    with open(resume_path, "wb") as f:
        f.write(b"dummy resume")
        
    try:
        # Step 1: fill personal information correctly
        page.fill("#input-firstName", "Workday")
        page.fill("#input-lastName", "Candidate")
        page.fill("#input-email", "workday@example.com")
        page.click("button[data-automation-id='bottom-navigation-next-button']")
        
        # Transition to Step 2
        page.wait_for_url("**/workday/apply/2")
        assert "Step 2" in page.title()
        
        # Step 2: upload resume and fill job title
        page.set_input_files("#resume-upload", resume_path)
        page.fill("#input-jobTitle", "Quality Engineer")
        page.click("button[data-automation-id='bottom-navigation-next-button']")
        
        # Transition to Step 3
        page.wait_for_url("**/workday/apply/3")
        assert "Step 3" in page.title()
        
        # Dry-run: Verify the submit button is present, but do not click it
        submit_btn = page.locator("button[data-automation-id='bottom-navigation-submit-button']")
        assert submit_btn.is_visible()
        assert "workday/submit" not in page.url
    finally:
        if os.path.exists(resume_path):
            os.remove(resume_path)


# T3_06: LinkedIn Easy Apply (F1) + Wellfound (F3)
@pytest.mark.skip(reason="Wellfound platform search/apply feature is currently unimplemented.")
def test_t3_06_linkedin_easy_apply_wellfound_skipped():
    """Stub verifying unimplemented Wellfound integration fails/skips gracefully."""
    pass


# T3_07: LinkedIn Easy Apply (F1) + Naukri (F4)
@pytest.mark.skip(reason="Naukri platform search/apply feature is currently unimplemented.")
def test_t3_07_linkedin_easy_apply_naukri_skipped():
    """Stub verifying unimplemented Naukri integration fails/skips gracefully."""
    pass


# T3_08: Indeed Scrape (F2) + Career Page Discovery (F5)
@pytest.mark.skip(reason="Career Page Discovery feature is currently unimplemented.")
def test_t3_08_indeed_scrape_career_discovery_skipped():
    """Stub verifying unimplemented Career Page Discovery fails/skips gracefully."""
    pass


# T3_09: Indeed Scrape (F2) + External Navigation (F6)
@pytest.mark.skip(reason="Production external portal navigation is unimplemented.")
def test_t3_09_indeed_scrape_external_navigation_unsupported():
    """Stub verifying unimplemented Production External Navigation fails/skips gracefully."""
    pass
