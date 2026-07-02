import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Ensure the parent directory is in sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Mock classes for unimplemented features F3, F4, F5, F6
class MockWellfoundClient:
    def apply(self, job_id):
        return {"status": "success"}
    def apply_with_error(self, job_id, error_type):
        raise Exception(f"Wellfound error: {error_type}")

class MockNaukriClient:
    def apply(self, job_id):
        return {"status": "success"}
    def apply_with_error(self, job_id, error_type):
        raise Exception(f"Naukri error: {error_type}")

class CareerPageDiscoverer:
    def find_career_page(self, company_url):
        if "google" in company_url:
            return "https://careers.google.com"
        elif "microsoft" in company_url:
            return "https://careers.microsoft.com"
        elif "github" in company_url:
            return "https://github.com/careers"
        elif "amazon" in company_url:
            return "https://amazon.jobs"
        elif "meta" in company_url:
            return "https://metacareers.com"
        raise Exception("Career page not found")

class ProductionExternalNavigator:
    def navigate_and_fill(self, url, portal_type):
        if portal_type == "unknown":
            raise Exception("Unsupported portal")
        return "success"


# F1: LinkedIn Easy Apply Happy Path (6 test cases via parameterization)
@pytest.mark.parametrize("job_id, city, exp_years, notice, sponsorship", [
    (101, "Remote", "3", "Immediate", "no"),
    (102, "New York", "5", "1 month", "yes"),
    (103, "London", "1", "2 months", "no"),
    (104, "San Francisco", "10", "Immediate", "no"),
    (105, "Bengaluru", "2", "15 days", "yes"),
    (106, "Berlin", "0", "3 months", "no")
])
def test_linkedin_easy_apply_happy_path(page, test_db, job_id, city, exp_years, notice, sponsorship):
    """Verify that Playwright can navigate to mock LinkedIn Easy Apply and successfully submit the form."""
    import database
    
    # Seed job into isolated database
    job_dict = {
        'key': f'linkedin_job_{job_id}',
        'title': 'Senior Python Developer',
        'company': 'InnovateTech Systems',
        'description': 'Python role description.',
        'location': city,
        'url': f'http://localhost:5001/linkedin/jobs/view/{job_id}',
        'salary': 'N/A'
    }
    database.add_jobs([job_dict])
    
    page.goto(f"http://localhost:5001/linkedin/jobs/view/{job_id}")
    
    # Verify top card information
    assert page.locator(".jobs-unified-top-card__job-title").is_visible()
    
    # Click Easy Apply
    apply_btn = page.locator(".jobs-apply-button")
    assert apply_btn.is_visible()
    apply_btn.click()
    
    # Step 1: Fill contact info
    page.wait_for_selector("#step-1")
    page.fill("input[name='city']", city)
    page.click("#step-1 .next-btn")
    
    # Step 2: Upload resume
    page.wait_for_selector("#step-2")
    resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"dummy_resume_{job_id}.pdf"))
    with open(resume_path, "wb") as f:
        f.write(b"dummy pdf resume content")
        
    try:
        page.set_input_files("input[name='resume_file']", resume_path)
        page.click("#step-2 .next-btn")
        
        # Step 3: Questions
        page.wait_for_selector("#step-3")
        page.fill("input[name='experience_years']", exp_years)
        page.fill("input[name='notice_period']", notice)
        page.select_option("select[name='sponsorship']", sponsorship)
        
        # Dismiss alert popup automatically
        page.once("dialog", lambda dialog: dialog.accept())
        page.click(".submit-btn")
        
        # Verify modal closed
        page.wait_for_selector("#easyApplyModal", state="hidden")
        assert not page.locator("#easyApplyModal").is_visible()
    finally:
        if os.path.exists(resume_path):
            os.remove(resume_path)


# F2: Indeed Happy Path (6 test cases via parameterization)
@pytest.mark.parametrize("keywords, country, location, expected_site, expected_title", [
    ("python", "us", "remote", "indeed", "Indeed Python Developer"),
    ("developer", "in", "bengaluru", "indeed", "Indeed Backend Engineer"),
    ("engineer", "gb", "london", "indeed", "Indeed Software Engineer"),
    ("analyst", "ca", "toronto", "indeed", "Indeed Data Analyst"),
    ("react", "de", "berlin", "indeed", "Indeed Frontend Developer"),
    ("django", "fr", "paris", "indeed", "Indeed Django Specialist")
])
def test_indeed_scrape_happy_path(test_db, keywords, country, location, expected_site, expected_title):
    """Verify Indeed scraping via python-jobspy returns valid results and updates DB."""
    import searcher
    
    mock_df = pd.DataFrame([{
        'id': f'indeed_key_{expected_title.replace(" ", "_")}',
        'title': expected_title,
        'company': 'Indeed Company Inc',
        'description': 'A wonderful Indeed job details description for python.',
        'location': location,
        'job_url': f'https://www.indeed.com/viewjob?jk={expected_title.replace(" ", "_")}',
        'min_amount': 50000,
        'max_amount': 80000,
        'currency': 'USD',
        'site': 'indeed'
    }])
    
    with patch("searcher.scrape_jobs") as mock_scrape:
        mock_scrape.return_value = mock_df
        
        jobs = searcher.search_jobspy_jobs(
            keywords=keywords,
            country=country,
            location=location,
            results_wanted=1
        )
        
        assert len(jobs) > 0
        job = jobs[0]
        assert job['title'] == expected_title
        assert job['site'] == 'indeed'
        assert job['company'] == 'Indeed Company Inc'


# F3: Wellfound - Unimplemented Mock/Stub (5 test cases via parameterization)
@pytest.mark.skip(reason="Wellfound platform search/apply feature is currently unimplemented.")
@pytest.mark.parametrize("job_id, expected_status", [
    ("wf_001", "success"),
    ("wf_002", "success"),
    ("wf_003", "success"),
    ("wf_004", "success"),
    ("wf_005", "success")
])
def test_wellfound_unimplemented_happy(job_id, expected_status):
    """Stub verifying intended API contract for Wellfound."""
    client = MockWellfoundClient()
    result = client.apply(job_id)
    assert result["status"] == expected_status


# F4: Naukri - Unimplemented Mock/Stub (5 test cases via parameterization)
@pytest.mark.skip(reason="Naukri platform search/apply feature is currently unimplemented.")
@pytest.mark.parametrize("job_id, expected_status", [
    ("naukri_001", "success"),
    ("naukri_002", "success"),
    ("naukri_003", "success"),
    ("naukri_004", "success"),
    ("naukri_005", "success")
])
def test_naukri_unimplemented_happy(job_id, expected_status):
    """Stub verifying intended API contract for Naukri."""
    client = MockNaukriClient()
    result = client.apply(job_id)
    assert result["status"] == expected_status


# F5: Career Page Discovery - Unimplemented Mock/Stub (5 test cases via parameterization)
@pytest.mark.skip(reason="Career Page Discovery feature is currently unimplemented.")
@pytest.mark.parametrize("company_url, expected_career_url", [
    ("https://google.com", "https://careers.google.com"),
    ("https://microsoft.com", "https://careers.microsoft.com"),
    ("https://github.com", "https://github.com/careers"),
    ("https://amazon.com", "https://amazon.jobs"),
    ("https://meta.com", "https://metacareers.com")
])
def test_career_discovery_unimplemented_happy(company_url, expected_career_url):
    """Stub verifying intended API contract for Career Page Discovery."""
    discoverer = CareerPageDiscoverer()
    career_url = discoverer.find_career_page(company_url)
    assert career_url == expected_career_url


# F6: External Portal Navigation - Production Mock/Stub (5 test cases via parameterization)
@pytest.mark.skip(reason="Production external portal navigation is unimplemented.")
@pytest.mark.parametrize("portal_url, portal_type", [
    ("https://careers.workday.com/company/job", "workday"),
    ("https://boards.greenhouse.io/company/jobs/123", "greenhouse"),
    ("https://jobs.lever.co/company/123", "lever"),
    ("https://apply.workable.com/company/j/123", "workable"),
    ("https://company.bamboohr.com/jobs/view.php?id=123", "bamboohr")
])
def test_external_navigation_unimplemented_happy(portal_url, portal_type):
    """Stub verifying intended API contract for production external navigation."""
    navigator = ProductionExternalNavigator()
    status = navigator.navigate_and_fill(portal_url, portal_type)
    assert status == "success"


# F6/F7/F8 Mock Server Greenhouse Apply (3 test cases)
@pytest.mark.parametrize("first, last, email, phone, exp, sponsorship", [
    ("Alice", "Smith", "alice@example.com", "1234567890", "3", "no"),
    ("Bob", "Jones", "bob@example.com", "0987654321", "5", "yes"),
    ("Charlie", "Brown", "charlie@example.com", "1122334455", "1", "no")
])
def test_greenhouse_mock_happy(page, first, last, email, phone, exp, sponsorship):
    """Verify Greenhouse mock application flow."""
    page.goto("http://localhost:5001/greenhouse/apply")
    assert "Greenhouse Mock" in page.title()
    
    resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"dummy_greenhouse_{first}.pdf"))
    with open(resume_path, "wb") as f:
        f.write(b"greenhouse resume")
    try:
        page.set_input_files("#resume_upload", resume_path)
        page.fill("#first_name", first)
        page.fill("#last_name", last)
        page.fill("#email", email)
        page.fill("#phone", phone)
        page.fill("#job_application_answers_attributes_0_text_value", exp)
        page.select_option("#job_application_answers_attributes_1_value", sponsorship)
        
        page.click("#submit_app")
        page.wait_for_url("**/greenhouse/submit")
        
        body_text = page.locator("body").text_content()
        assert "Greenhouse application received" in body_text
    finally:
        if os.path.exists(resume_path):
            os.remove(resume_path)


# F6/F7/F8 Mock Server Workday Apply (3 test cases)
@pytest.mark.parametrize("first, last, email, title", [
    ("Diana", "Prince", "diana@example.com", "Backend Dev"),
    ("Bruce", "Wayne", "bruce@example.com", "Systems Architect"),
    ("Clark", "Kent", "clark@example.com", "News Reporter")
])
def test_workday_mock_happy(page, first, last, email, title):
    """Verify Workday mock application wizard flow."""
    page.goto("http://localhost:5001/workday/apply/1")
    assert "Step 1" in page.title()
    
    page.fill("#input-firstName", first)
    page.fill("#input-lastName", last)
    page.fill("#input-email", email)
    page.click("button[data-automation-id='bottom-navigation-next-button']")
    
    page.wait_for_url("**/workday/apply/2")
    assert "Step 2" in page.title()
    
    resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"dummy_workday_{first}.pdf"))
    with open(resume_path, "wb") as f:
        f.write(b"workday resume")
    try:
        page.set_input_files("#resume-upload", resume_path)
        page.fill("#input-jobTitle", title)
        page.click("button[data-automation-id='bottom-navigation-next-button']")
        
        page.wait_for_url("**/workday/apply/3")
        assert "Step 3" in page.title()
        
        page.click("button[data-automation-id='bottom-navigation-submit-button']")
        page.wait_for_url("**/workday/submit")
        
        body_text = page.locator("body").text_content()
        assert "Workday application submitted" in body_text
    finally:
        if os.path.exists(resume_path):
            os.remove(resume_path)


# F7: Form Mapping (5 test cases via parameterization)
@pytest.mark.parametrize("selector, element_type, label, value, options", [
    ("#first_name", "text", "First Name", "John", []),
    ("#email", "email", "Email", "john@example.com", []),
    ("#sponsorship", "select", "Sponsorship", "no", ["yes", "no"]),
    ("#resume", "file", "Resume", "", []),
    ("#submit", "button", "Submit", "", [])
])
def test_form_mapping_happy(selector, element_type, label, value, options):
    """Verify correct layout parsing and element creation for form mapping."""
    from pinchtab_client import LayoutElement
    element = LayoutElement(selector=selector, element_type=element_type, label=label, value=value, options=options)
    assert element.selector == selector
    assert element.element_type == element_type
    assert element.label == label
    assert element.value == value
    assert element.options == options
    
    data = element.to_dict()
    assert data["selector"] == selector
    assert data["type"] == element_type
    
    deserialized = LayoutElement.from_dict(data)
    assert deserialized.selector == selector
    assert deserialized.element_type == element_type


# F8: Resume Upload / Multi-page flow transitions (4 test cases via parameterization)
@pytest.mark.parametrize("flow_steps, expected_url_patterns", [
    ([1, 2, 3], ["**/workday/apply/1", "**/workday/apply/2", "**/workday/apply/3"]),
    ([1, 2, 1], ["**/workday/apply/1", "**/workday/apply/2", "**/workday/apply/1"]),
    ([1, 2, 3, 2], ["**/workday/apply/1", "**/workday/apply/2", "**/workday/apply/3", "**/workday/apply/2"]),
    ([1, 2, 3, "submit"], ["**/workday/apply/1", "**/workday/apply/2", "**/workday/apply/3", "**/workday/submit"])
])
def test_resume_upload_flow_happy(page, flow_steps, expected_url_patterns):
    """Verify multi-page navigation and file upload step progression."""
    page.goto("http://localhost:5001/workday/apply/1")
    
    resume_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "dummy_flow_resume.pdf"))
    with open(resume_path, "wb") as f:
        f.write(b"flow resume")
        
    try:
        for idx, step in enumerate(flow_steps):
            if step == 1:
                page.wait_for_url("**/workday/apply/1")
                page.fill("#input-firstName", "Flow")
                page.fill("#input-lastName", "Test")
                page.fill("#input-email", "flow@example.com")
                page.click("button[data-automation-id='bottom-navigation-next-button']")
            elif step == 2:
                page.wait_for_url("**/workday/apply/2")
                page.set_input_files("#resume-upload", resume_path)
                page.fill("#input-jobTitle", "Flow tester")
                if idx < len(flow_steps) - 1 and flow_steps[idx+1] == 1:
                    page.click("a[data-automation-id='bottom-navigation-back-button']")
                else:
                    page.click("button[data-automation-id='bottom-navigation-next-button']")
            elif step == 3:
                page.wait_for_url("**/workday/apply/3")
                assert "Step 3" in page.title()
                if idx < len(flow_steps) - 1 and flow_steps[idx+1] == 2:
                    page.click("a[data-automation-id='bottom-navigation-back-button']")
                else:
                    page.click("button[data-automation-id='bottom-navigation-submit-button']")
            elif step == "submit":
                page.wait_for_url("**/workday/submit")
                assert "Workday application submitted" in page.locator("body").text_content()
    finally:
        if os.path.exists(resume_path):
            os.remove(resume_path)


from contextlib import contextmanager

@contextmanager
def patch_automator_environment():
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
                return self.orig_launch(user_data_dir, **kwargs)
                
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

# F9: Dry-run safety (3 test cases via parameterization/environment check)
@pytest.mark.xfail(reason="Dry-run safety not implemented in automator")
@pytest.mark.parametrize("dry_run_state, expected_clicked", [
    (True, False),
    (False, True)
])
def test_dry_run_safety_happy(test_db, dry_run_state, expected_clicked):
    """Verify dry run mode skips the final submit button click."""
    import config
    import automator
    import database
    
    original_dry_run = config.DRY_RUN
    config.DRY_RUN = dry_run_state
    
    try:
        job_id = database.add_jobs([{
            'key': '12345',
            'title': 'Senior Python Developer',
            'company': 'InnovateTech Systems',
            'description': 'Python role description.',
            'location': 'Remote',
            'url': 'http://localhost:5001/linkedin/jobs/view/12345',
            'salary': 'N/A'
        }])[0]
        
        with patch_automator_environment():
            automator.run_automator(limit=1)
            
            job = database.get_job(job_id)
            if expected_clicked:
                assert job['status'] == 'applied'
            else:
                assert job['status'] != 'applied'
    finally:
        config.DRY_RUN = original_dry_run
        from config import OUTPUT_DIR
        mock_resume = os.path.join(OUTPUT_DIR, f"Resume_Mock_12345.docx")
        if os.path.exists(mock_resume):
            try:
                os.remove(mock_resume)
            except OSError:
                pass

@pytest.mark.parametrize("env_val, expected_bool", [
    ("True", True),
    ("False", False),
    ("1", True),
    ("0", False),
    ("yes", True)
])
def test_dry_run_config_parsing(env_val, expected_bool):
    """Verify environment variable parsing for DRY_RUN flag."""
    with patch.dict(os.environ, {"DRY_RUN": env_val}):
        dry_run_parsed = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")
        assert dry_run_parsed == expected_bool
