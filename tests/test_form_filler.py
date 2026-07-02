import os
import json
import tempfile
import pytest
from unittest.mock import Mock, patch

import config
import database
from pinchtab_client import LayoutData, LayoutElement, PinchTabClient
from form_filler import GeminiFormFiller

class MockResponse:
    def __init__(self, text):
        self.text = text

def test_init_without_api_key():
    """Verify that initialization raises ValueError if GEMINI_API_KEY is not provided or set."""
    with patch("config.GEMINI_API_KEY", None):
        with pytest.raises(ValueError) as excinfo:
            GeminiFormFiller(api_key=None)
        assert "GEMINI_API_KEY is not set" in str(excinfo.value)

def test_prune_elements():
    """Verify that prune_elements filters out non-fillable elements correctly."""
    elements = [
        LayoutElement(selector="#first_name", element_type="text", label="First Name"),
        LayoutElement(selector="#submit_btn", element_type="button", label="Submit"),
        LayoutElement(selector="#hidden_id", element_type="hidden", label="ID"),
        LayoutElement(selector="#sponsorship", element_type="select", label="Sponsorship Needed", options=["Yes", "No"]),
        LayoutElement(selector="#resume", element_type="file", label="Resume")
    ]
    with patch("config.GEMINI_API_KEY", "dummy_key"):
        filler = GeminiFormFiller()
        pruned = filler.prune_elements(elements)
        
        # Verify length and type exclusion
        assert len(pruned) == 3
        selectors = [e["selector"] for e in pruned]
        assert "#first_name" in selectors
        assert "#sponsorship" in selectors
        assert "#resume" in selectors
        assert "#submit_btn" not in selectors
        assert "#hidden_id" not in selectors

@patch("google.generativeai.GenerativeModel")
def test_map_fields_and_fuzzy_matching(mock_model_class):
    """Verify that map_fields correctly interacts with Gemini, does fuzzy option matching and exact mapping."""
    # Setup Mock Model
    mock_model_instance = Mock()
    mock_model_class.return_value = mock_model_instance
    
    # Gemini response with some options matching perfectly, some fuzzy, and some not matching
    gemini_json_response = {
        "mappings": {
            "#first_name": "Alice",
            "#sponsorship": "no",
            "#gender": "Female",
            "#veteran": "Not a veteran"
        },
        "reasoning": {
            "#first_name": "From full name",
            "#sponsorship": "Profile indicates authorization",
            "#gender": "Matches female",
            "#veteran": "No military history"
        }
    }
    mock_model_instance.generate_content.return_value = MockResponse(json.dumps(gemini_json_response))

    # Layout elements including select elements with option lists
    layout = LayoutData(elements=[
        LayoutElement(selector="#first_name", element_type="text", label="First Name"),
        LayoutElement(selector="#sponsorship", element_type="select", label="Require sponsorship?", options=["Yes", "No, I do not"]),
        LayoutElement(selector="#gender", element_type="select", label="Gender", options=["Male", "Female", "Prefer not to say"]),
        LayoutElement(selector="#veteran", element_type="select", label="Veteran Status", options=["Yes", "No"])
    ])
    
    profile = {"full_name": "Alice Smith", "base_resume": "{}"}

    with patch("config.GEMINI_API_KEY", "dummy_key"):
        filler = GeminiFormFiller()
        res = filler.map_fields(layout, profile)
        
        # Verify mappings resolved
        mappings = res["mappings"]
        assert mappings["#first_name"] == "Alice"
        
        # Verify fuzzy matching
        # "no" should match "No, I do not"
        assert mappings["#sponsorship"] == "No, I do not"
        
        # "Female" (exact match) should remain "Female"
        assert mappings["#gender"] == "Female"
        
        # "Not a veteran" does not match "Yes" or "No", so it should resolve to None
        assert mappings["#veteran"] is None

        # Verify generate_mappings list output
        list_res = filler.generate_mappings(layout, profile)
        assert "mappings" in list_res
        assert isinstance(list_res["mappings"], list)
        assert len(list_res["mappings"]) == 4

@patch("google.generativeai.GenerativeModel")
def test_fill_form_mode2_basic(mock_model_class):
    """Verify that fill_form in Mode 2 works with text inputs using mocked PinchTabClient."""
    mock_model_instance = Mock()
    mock_model_class.return_value = mock_model_instance
    
    gemini_json_response = {
        "mappings": {
            "#first_name": "Alice",
            "#phone": "+19999999999"
        },
        "reasoning": {}
    }
    mock_model_instance.generate_content.return_value = MockResponse(json.dumps(gemini_json_response))

    # Mock PinchTabClient
    mock_client = Mock(spec=PinchTabClient)
    mock_client.fill_field.return_value = True

    layout = LayoutData(elements=[
        LayoutElement(selector="#first_name", element_type="text", label="First Name"),
        LayoutElement(selector="#phone", element_type="text", label="Phone")
    ])
    profile = {"full_name": "Alice Smith"}

    with patch("config.GEMINI_API_KEY", "dummy_key"):
        filler = GeminiFormFiller(pinchtab_client=mock_client)
        results = filler.fill_form(layout, profile)

        # Assert correct methods were called on the client
        mock_client.fill_field.assert_any_call("#first_name", "Alice")
        mock_client.fill_field.assert_any_call("#phone", "+19999999999")
        
        # Assert returns have summary metrics and status per selector
        assert results["success_count"] == 2
        assert results["failure_count"] == 0
        assert results["#first_name"] is True
        assert results["#phone"] is True

@patch("google.generativeai.GenerativeModel")
def test_fill_form_mode2_uploads(mock_model_class):
    """Verify that RESUME and COVER_LETTER uploads and text fillings work in Mode 2."""
    mock_model_instance = Mock()
    mock_model_class.return_value = mock_model_instance
    
    gemini_json_response = {
        "mappings": {
            "#resume": "RESUME",
            "#cover_letter_file": "COVER_LETTER",
            "#cover_letter_text": "COVER_LETTER"
        },
        "reasoning": {}
    }
    mock_model_instance.generate_content.return_value = MockResponse(json.dumps(gemini_json_response))

    mock_client = Mock(spec=PinchTabClient)
    mock_client.upload_file.return_value = True
    mock_client.fill_field.return_value = True

    layout = LayoutData(elements=[
        LayoutElement(selector="#resume", element_type="file", label="Resume"),
        LayoutElement(selector="#cover_letter_file", element_type="file", label="Cover Letter"),
        LayoutElement(selector="#cover_letter_text", element_type="textarea", label="Cover Letter Text")
    ])
    profile = {"full_name": "Alice Smith"}

    # Create temporary files for uploads
    resume_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    resume_path = resume_file.name
    resume_file.close()

    cl_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
    cl_file.write(b"This is my cover letter content.")
    cl_file.close()
    cover_letter_path = cl_file.name

    try:
        with patch("config.GEMINI_API_KEY", "dummy_key"):
            filler = GeminiFormFiller(pinchtab_client=mock_client)
            results = filler.fill_form(
                layout, 
                profile, 
                resume_path=resume_path, 
                cover_letter_path=cover_letter_path
            )

            # Verify uploads called with correct paths
            mock_client.upload_file.assert_any_call("#resume", resume_path)
            mock_client.upload_file.assert_any_call("#cover_letter_file", cover_letter_path)
            
            # Verify cover letter pasting called with text content read from file
            mock_client.fill_field.assert_any_call("#cover_letter_text", "This is my cover letter content.")
            
            assert results["success_count"] == 3
            assert results["failure_count"] == 0
    finally:
        # Clean up temp files
        os.remove(resume_path)
        os.remove(cover_letter_path)

@patch("google.generativeai.GenerativeModel")
def test_fill_form_mode1_db(mock_model_class, test_db):
    """Verify Mode 1 filling retrieves profile/job data and falls back to database cover letter."""
    mock_model_instance = Mock()
    mock_model_class.return_value = mock_model_instance
    
    gemini_json_response = {
        "mappings": {
            "#name": "Test Candidate",
            "#resume": "RESUME",
            "#cl_text": "COVER_LETTER"
        },
        "reasoning": {}
    }
    mock_model_instance.generate_content.return_value = MockResponse(json.dumps(gemini_json_response))

    mock_client = Mock(spec=PinchTabClient)
    mock_client.get_page_layout.return_value = LayoutData(elements=[
        LayoutElement(selector="#name", element_type="text", label="Full Name"),
        LayoutElement(selector="#resume", element_type="file", label="Resume"),
        LayoutElement(selector="#cl_text", element_type="textarea", label="Cover Letter")
    ])
    mock_client.fill_field.return_value = True
    mock_client.upload_file.return_value = True

    # Setup database with a tailored resume path and cover letter
    conn = database.get_db_connection()
    conn.execute("""
    INSERT INTO jobs (id, job_key, title, company, description, status, cover_letter, tailored_resume_docx_path)
    VALUES (999, 'jk_123', 'Software Dev', 'Mock Company', 'Cool job', 'new', 'Dear Hiring Manager, I love coding.', 'dummy_resume.docx')
    """)
    conn.commit()
    conn.close()

    # Create dummy resume file to pass os.path.exists checks
    with open("dummy_resume.docx", "w") as f:
        f.write("resume content")

    try:
        with patch("config.GEMINI_API_KEY", "dummy_key"):
            filler = GeminiFormFiller(pinchtab_client=mock_client)
            # Call with Mode 1: job_id = 999
            results = filler.fill_form(target=999, context_data="mock_page")

            # Check PinchTab calls
            mock_client.get_page_layout.assert_called_once_with("mock_page")
            mock_client.fill_field.assert_any_call("#name", "Test Candidate")
            mock_client.upload_file.assert_called_once_with("#resume", "dummy_resume.docx")
            
            # Should fall back to the text database cover letter since no path provided
            mock_client.fill_field.assert_any_call("#cl_text", "Dear Hiring Manager, I love coding.")
            
            assert results["success_count"] == 3
            assert results["failure_count"] == 0
    finally:
        if os.path.exists("dummy_resume.docx"):
            os.remove("dummy_resume.docx")

@patch("google.generativeai.GenerativeModel")
def test_error_handling_gemini_failure(mock_model_class):
    """Verify that map_fields handles Gemini Exceptions gracefully."""
    mock_model_instance = Mock()
    mock_model_class.return_value = mock_model_instance
    mock_model_instance.generate_content.side_effect = Exception("API rate limit exceeded or invalid key")

    layout = LayoutData(elements=[
        LayoutElement(selector="#first_name", element_type="text", label="First Name")
    ])
    profile = {"full_name": "Alice Smith"}

    with patch("config.GEMINI_API_KEY", "dummy_key"):
        filler = GeminiFormFiller()
        res = filler.map_fields(layout, profile)
        
        # Verify it caught the error and populated the error field
        assert res["mappings"] == {}
        assert "API rate limit exceeded" in res["error"]

        # Verify fill_form also returns the error instead of crashing
        results = filler.fill_form(layout, profile)
        assert results["success_count"] == 0
        assert results["failure_count"] == 0
        assert "API rate limit" in results["error"]

@patch("google.generativeai.GenerativeModel")
def test_error_handling_pinchtab_failure(mock_model_class):
    """Verify that fill_form handles PinchTab Client exceptions gracefully and counts failures."""
    mock_model_instance = Mock()
    mock_model_class.return_value = mock_model_instance
    
    gemini_json_response = {
        "mappings": {
            "#first_name": "Alice",
            "#phone": "+19999999999"
        },
        "reasoning": {}
    }
    mock_model_instance.generate_content.return_value = MockResponse(json.dumps(gemini_json_response))

    mock_client = Mock(spec=PinchTabClient)
    # Make one succeed and one throw exception
    mock_client.fill_field.side_effect = [True, Exception("Network disconnect")]

    layout = LayoutData(elements=[
        LayoutElement(selector="#first_name", element_type="text", label="First Name"),
        LayoutElement(selector="#phone", element_type="text", label="Phone")
    ])
    profile = {"full_name": "Alice Smith"}

    with patch("config.GEMINI_API_KEY", "dummy_key"):
        filler = GeminiFormFiller(pinchtab_client=mock_client)
        results = filler.fill_form(layout, profile)
        
        assert results["success_count"] == 1
        assert results["failure_count"] == 1
        assert results["#first_name"] is True
        assert results["#phone"] is False
