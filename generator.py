import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def set_cell_border(cell, **kwargs):
    """
    Sets individual borders for a table cell.
    Usage: set_cell_border(cell, bottom={"sz": 12, "val": "single", "color": "D3D3D3"})
    """
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.first_child_found_in("w:tcBorders")
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)
    
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        edge_data = kwargs.get(edge)
        if edge_data:
            tag = 'w:{}'.format(edge)
            element = tcBorders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                tcBorders.append(element)
            for key, val in edge_data.items():
                element.set(qn('w:{}'.format(key)), str(val))

def create_txt_cover_letter(cover_letter_text, output_path):
    """
    Saves the generated cover letter to a plain text file.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cover_letter_text)
    print(f"Generated cover letter at: {output_path}")

def create_docx_resume(resume_data, output_path):
    """
    Generates a clean, professional, ATS-friendly Word document (.docx)
    from the structured resume JSON data.
    """
    doc = Document()
    
    # Page setup - 0.75-inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Base styling
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x2D, 0x37, 0x48) # Charcoal slate

    # 1. Header (Name, Contact Details)
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run(resume_data.get('name', 'Your Name'))
    title_run.font.name = 'Calibri'
    title_run.font.size = Pt(22)
    title_run.bold = True
    title_run.font.color.rgb = RGBColor(0x1A, 0x20, 0x2C) # Off-black
    title_p.paragraph_format.space_after = Pt(2)

    # Contact Details Paragraph
    contact_p = doc.add_paragraph()
    contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_p.paragraph_format.space_after = Pt(18)
    
    links = []
    if resume_data.get('email'): links.append(resume_data.get('email'))
    if resume_data.get('phone'): links.append(resume_data.get('phone'))
    if resume_data.get('linkedin'): links.append(resume_data.get('linkedin'))
    if resume_data.get('github'): links.append(resume_data.get('github'))
    if resume_data.get('website'): links.append(resume_data.get('website'))
    
    contact_text = "  |  ".join(links)
    contact_run = contact_p.add_run(contact_text)
    contact_run.font.size = Pt(9.5)
    contact_run.font.color.rgb = RGBColor(0x71, 0x80, 0x96) # Muted Gray

    # Helper function to add Section Headers
    def add_section_header(title):
        header_p = doc.add_paragraph()
        header_p.paragraph_format.space_before = Pt(16)
        header_p.paragraph_format.space_after = Pt(6)
        header_p.paragraph_format.keep_with_next = True
        
        run = header_p.add_run(title.upper())
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x2B, 0x6C, 0xB0) # Slate Blue
        
        # Add a subtle line under the header by adding a bottom border or dashes
        # Programmatically we can just add a paragraph border or a run of dashes,
        # but a neat line can also be added using XML or a divider paragraph.
        # Let's keep it simple and ATS friendly (no complex graphics).

    # Helper to add experience / project entries
    def add_job_header(bold_title, regular_title, date_str):
        # We use a 1-row table with 2 cells to align dates to the right cleanly
        table = doc.add_table(rows=1, cols=2)
        table.autofit = False
        table.columns[0].width = Inches(5.2)
        table.columns[1].width = Inches(1.8)
        
        # Set borders to None (invisible table)
        for row in table.rows:
            for cell in row.cells:
                tcPr = cell._tc.get_or_add_tcPr()
                tcBorders = OxmlElement('w:tcBorders')
                for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
                    border = OxmlElement(f'w:{border_name}')
                    border.set(qn('w:val'), 'none')
                    tcBorders.append(border)
                tcPr.append(tcBorders)
        
        # Left side
        cell_l = table.cell(0, 0)
        p_l = cell_l.paragraphs[0]
        p_l.paragraph_format.space_after = Pt(2)
        p_l.paragraph_format.space_before = Pt(4)
        
        run_bold = p_l.add_run(bold_title)
        run_bold.bold = True
        
        if regular_title:
            p_l.add_run(f"  —  {regular_title}")
            
        # Right side (Dates)
        cell_r = table.cell(0, 1)
        p_r = cell_r.paragraphs[0]
        p_r.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_r.paragraph_format.space_after = Pt(2)
        p_r.paragraph_format.space_before = Pt(4)
        
        run_date = p_r.add_run(date_str)
        run_date.font.size = Pt(9.5)
        run_date.font.color.rgb = RGBColor(0x71, 0x80, 0x96)

    # 2. Professional Summary
    add_section_header("Professional Summary")
    summary_p = doc.add_paragraph(resume_data.get('summary', ''))
    summary_p.paragraph_format.space_after = Pt(10)
    summary_p.paragraph_format.line_spacing = 1.15

    # 3. Skills
    add_section_header("Skills")
    skills = resume_data.get('skills', [])
    skills_p = doc.add_paragraph()
    skills_p.paragraph_format.space_after = Pt(10)
    skills_p.paragraph_format.line_spacing = 1.15
    skills_p.add_run(", ".join(skills))

    # 4. Experience
    add_section_header("Professional Experience")
    for exp in resume_data.get('experience', []):
        add_job_header(exp.get('role', ''), exp.get('company', ''), exp.get('dates', ''))
        
        # Add highlight bullet points
        for bullet in exp.get('highlights', []):
            bp = doc.add_paragraph(style='List Bullet')
            bp.paragraph_format.space_after = Pt(3)
            bp.paragraph_format.space_before = Pt(0)
            bp.paragraph_format.line_spacing = 1.15
            bp.add_run(bullet)

    # 5. Projects
    projects = resume_data.get('projects', [])
    if projects:
        add_section_header("Projects & Accomplishments")
        for proj in projects:
            add_job_header(proj.get('title', ''), "", "")
            
            if proj.get('description'):
                desc_p = doc.add_paragraph()
                desc_p.paragraph_format.space_after = Pt(3)
                desc_p.paragraph_format.space_before = Pt(0)
                desc_p.paragraph_format.left_indent = Inches(0.25)
                desc_run = desc_p.add_run(proj.get('description'))
                desc_run.font.italic = True
                desc_run.font.size = Pt(9.5)
            
            for bullet in proj.get('highlights', []):
                bp = doc.add_paragraph(style='List Bullet')
                bp.paragraph_format.space_after = Pt(3)
                bp.paragraph_format.space_before = Pt(0)
                bp.paragraph_format.line_spacing = 1.15
                bp.add_run(bullet)

    # 6. Education
    add_section_header("Education")
    for edu in resume_data.get('education', []):
        add_job_header(edu.get('degree', ''), edu.get('institution', ''), edu.get('dates', ''))

    # Save document
    doc.save(output_path)
    print(f"Generated tailored DOCX resume at: {output_path}")

if __name__ == '__main__':
    # Test generation with sample data
    import json
    with open('base_resume.json', 'r') as f:
        sample_data = json.load(f)
    create_docx_resume(sample_data, 'test_resume.docx')
