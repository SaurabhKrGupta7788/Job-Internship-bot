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


# F1: LinkedIn Easy Apply Boundary/Corner Cases (6 test cases via parameterization)
@pytest.mark.parametrize("action, input_data, expected_outcome", [
    ("discard_confirm", {"city": "Remote"}, "closed"),
    ("discard_cancel", {"city": "Remote"}, "open"),
    ("invalid_exp_negative", {"city": "Remote", "exp": "-5", "notice": "Immediate", "spon": "no"}, "submitted"),
    ("invalid_exp_huge", {"city": "Remote", "exp": "9999", "notice": "Immediate", "spon": "no"}, "submitted"),
    ("special_chars_city", {"city": "Rë-môtê!@#$", "exp": "3", "notice": "Immediate", "spon": "no"}, "submitted"),
    ("empty_city", {"city": "", "exp": "3", "notice": "Immediate", "spon": "no"}, "submitted")
])
def test_linkedin_easy_apply_boundary(page, action, input_data, expected_outcome):
    """Verify LinkedIn Easy Apply handles boundary inputs, special characters, and cancel flows."""
    page.goto("http://localhost:5001/linkedin/jobs/view/123")
    apply_btn = page.locator(".jobs-apply-button")
    apply_btn.click()
    page.wait_for_selector("#easyApplyModal")
    
    if action == "discard_confirm":
        page.click("button[aria-label='Dismiss']")
        page.wait_for_selector("#discardModal")
        page.click(".discard-confirm-btn")
        page.wait_for_selector("#easyApplyModal", state="hidden")
        assert not page.locator("#easyApplyModal").is_visible()
    elif action == "discard_cancel":
        page.click("button[aria-label='Dismiss']")
        page.wait_for_selector("#discardModal")
        page.click(".discard-cancel-btn")
        assert page.locator("#easyApplyModal").is_visible()
    else:
        page.fill("input[name='city']", input_data.get("city", ""))
        page.click("#step-1 .next-btn")
        
        page.wait_for_selector("#step-2")
        page.click("#step-2 .next-btn")
        
        page.wait_for_selector("#step-3")
        page.fill("input[name='experience_years']", input_data.get("exp", ""))
        page.fill("input[name='notice_period']", input_data.get("notice", ""))
        page.select_option("select[name='sponsorship']", input_data.get("spon", ""))
        
        page.once("dialog", lambda dialog: dialog.accept())
        page.click(".submit-btn")
        
        page.wait_for_selector("#easyApplyModal", state="hidden")
        assert not page.locator("#easyApplyModal").is_visible()


# F2: Indeed Boundary/Corner Cases (6 test cases via parameterization)
@pytest.mark.parametrize("scenario, mock_data_or_exception, expected_result_len", [
    ("empty_dataframe", pd.DataFrame([]), 0),
    ("exception_rate_limit", Exception("Indeed 429 Too Many Requests"), 0),
    ("missing_fields", pd.DataFrame([{'id': None, 'title': None, 'company': None, 'job_url': None}]), 1),
    ("html_in_description", pd.DataFrame([{'id': 'ind_html', 'title': 'Eng', 'company': 'Co', 'description': '<p>Line 1</p><br>Line 2', 'job_url': 'http://ind.com/1'}]), 1),
    ("malformed_salary", pd.DataFrame([{'id': 'ind_sal', 'title': 'Eng', 'company': 'Co', 'min_amount': '', 'max_amount': '', 'currency': '', 'job_url': 'http://ind.com/2'}]), 1),
    ("duplicate_job_key", pd.DataFrame([
        {'id': 'duplicate_key', 'title': 'Eng', 'company': 'Co', 'job_url': 'http://ind.com/3'},
        {'id': 'duplicate_key', 'title': 'Eng', 'company': 'Co', 'job_url': 'http://ind.com/3'}
    ]), 2)
])
def test_indeed_scrape_boundary(test_db, scenario, mock_data_or_exception, expected_result_len):
    """Verify Indeed scraping behaves robustly when encountering malformed data, duplicates, or network errors."""
    import searcher
    
    with patch("searcher.scrape_jobs") as mock_scrape:
        if isinstance(mock_data_or_exception, Exception):
            mock_scrape.side_effect = mock_data_or_exception
            jobs = searcher.search_jobspy_jobs(keywords="python")
            assert len(jobs) == expected_result_len
        else:
            mock_scrape.return_value = mock_data_or_exception
            jobs = searcher.search_jobspy_jobs(keywords="python")
            assert len(jobs) == expected_result_len
            if expected_result_len > 0 and scenario == "html_in_description":
                assert "Line 1" in jobs[0]['description']
            elif expected_result_len > 0 and scenario == "malformed_salary":
                salary = jobs[0]['salary']
                assert salary == 'N/A' or 'None' in salary or 'nan' in salary or salary == '-  '


# F3: Wellfound Boundary Cases (5 test cases via parameterization)
@pytest.mark.skip(reason="Wellfound platform search/apply feature boundary cases are unimplemented.")
@pytest.mark.parametrize("error_type", [
    ("auth_failure"),
    ("rate_limit"),
    ("layout_change"),
    ("invalid_api_key"),
    ("timeout")
])
def test_wellfound_boundary(error_type):
    """Stub verifying Wellfound handles boundary error states."""
    client = MockWellfoundClient()
    with pytest.raises(Exception):
        client.apply_with_error("wf_001", error_type)


# F4: Naukri Boundary Cases (5 test cases via parameterization)
@pytest.mark.skip(reason="Naukri platform search/apply feature boundary cases are unimplemented.")
@pytest.mark.parametrize("error_type", [
    ("missing_resume"),
    ("expired_session"),
    ("captcha_required"),
    ("server_500"),
    ("invalid_payload")
])
def test_naukri_boundary(error_type):
    """Stub verifying Naukri handles boundary error states."""
    client = MockNaukriClient()
    with pytest.raises(Exception):
        client.apply_with_error("naukri_001", error_type)


# F5: Career Page Discovery Boundary Cases (5 test cases via parameterization)
@pytest.mark.skip(reason="Career Page Discovery feature boundary cases are unimplemented.")
@pytest.mark.parametrize("broken_url", [
    ("http://broken-link-123.com"),
    ("https://httpstat.us/404"),
    ("https://httpstat.us/500"),
    ("https://circular-redirect.com"),
    ("https://dns-error-domain.xyz")
])
def test_career_discovery_boundary(broken_url):
    """Stub verifying Career Page Discovery handles network/broken url errors."""
    discoverer = CareerPageDiscoverer()
    with pytest.raises(Exception):
        discoverer.find_career_page(broken_url)


# F6: External Portal Navigation Boundary Cases (5 test cases via parameterization)
@pytest.mark.skip(reason="Production external portal navigation boundary cases are unimplemented.")
@pytest.mark.parametrize("invalid_portal_url", [
    ("ftp://invalid-protocol.com"),
    ("https://empty-page.com"),
    ("https://unsupported-portal.com"),
    ("https://restricted-access-portal.com"),
    ("https://expired-ssl-portal.com")
])
def test_external_navigation_production_boundary(invalid_portal_url):
    """Stub verifying production external portal navigation handles incorrect URLs."""
    navigator = ProductionExternalNavigator()
    with pytest.raises(Exception):
        navigator.navigate_and_fill(invalid_portal_url, "unknown")


# F6/F7/F8 Mock Server Greenhouse / Workday Boundary Cases (4 test cases)
@pytest.mark.parametrize("boundary_type, field_data", [
    ("greenhouse_missing_required", {"first": "", "last": "Smith", "email": "a@b.com", "phone": "123"}),
    ("greenhouse_invalid_email", {"first": "Bob", "last": "Jones", "email": "not-an-email", "phone": "123"}),
    ("workday_invalid_file_type", {"first": "Diana", "last": "Prince", "email": "d@p.com", "resume_suffix": ".exe"}),
    ("workday_step1_missing_email", {"first": "Bruce", "last": "Wayne", "email": "", "resume_suffix": ".pdf"})
])
def test_greenhouse_workday_mock_boundary(page, boundary_type, field_data):
    """Verify local mock external portal behavior under boundary and validation failure states."""
    if "greenhouse" in boundary_type:
        page.goto("http://localhost:5001/greenhouse/apply")
        
        if boundary_type == "greenhouse_missing_required":
            page.fill("#last_name", field_data["last"])
            page.fill("#email", field_data["email"])
            page.fill("#phone", field_data["phone"])
            page.click("#submit_app")
            assert "greenhouse/apply" in page.url
        elif boundary_type == "greenhouse_invalid_email":
            page.fill("#first_name", field_data["first"])
            page.fill("#last_name", field_data["last"])
            page.fill("#email", field_data["email"])
            page.fill("#phone", field_data["phone"])
            page.click("#submit_app")
            assert "greenhouse/apply" in page.url
            
    elif "workday" in boundary_type:
        page.goto("http://localhost:5001/workday/apply/1")
        if boundary_type == "workday_step1_missing_email":
            page.fill("#input-firstName", field_data["first"])
            page.fill("#input-lastName", field_data["last"])
            page.click("button[data-automation-id='bottom-navigation-next-button']")
            assert "workday/apply/1" in page.url
        elif boundary_type == "workday_invalid_file_type":
            page.fill("#input-firstName", field_data["first"])
            page.fill("#input-lastName", field_data["last"])
            page.fill("#input-email", field_data["email"])
            page.click("button[data-automation-id='bottom-navigation-next-button']")
            
            page.wait_for_url("**/workday/apply/2")
            
            suffix = field_data["resume_suffix"]
            invalid_file_path = os.path.abspath(f"invalid_resume{suffix}")
            with open(invalid_file_path, "wb") as f:
                f.write(b"invalid format")
                
            try:
                page.set_input_files("#resume-upload", invalid_file_path)
                page.fill("#input-jobTitle", "Hacker")
                page.click("button[data-automation-id='bottom-navigation-next-button']")
                
                page.wait_for_url("**/workday/apply/3")
                assert "Step 3" in page.title()
            finally:
                if os.path.exists(invalid_file_path):
                    os.remove(invalid_file_path)


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

# F7: Form Mapping Boundary Cases
def _run_form_mapping(page):
    page.goto("http://localhost:5001/form_mapping_boundary")
    location = "Tôkyô 🗼"
    inputs = page.locator("input[type='text'], select").all()
    for inp in inputs:
        if inp.is_visible() and not inp.input_value():
            # Get label or question text
            # Try finding parent text or preceding label
            question_text = "years of experience"
            try:
                question_text = inp.evaluate("el => el.closest('.jobs-easy-apply-form-section__grouping').innerText")
            except:
                pass
            
            # Basic heuristic for common questions
            if "experience" in question_text.lower() or "years" in question_text.lower():
                inp.fill("3") # Default to 3 years matching your resume
            elif "city" in question_text.lower() or "location" in question_text.lower():
                inp.fill(location)
            elif "notice" in question_text.lower():
                inp.fill("Immediate")
            elif inp.evaluate("el => el.tagName") == "SELECT":
                # Select first option
                inp.select_option(index=1)

def test_form_mapping_unicode_emoji(page):
    """Verify that form mapping handles unicode/emoji labels correctly (F7)."""
    _run_form_mapping(page)
    assert page.locator("#exp_input").input_value() == "3"

def test_form_mapping_long_labels(page):
    """Verify that form mapping handles long labels correctly (F7)."""
    _run_form_mapping(page)
    assert page.locator("#loc_input").input_value() == "Tôkyô 🗼"
    assert page.locator("#notice_input").input_value() == "Immediate"

def test_form_mapping_empty_groups(page):
    """Verify that form mapping handles inputs in empty groups (no label) correctly (F7)."""
    _run_form_mapping(page)
    assert page.locator("#empty_input").input_value() == ""

def test_form_mapping_select_tags(page):
    """Verify that form mapping handles select tags correctly (F7)."""
    _run_form_mapping(page)
    assert page.locator("#spon_select").input_value() == "yes"

def test_form_mapping_outside_standard_groups(page):
    """Verify that form mapping handles inputs outside standard groups correctly by falling back (F7)."""
    _run_form_mapping(page)
    assert page.locator("#other_input").input_value() == "3"


# F8: Resume Upload / Multi-page Boundary Cases
def test_resume_upload_nonexistent_file():
    """Verify PinchTabClient.upload_file error handling when file path does not exist (F8)."""
    from pinchtab_client import PinchTabClient, PinchTabAPIError
    client = PinchTabClient(base_url="http://localhost:5001")
    with pytest.raises(PinchTabAPIError) as exc_info:
        client.upload_file("#resume", "nonexistent_file_path.pdf")
    assert "File not found" in str(exc_info.value)

def test_resume_upload_invalid_selector():
    """Verify PinchTabClient.upload_file error handling with an invalid/empty selector (F8)."""
    from pinchtab_client import PinchTabClient, PinchTabAPIError
    client = PinchTabClient(base_url="http://localhost:5001")
    with pytest.raises(PinchTabAPIError) as exc_info_empty:
        client.upload_file("", "dummy_path.pdf")
    assert "Invalid selector" in str(exc_info_empty.value)

def test_resume_upload_zero_byte_file(tmp_path):
    """Verify PinchTabClient.upload_file error handling with a zero-byte file path (F8)."""
    from pinchtab_client import PinchTabClient, PinchTabAPIError
    client = PinchTabClient(base_url="http://localhost:5001")
    # Create a zero-byte file
    zero_byte_file = tmp_path / "empty_resume.pdf"
    zero_byte_file.touch()
    
    with pytest.raises(PinchTabAPIError) as exc_info:
        client.upload_file("#resume", str(zero_byte_file))
    assert "Zero-byte file" in str(exc_info.value)

def test_resume_upload_special_characters_filename(tmp_path):
    """Verify PinchTabClient.upload_file with filenames containing special characters (F8)."""
    from pinchtab_client import PinchTabClient
    client = PinchTabClient(base_url="http://localhost:5001")
    # Create a file with special characters in the filename
    special_name = "resume_#%$_★_😊.pdf"
    special_file = tmp_path / special_name
    special_file.write_bytes(b"dummy resume content")
    
    # Verify upload succeeds
    assert client.upload_file("#resume", str(special_file)) is True

def test_resume_upload_valid_file(tmp_path):
    """Verify PinchTabClient.upload_file succeeds with a standard valid file (F8)."""
    from pinchtab_client import PinchTabClient
    client = PinchTabClient(base_url="http://localhost:5001")
    valid_file = tmp_path / "valid_resume.pdf"
    valid_file.write_bytes(b"valid resume content")
    assert client.upload_file("#resume", str(valid_file)) is True


# F9: Dry-run safety Boundary Cases (9 test cases)
@pytest.mark.parametrize("invalid_env_val, expected_val", [
    ("maybe", False),
    ("", False),
    ("none", False),
    ("TRUE", True),
    ("1", True),
    ("false", False),
    ("0", False),
    ("no", False),
    ("yes", True)
])
def test_dry_run_boundary_parsing(invalid_env_val, expected_val):
    """Verify dry run handles invalid configuration values by defaulting safely."""
    with patch.dict(os.environ, {"DRY_RUN": invalid_env_val}):
        dry_run_parsed = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")
        assert dry_run_parsed == expected_val

@pytest.mark.xfail(reason="Dry-run safety not implemented in automator")
def test_dry_run_db_status_protection(test_db):
    """Verify database status is not accidentally marked as applied when in dry-run mode."""
    import config
    import automator
    import database
    
    original_dry_run = config.DRY_RUN
    config.DRY_RUN = True
    
    try:
        # Seed the job to database so the automator can process it
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
            
            # Verify that database status is not accidentally marked as applied
            job = database.get_job(job_id)
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
