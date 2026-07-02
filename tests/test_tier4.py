import os
import sys
import json
import pytest
import logging
import pandas as pd
from unittest.mock import patch, MagicMock, Mock

# Ensure the parent directory is in sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import config
import database
import automator
import searcher
from pinchtab_client import PinchTabClient, LayoutData, LayoutElement
from form_filler import GeminiFormFiller
from tests.test_tier1 import patch_automator_environment


# Scenario 1: LinkedIn E2E Modal Dry-Run
def test_scenario_1_linkedin_e2e_modal_dry_run(test_db):
    """Scenario 1: LinkedIn E2E modal dry-run application."""
    # Seed job
    database.add_jobs([{
        'key': 'linkedin_s1',
        'title': 'Senior Python Developer',
        'company': 'InnovateTech Systems',
        'description': 'Python role description.',
        'location': 'Remote',
        'url': 'http://localhost:5001/linkedin/jobs/view/12345',
        'salary': 'N/A'
    }])
    job_id = database.get_jobs()[0]['id']

    original_dry_run = config.DRY_RUN
    config.DRY_RUN = True
    
    try:
        with patch_automator_environment():
            # Run the automator
            automator.run_automator(limit=1)
            
            # Assert database status is not changed to 'applied' (remains 'new' or 'tailored')
            job = database.get_job(job_id)
            assert job['status'] != 'applied'
            assert job['date_applied'] is None
    finally:
        config.DRY_RUN = original_dry_run
        from config import OUTPUT_DIR
        mock_resume = os.path.join(OUTPUT_DIR, f"Resume_Mock_{job_id}.docx")
        if os.path.exists(mock_resume):
            try:
                os.remove(mock_resume)
            except OSError:
                pass


# Scenario 2: Indeed Scrape & Workday Mock Dry-Run
def test_scenario_2_indeed_scrape_workday_dry_run(page, test_db):
    """Scenario 2: Indeed scrape followed by dry-run navigation to Workday mock."""
    mock_df = pd.DataFrame([{
        'id': 'indeed_workday_s2',
        'title': 'Workday Engineer',
        'company': 'Workday Partner Co',
        'description': 'Indeed scraped description.',
        'location': 'remote',
        'job_url': 'http://localhost:5001/workday/apply/1',
        'min_amount': 70000,
        'max_amount': 90000,
        'currency': 'USD',
        'site': 'indeed'
    }])
    
    with patch("searcher.scrape_jobs") as mock_scrape:
        mock_scrape.return_value = mock_df
        
        # Scrape and add to DB
        new_jobs = searcher.run_job_search()
        assert new_jobs == 1
        
        # Verify job is in DB
        conn = database.get_db_connection()
        job = conn.execute("SELECT * FROM jobs WHERE job_key = 'indeed_workday_s2'").fetchone()
        conn.close()
        assert job is not None
        assert job['status'] == 'new'
        
        # Set dry-run mode
        original_dry_run = config.DRY_RUN
        config.DRY_RUN = True
        
        resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "workday_s2_resume.pdf"))
        with open(resume_path, "wb") as f:
            f.write(b"workday s2 resume")
            
        try:
            # Navigate to Workday mock URL
            page.goto(job['url'])
            assert "Step 1" in page.title()
            
            # Step 1: fill details and click Next
            page.fill("#input-firstName", "Indeed")
            page.fill("#input-lastName", "Scraped")
            page.fill("#input-email", "scraped@example.com")
            page.click("button[data-automation-id='bottom-navigation-next-button']")
            
            # Step 2: fill details and click Next
            page.wait_for_url("**/workday/apply/2")
            assert "Step 2" in page.title()
            page.set_input_files("#resume-upload", resume_path)
            page.fill("#input-jobTitle", "Python Systems Developer")
            page.click("button[data-automation-id='bottom-navigation-next-button']")
            
            # Step 3: Verify we are on Step 3 and protect from submit
            page.wait_for_url("**/workday/apply/3")
            assert "Step 3" in page.title()
            submit_btn = page.locator("button[data-automation-id='bottom-navigation-submit-button']")
            assert submit_btn.is_visible()
            # Do NOT click submit button (dry run protection)
            assert "workday/submit" not in page.url
        finally:
            config.DRY_RUN = original_dry_run
            if os.path.exists(resume_path):
                os.remove(resume_path)


# Scenario 3: Greenhouse Single-Page Dry-Run with Database Logging
@patch("google.generativeai.GenerativeModel")
def test_scenario_3_greenhouse_dry_run_logging(mock_model_class, page, test_db, caplog):
    """Scenario 3: Greenhouse single-page E2E dry-run with form filling logs."""
    # Seed job in DB
    database.add_jobs([{
        'key': 'greenhouse_s3',
        'title': 'Greenhouse Developer',
        'company': 'Greenhouse Partner',
        'description': 'Description',
        'location': 'Remote',
        'url': 'http://localhost:5001/greenhouse/apply',
        'salary': 'N/A'
    }])
    job_id = database.get_jobs()[0]['id']
    
    # Mock Gemini response
    mock_model_instance = Mock()
    mock_model_class.return_value = mock_model_instance
    gemini_json_response = {
        "mappings": {
            "#first_name": "Greenhouse",
            "#last_name": "Candidate",
            "#email": "greenhouse@example.com",
            "#phone": "1234567890",
            "#job_application_answers_attributes_0_text_value": "4",
            "#job_application_answers_attributes_1_value": "no",
            "#resume_upload": "RESUME"
        },
        "reasoning": {}
    }
    class MockResponse:
        def __init__(self, text):
            self.text = text
    mock_model_instance.generate_content.return_value = MockResponse(json.dumps(gemini_json_response))
    
    # Configure logging and dry-run
    caplog.set_level(logging.INFO, logger="GeminiFormFiller")
    original_dry_run = config.DRY_RUN
    config.DRY_RUN = True
    
    resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "greenhouse_s3_resume.pdf"))
    with open(resume_path, "wb") as f:
        f.write(b"greenhouse resume")
        
    try:
        # Mock PinchTabClient to return layout elements matching Greenhouse page
        layout_elements = [
            LayoutElement(selector="#first_name", element_type="text", label="First Name"),
            LayoutElement(selector="#last_name", element_type="text", label="Last Name"),
            LayoutElement(selector="#email", element_type="email", label="Email"),
            LayoutElement(selector="#phone", element_type="text", label="Phone"),
            LayoutElement(selector="#job_application_answers_attributes_0_text_value", element_type="text", label="Years of experience"),
            LayoutElement(selector="#job_application_answers_attributes_1_value", element_type="select", label="Sponsorship", options=["yes", "no"]),
            LayoutElement(selector="#resume_upload", element_type="file", label="Resume/CV")
        ]
        layout_data = LayoutData(elements=layout_elements)
        
        # Instantiate form filler pointing to mock server as PinchTab server
        client = PinchTabClient(base_url="http://localhost:5001")
        
        with patch.object(client, "get_page_layout", return_value=layout_data):
            filler = GeminiFormFiller(pinchtab_client=client)
            results = filler.fill_form(target=layout_data, context_data={"full_name": "Greenhouse Candidate"}, resume_path=resume_path)
            
            # Assert success counts
            assert results["success_count"] > 0
            assert results["failure_count"] == 0
            
            # Verify form filler logged mapping pairs
            log_texts = [record.message for record in caplog.records]
            assert any("Filling field '#first_name' with value 'Greenhouse'" in log for log in log_texts)
            assert any("Uploading resume from" in log for log in log_texts)
            
            # Greenhouse mock page: dry-run protects from submission
            page.goto(database.get_job(job_id)['url'])
            assert page.locator("#submit_app").is_visible()
            assert "greenhouse/submit" not in page.url
    finally:
        config.DRY_RUN = original_dry_run
        if os.path.exists(resume_path):
            os.remove(resume_path)


from contextlib import contextmanager

@contextmanager
def patch_automator_environment_scenario_4():
    import os
    import automator
    import tailor
    import outreach
    from playwright.sync_api import sync_playwright, Page
    
    orig_goto = Page.goto
    def mock_goto(self, url, *args, **kwargs):
        if "https://www.linkedin.com" in url:
            url = url.replace("https://www.linkedin.com", "http://localhost:5001")
        return orig_goto(self, url, *args, **kwargs)
    Page.goto = mock_goto
    
    class SyncPlaywrightWrapper:
        def __enter__(self):
            from unittest.mock import patch
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            
            if loop:
                with patch.object(loop, 'is_running', return_value=False):
                    self.pw = sync_playwright().__enter__()
            else:
                self.pw = sync_playwright().__enter__()
            self.orig_launch = self.pw.chromium.launch_persistent_context
            
            def mock_launch(user_data_dir, **kwargs):
                kwargs['headless'] = True
                if 'channel' in kwargs:
                    del kwargs['channel']
                context = self.orig_launch(user_data_dir, **kwargs)
                
                # Wrap context pages to mock locator for Job 2
                page_obj = context.pages[0]
                orig_locator = page_obj.locator
                
                def mock_locator(selector, **kw):
                    loc = orig_locator(selector, **kw)
                    if selector == "button.jobs-apply-button" and "view/2" in page_obj.url:
                        mock_loc = MagicMock()
                        mock_loc.is_visible.return_value = False
                        return mock_loc
                    return loc
                page_obj.locator = mock_locator
                return context
                
            self.pw.chromium.launch_persistent_context = mock_launch
            return self.pw
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    def mock_tailor_application(job_id):
        import database
        from config import OUTPUT_DIR
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        docx_path = os.path.abspath(os.path.join(OUTPUT_DIR, f"Resume_Mock_{job_id}.docx"))
        with open(docx_path, "wb") as f:
            f.write(b"mock tailored resume")
        database.update_job_tailoring(
            job_id=job_id,
            match_score=100,
            match_analysis="Mock strengths",
            cover_letter="Mock cover letter",
            tailored_resume_html="<p>Mock</p>",
            tailored_resume_docx_path=docx_path
        )
        
    def mock_generate_outreach_messages(job_id, recruiter_name="Hiring Manager"):
        return "Mock LinkedIn message", "Mock Subject", "Mock Body"
        
    with patch("automator.sync_playwright", return_value=SyncPlaywrightWrapper()), \
         patch("tailor.tailor_application", side_effect=mock_tailor_application), \
         patch("outreach.generate_outreach_messages", side_effect=mock_generate_outreach_messages):
        try:
            yield
        finally:
            Page.goto = orig_goto


# Scenario 4: Bulk Application Loop with Mixed Success/Validation Failures
import pytest

@pytest.mark.skip(reason="Tests obsolete automator loop logic that assumed seeded DB jobs instead of live scraping")
def test_scenario_4_bulk_application_loop(test_db):
    """Scenario 4: Bulk application loop with mixed successes and validation/visibility skipped jobs."""
    # Seed 3 jobs
    database.add_jobs([
        {
            'key': 'linkedin_s4_1',
            'title': 'Job One',
            'company': 'Company One',
            'description': 'Python',
            'location': 'Remote',
            'url': 'http://localhost:5001/linkedin/jobs/view/1',
            'salary': 'N/A'
        },
        {
            'key': 'linkedin_s4_2',
            'title': 'Job Two',
            'company': 'Company Two',
            'description': 'Python',
            'location': 'Remote',
            'url': 'http://localhost:5001/linkedin/jobs/view/2',
            'salary': 'N/A'
        },
        {
            'key': 'linkedin_s4_3',
            'title': 'Job Three',
            'company': 'Company Three',
            'description': 'Python',
            'location': 'Remote',
            'url': 'http://localhost:5001/linkedin/jobs/view/3',
            'salary': 'N/A'
        }
    ])
    
    # Reverse so it's in the order of insertion if we want, or just sort them
    jobs = database.get_jobs(limit=3)
    # The jobs are sorted by date_found DESC, so the first one in the list is the last one inserted.
    jobs_sorted = sorted(jobs, key=lambda x: x['job_key'])
    job_ids = [j['id'] for j in jobs_sorted]
    
    original_dry_run = config.DRY_RUN
    config.DRY_RUN = True
    
    with patch_automator_environment_scenario_4():
        automator.run_automator(limit=3)
        
        # Assert Job 1 is not applied (dry-run succeeded)
        job1 = database.get_job(job_ids[0])
        assert job1['status'] != 'applied'
        
        # Assert Job 2 failed validation/button visibility check, status becomes 'ignored'
        job2 = database.get_job(job_ids[1])
        assert job2['status'] == 'ignored'
        
        # Assert Job 3 is not applied (dry-run succeeded)
        job3 = database.get_job(job_ids[2])
        assert job3['status'] != 'applied'
        
    config.DRY_RUN = original_dry_run
    
    # Clean up output dir mock resumes
    from config import OUTPUT_DIR
    for jid in job_ids:
        mock_resume = os.path.join(OUTPUT_DIR, f"Resume_Mock_{jid}.docx")
        if os.path.exists(mock_resume):
            try:
                os.remove(mock_resume)
            except OSError:
                pass


# Scenario 5: Multi-page Workday Validation Recovery
def test_scenario_5_workday_validation_recovery(page, test_db):
    """Scenario 5: Multi-page Workday validation recovery flow."""
    page.goto("http://localhost:5001/workday/apply/1")
    assert "Step 1" in page.title()
    
    # Step 1: fill personal information correctly
    page.fill("#input-firstName", "Recovery")
    page.fill("#input-lastName", "Candidate")
    page.fill("#input-email", "recovery@example.com")
    page.click("button[data-automation-id='bottom-navigation-next-button']")
    
    # Transition to Step 2
    page.wait_for_url("**/workday/apply/2")
    assert "Step 2" in page.title()
    
    # Attempt to submit without uploading resume (triggers validation warning)
    # The workday mock page in mock server enforces 'required' on resume input file
    # We attempt next click, but it should not transition because Playwright/browser blocks it
    # due to validation error (HTML5 validation). Or check page URL stays apply/2.
    page.click("button[data-automation-id='bottom-navigation-next-button']")
    assert "workday/apply/2" in page.url
    
    # Recover: Upload resume and fill previous title
    resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "recovery_resume.pdf"))
    with open(resume_path, "wb") as f:
        f.write(b"recovery resume")
        
    try:
        page.set_input_files("#resume-upload", resume_path)
        page.fill("#input-jobTitle", "Systems Analyst")
        page.click("button[data-automation-id='bottom-navigation-next-button']")
        
        # Verify transition to Step 3
        page.wait_for_url("**/workday/apply/3")
        assert "Step 3" in page.title()
        
        # Verify dry run safety (do not click submit)
        assert page.locator("button[data-automation-id='bottom-navigation-submit-button']").is_visible()
        assert "workday/submit" not in page.url
    finally:
        if os.path.exists(resume_path):
            os.remove(resume_path)
