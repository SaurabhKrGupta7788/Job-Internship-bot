import os
import json
import logging
import re
from typing import Dict, Any, List, Optional
import google.generativeai as genai

import config
import database
from playwright_extractor import PlaywrightFormDOM, LayoutData, LayoutElement

logger = logging.getLogger("GeminiFormFiller")

class GeminiFormFiller:
    """
    Form Filler using the Gemini API ('gemini-flash-lite-latest') to map page elements 
    to candidate profile data, and fill them on the active browser tab via PlaywrightFormDOM.
    """

    def __init__(
        self, 
        api_key: Optional[str] = None, 
        extractor: Optional[PlaywrightFormDOM] = None, 
        model_name: str = "gemini-flash-lite-latest"
    ):
        """Initializes the Gemini Form Filler, native extractor, and Gemini API configuration."""
        self.api_key = api_key or getattr(config, "GEMINI_API_KEY", None)
        self.client = extractor
        self.model_name = model_name

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set. Please provide it or configure it in config.py.")

        # Configure Gemini API
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={"response_mime_type": "application/json"}
        )

    def prune_elements(self, elements: List[LayoutElement]) -> List[Dict[str, Any]]:
        """
        Filters out non-fillable elements (like buttons) and extracts minimal attributes 
        to reduce token consumption.
        """
        pruned = []
        for elem in elements:
            if elem.element_type in ("button", "submit", "hidden"):
                continue
            pruned.append({
                "selector": elem.selector,
                "type": elem.element_type,
                "label": elem.label,
                "options": elem.options
            })
        return pruned

    def _prepare_prompt(self, elements: List[Dict[str, Any]], profile_data: Dict[str, Any]) -> str:
        """Constructs the detailed prompt instructing Gemini how to map candidate data to HTML fields."""
        # Parse nested resume string if it's stored as JSON string
        base_resume = profile_data.get("base_resume")
        if isinstance(base_resume, str) and base_resume.strip():
            try:
                # Copy to avoid mutating original dictionary
                profile_data = dict(profile_data)
                profile_data["base_resume"] = json.loads(base_resume)
            except Exception:
                pass

        prompt = f"""
You are an expert browser automation assistant. Your task is to analyze a set of HTML input fields (extracted from a job application form) and map them to the correct values from the candidate's profile.

Candidate Profile JSON:
{json.dumps(profile_data, indent=2)}

Form Fields JSON:
{json.dumps(elements, indent=2)}

Task Instructions:
1. Match each form field (identified by its 'selector') to the corresponding value in the Candidate Profile.
2. Output a single JSON object with two top-level keys:
   - "mappings": A dictionary mapping each 'selector' (string) to the determined value (string).
   - "reasoning": A dictionary mapping each 'selector' (string) to a short explanation of how the value was determined.
3. For file inputs (type 'file'):
   - Map them to "RESUME" if the label mentions "resume", "cv", or "curriculum vitae".
   - Map them to "COVER_LETTER" if the label mentions "cover letter".
   - Map them to null or omit if they correspond to other documents not present.
4. For dropdowns (type 'select'):
   - Use the 'options' field provided in the Form Fields JSON. Select the EXACT option string that best matches the candidate's profile.
   - For visa sponsorship questions (e.g. "Will you require sponsorship?"):
     - If the candidate does not require sponsorship, select the option representing "No" (e.g., "No", "no", "false" depending on what options are available).
     - If the candidate requires sponsorship, select the option representing "Yes".
   - For demographic questions (e.g., gender, race, veteran status, disability):
     - Choose the option that matches the candidate's profile, or default to options like "Decline to Self-Identify", "I do not wish to answer", or "Prefer not to say" if they exist.
5. If an input field cannot be matched or is not applicable to the candidate's profile, map it to null.
6. Return only a valid JSON object matching the schema below. Do not include markdown code block syntax (like ```json) in the response text itself, just raw JSON.

Output JSON Schema:
{{
  "mappings": {{
    "<selector>": "<value_to_fill_or_select_or_upload_or_null>"
  }},
  "reasoning": {{
    "<selector>": "<brief_reasoning>"
  }}
}}
"""
        return prompt

    def map_fields(self, layout_data: LayoutData, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calls the Gemini API to determine the selector-to-value mapping."""
        pruned_elems = self.prune_elements(layout_data.elements)
        if not pruned_elems:
            logger.info("No fillable elements found on current page layout.")
            return {"mappings": {}, "reasoning": {}}

        prompt = self._prepare_prompt(pruned_elems, profile_data)

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean markdown code blocks if the model returned them
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            result = json.loads(text)
            
            # Post-processing: Validate selection options and perform fuzzy match
            mappings = result.get("mappings", {})
            for elem in layout_data.elements:
                if elem.element_type == "select" and elem.options:
                    val = mappings.get(elem.selector)
                    if val is not None:
                        val_str = str(val).strip()
                        # Try exact match first, then case-insensitive containment
                        if val_str not in elem.options:
                            matched = False
                            for opt in elem.options:
                                if val_str.lower() == opt.lower() or val_str.lower() in opt.lower():
                                    logger.info(f"Case-insensitive match '{val_str}' to option '{opt}' for {elem.selector}")
                                    mappings[elem.selector] = opt
                                    matched = True
                                    break
                            if not matched:
                                logger.error(f"No matching option for '{val_str}' in {elem.options} for selector '{elem.selector}'. Setting to None.")
                                mappings[elem.selector] = None

            result["mappings"] = mappings
            return result
        except Exception as e:
            logger.error(f"Error reasoning about form layout with Gemini: {e}")
            return {"mappings": {}, "reasoning": {}, "error": str(e)}

    def generate_mappings(self, layout: LayoutData, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses the Gemini model to map candidate profile to layout elements.
        Returns a dict in the list format to match the first proposal.
        """
        res = self.map_fields(layout, profile)
        mappings_dict = res.get("mappings", {})
        
        # We need to find the element type for each selector from layout elements
        elem_types = {elem.selector: elem.element_type for elem in layout.elements}
        
        mappings_list = []
        for selector, value in mappings_dict.items():
            mappings_list.append({
                "selector": selector,
                "type": elem_types.get(selector, "text"),
                "value": value
            })
        return {"mappings": mappings_list}

    def fill_form(
        self, 
        target: Any, 
        context_data: Any = None,
        resume_path: Optional[str] = None,
        cover_letter_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fills the form using resolved mappings via PlaywrightFormDOM.
        Supports dual modes of invocation:
        1. fill_form(job_id: int, page_id: Optional[str] = None)
        2. fill_form(layout_data: LayoutData, profile_data: Dict[str, Any], resume_path: Optional[str], cover_letter_path: Optional[str])
        """
        # Determine Mode
        if isinstance(target, (int, float)) or (isinstance(target, str) and target.isdigit()):
            # Mode 1: database-backed job_id
            job_id = int(target)
            page_id = context_data

            # 1. Fetch Candidate Profile and Job Details
            profile_data = database.get_profile()
            if not profile_data:
                raise ValueError("No candidate profile found in database.")
                
            job = database.get_job(job_id)
            if not job:
                raise ValueError(f"Job with ID {job_id} not found in database.")

            # 2. Get Page Layout
            logger.info(f"Retrieving page layout for form matching")
            layout_data = self.client.get_page_layout()
            if not layout_data or not layout_data.elements:
                logger.warning("No elements returned in page layout.")
                return {"success_count": 0, "failure_count": 0, "applied_mappings": []}

            # 3. Find cover letter and tailored resume paths
            resume_path = job.get("tailored_resume_docx_path")
            
            cover_letter_path = None
            if job.get("cover_letter"):
                company_clean = re.sub(r'[^\w\s-]', '', job.get('company', 'Company')).strip().replace(' ', '_')
                title_clean = re.sub(r'[^\w\s-]', '', job.get('title', 'Title')).strip().replace(' ', '_')
                cl_filename = f"CoverLetter_{company_clean}_{title_clean}.txt"
                cover_letter_path = os.path.join(config.OUTPUT_DIR, cl_filename)
                
                # Fallback to writing the text to a temp file if it does not exist
                if not os.path.exists(cover_letter_path):
                    cover_letter_path = os.path.join(config.OUTPUT_DIR, f"temp_CL_{job_id}.txt")
                    with open(cover_letter_path, "w", encoding="utf-8") as f:
                        f.write(job["cover_letter"])
        else:
            # Mode 2: layout_data and profile_data passed directly
            layout_data = target
            profile_data = context_data
            job = None

        # 4. Generate Mappings
        mapping_result = self.map_fields(layout_data, profile_data)
        mappings = mapping_result.get("mappings", {})

        # 5. Apply Mappings
        success_count = 0
        failure_count = 0
        applied_mappings = []
        results = {}

        # Create lookup for elements by selector
        elem_map = {elem.selector: elem for elem in layout_data.elements}

        for selector, value in mappings.items():
            if value is None:
                continue

            elem = elem_map.get(selector)
            elem_type = elem.element_type if elem else "text"

            try:
                success = False
                if value == "RESUME":
                    if resume_path and os.path.exists(resume_path):
                        logger.info(f"Uploading resume from '{resume_path}' to selector '{selector}'")
                        success = self.client.upload_file(selector, resume_path)
                    else:
                        logger.error(f"Resume file not found at: {resume_path}")
                        success = False
                elif value == "COVER_LETTER":
                    if elem_type == "file":
                        if cover_letter_path and os.path.exists(cover_letter_path):
                            logger.info(f"Uploading cover letter from '{cover_letter_path}' to selector '{selector}'")
                            success = self.client.upload_file(selector, cover_letter_path)
                        else:
                            logger.error(f"Cover letter file not found at: {cover_letter_path}")
                            success = False
                    else:
                        # Try to get text content from file first
                        cl_text = ""
                        if cover_letter_path and os.path.exists(cover_letter_path):
                            try:
                                with open(cover_letter_path, "r", encoding="utf-8") as f:
                                    cl_text = f.read()
                            except Exception as e:
                                logger.error(f"Error reading cover letter file: {e}")
                        
                        # Fallback to job dict cover letter text if not read from file
                        if not cl_text and job:
                            cl_text = job.get("cover_letter", "")
                            
                        if cl_text:
                            logger.info(f"Pasting cover letter text into selector '{selector}'")
                            success = self.client.fill_field(selector, cl_text)
                        else:
                            logger.error("Cover letter text content is empty.")
                            success = False
                else:
                    logger.info(f"Filling field '{selector}' with value '{value}'")
                    success = self.client.fill_field(selector, str(value))

                if success:
                    success_count += 1
                    applied_mappings.append({"selector": selector, "value": value, "status": "success"})
                    results[selector] = True
                else:
                    failure_count += 1
                    applied_mappings.append({"selector": selector, "value": value, "status": "failed"})
                    results[selector] = False

            except Exception as e:
                logger.error(f"Error filling field {selector}: {e}")
                failure_count += 1
                applied_mappings.append({"selector": selector, "value": value, "status": "error", "error": str(e)})
                results[selector] = False

        # Add summary keys to results dict so both return style expectations are satisfied
        results["success_count"] = success_count
        results["failure_count"] = failure_count
        results["applied_mappings"] = applied_mappings
        if "error" in mapping_result:
            results["error"] = mapping_result["error"]

        return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    print("GeminiFormFiller loaded.")
