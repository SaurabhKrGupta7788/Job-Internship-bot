import json
import google.generativeai as genai
from config import GEMINI_API_KEY
import database

def get_gemini_model():
    """Initializes and returns the Gemini model."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in environment or config.")
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(
        model_name="gemini-flash-lite-latest",
        generation_config={"response_mime_type": "application/json"}
    )

def tailor_application(job_id):
    """
    Tailors the user resume and creates a cover letter for a specific job listing using Gemini.
    """
    profile = database.get_profile()
    if not profile or not profile.get('base_resume'):
        raise ValueError("Base resume is empty in the user profile. Please upload a resume first.")

    job = database.get_job(job_id)
    if not job:
        raise ValueError(f"Job with ID {job_id} not found.")

    base_resume_json = profile.get('base_resume')
    
    # Try parsing to verify valid JSON
    try:
        base_resume_data = json.loads(base_resume_json)
    except Exception as e:
        # If it's not JSON, we will assume it's text and ask Gemini to convert it to JSON first
        base_resume_data = base_resume_json

    # Construct prompt
    prompt = f"""
    You are an elite ATS (Applicant Tracking System) optimization specialist and executive recruiter.
    Your objective is to optimize the candidate's resume and cover letter to maximize the likelihood of passing corporate ATS screenings and hiring manager reviews.

    For the tailored deliverables:
    1. **ATS Keyword Alignment**: Identify the primary technical keywords, tools, frameworks, and soft skills mentioned in the Job Description. Integrate these EXACT keywords seamlessly into the tailored resume's Skills and Experience sections.
    2. **X-Y-Z Accomplishment Formula**: Rewrite experience highlight bullets using Google's X-Y-Z formula: "Accomplished [X] as measured by [Y], by doing [Z]". Use high-impact active action verbs (e.g., *Engineered, Spearheaded, Systematized, Optimized, Deployed*).
    3. **No Fabrication**: Frame existing experiences, hackathons, and research projects to directly answer the job requirements, but do NOT make up job titles, companies, or dates.
    4. **Cover Letter**: Draft a compelling, personalized cover letter that highlights the overlap between the candidate's background (especially research roles and hackathons) and the company's tech stack.

    Base Resume:
    {json.dumps(base_resume_data, indent=2) if isinstance(base_resume_data, dict) else base_resume_data}

    Target Job Details:
    Title: {job.get('title')}
    Company: {job.get('company')}
    Location: {job.get('location')}
    Description: {job.get('description')}

    Output your response in the following strict JSON schema:
    {{
      "match_score": 95,
      "match_analysis": "Strengths: ... | Missing Keywords: ... | Strategic Tips: ... (Format as concise bullets)",
      "cover_letter": "[Full, highly-polished Cover Letter tailored to the role]",
      "tailored_resume": {{
         "name": "[same as candidate]",
         "email": "[same as candidate]",
         "phone": "[same as candidate]",
         "linkedin": "[same as candidate]",
         "github": "[same as candidate]",
         "website": "[same as candidate]",
         "summary": "[Executive summary written using job keywords, highlighting core strengths]",
         "skills": ["Skill1", "Skill2", "Skill3", "..."],
         "experience": [
            {{
               "company": "[same as candidate]",
               "role": "[same as candidate]",
               "dates": "[same as candidate]",
               "highlights": [
                  "High-impact Google X-Y-Z bullet incorporating job keywords",
                  "High-impact Google X-Y-Z bullet incorporating job keywords"
               ]
            }}
         ],
         "projects": [
            {{
               "title": "[same as candidate]",
               "description": "[same as candidate]",
               "highlights": [
                  "High-impact project bullet incorporating job keywords"
               ]
            }}
         ],
         "education": [
            {{
               "institution": "[same as candidate]",
               "degree": "[same as candidate]",
               "dates": "[same as candidate]"
            }}
         ]
      }}
    }}
    """

    model = get_gemini_model()
    response = model.generate_content(prompt)
    
    try:
        result = json.loads(response.text)
    except Exception as e:
        print(f"Error parsing Gemini response as JSON: {e}")
        print(response.text)
        raise e

    match_score = result.get('match_score', 0)
    match_analysis = result.get('match_analysis', '')
    cover_letter = result.get('cover_letter', '')
    tailored_resume = result.get('tailored_resume', {})

    # Generate html representation of the resume for UI previewing
    tailored_resume_html = generate_resume_html(tailored_resume)
    
    # Save files to output directory
    import os
    from config import OUTPUT_DIR
    import generator
    
    # Generate tailored DOCX file
    import re
    company_clean = re.sub(r'[^\w\s-]', '', job.get('company')).strip().replace(' ', '_')
    title_clean = re.sub(r'[^\w\s-]', '', job.get('title')).strip().replace(' ', '_')
    docx_filename = f"Resume_{company_clean}_{title_clean}.docx"
    docx_path = os.path.join(OUTPUT_DIR, docx_filename)
    
    generator.create_docx_resume(tailored_resume, docx_path)
    
    # Generate Cover Letter file
    cl_filename = f"CoverLetter_{company_clean}_{title_clean}.txt"
    cl_path = os.path.join(OUTPUT_DIR, cl_filename)
    generator.create_txt_cover_letter(cover_letter, cl_path)
    
    # Save the tailoring results to database
    database.update_job_tailoring(
        job_id=job_id,
        match_score=match_score,
        match_analysis=match_analysis,
        cover_letter=cover_letter,
        tailored_resume_html=tailored_resume_html,
        tailored_resume_docx_path=docx_path
    )
    
    print(f"Successfully tailored application for Job ID {job_id} (Score: {match_score}%)")
    return result

def generate_resume_html(resume_data):
    """
    Renders the tailored resume JSON data into a clean, modern HTML layout.
    """
    # Simple CSS styled HTML string
    skills_html = "".join([f"<li>{s}</li>" for s in resume_data.get('skills', [])])
    
    exp_html = ""
    for exp in resume_data.get('experience', []):
        bullets = "".join([f"<li>{b}</li>" for b in exp.get('highlights', [])])
        exp_html += f"""
        <div class="resume-item">
            <div class="resume-header">
                <strong>{exp.get('role')}</strong> - {exp.get('company')}
                <span class="resume-date">{exp.get('dates')}</span>
            </div>
            <ul>{bullets}</ul>
        </div>
        """
        
    proj_html = ""
    for proj in resume_data.get('projects', []):
        bullets = "".join([f"<li>{b}</li>" for b in proj.get('highlights', [])])
        proj_html += f"""
        <div class="resume-item">
            <div class="resume-header">
                <strong>{proj.get('title')}</strong>
            </div>
            <p style="margin: 4px 0;">{proj.get('description')}</p>
            <ul>{bullets}</ul>
        </div>
        """
        
    edu_html = ""
    for edu in resume_data.get('education', []):
        edu_html += f"""
        <div class="resume-item">
            <div class="resume-header">
                <strong>{edu.get('degree')}</strong> - {edu.get('institution')}
                <span class="resume-date">{edu.get('dates')}</span>
            </div>
        </div>
        """

    links = []
    if resume_data.get('linkedin'): links.append(f"LinkedIn: {resume_data.get('linkedin')}")
    if resume_data.get('github'): links.append(f"GitHub: {resume_data.get('github')}")
    if resume_data.get('website'): links.append(f"Website: {resume_data.get('website')}")
    links_str = " | ".join(links)

    html = f"""
    <div class="tailored-resume-preview">
        <style>
            .tailored-resume-preview {{
                font-family: 'Inter', system-ui, sans-serif;
                color: #2d3748;
                line-height: 1.5;
                padding: 40px;
                background: white;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                max-width: 800px;
                margin: auto;
            }}
            .resume-title {{
                text-align: center;
                margin-bottom: 5px;
                color: #1a202c;
            }}
            .resume-subtitle {{
                text-align: center;
                font-size: 0.9rem;
                color: #718096;
                margin-bottom: 20px;
            }}
            .resume-section-title {{
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 5px;
                margin-top: 20px;
                margin-bottom: 10px;
                font-size: 1.1rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: #2b6cb0;
            }}
            .resume-item {{
                margin-bottom: 15px;
            }}
            .resume-header {{
                display: flex;
                justify-content: space-between;
                font-weight: 500;
                color: #2d3748;
            }}
            .resume-date {{
                color: #718096;
                font-size: 0.85rem;
            }}
            .tailored-resume-preview ul {{
                margin-top: 5px;
                padding-left: 20px;
            }}
            .tailored-resume-preview li {{
                margin-bottom: 4px;
            }}
            .skills-list {{
                display: flex;
                flex-wrap: wrap;
                list-style: none !important;
                padding-left: 0 !important;
                gap: 8px;
            }}
            .skills-list li {{
                background: #ebf8ff;
                color: #2b6cb0;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 0.85rem;
            }}
        </style>
        
        <h1 class="resume-title">{resume_data.get('name')}</h1>
        <div class="resume-subtitle">
            Email: {resume_data.get('email')} | Phone: {resume_data.get('phone')}<br>
            {links_str}
        </div>
        
        <div class="resume-section-title">Professional Summary</div>
        <p>{resume_data.get('summary')}</p>
        
        <div class="resume-section-title">Skills</div>
        <ul class="skills-list">
            {skills_html}
        </ul>
        
        <div class="resume-section-title">Professional Experience</div>
        {exp_html}
        
        {f'<div class="resume-section-title">Projects</div>{proj_html}' if proj_html else ''}
        
        <div class="resume-section-title">Education</div>
        {edu_html}
    </div>
    """
    return html
