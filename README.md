# JobCraft: AI-Powered Job Search, Resume Tailoring & Application Tracker

JobCraft is a self-hosted local assistant that harvests job postings, custom-tailors professional resumes and cover letters in real-time using Google's Gemini API, tracks application states, and scans your email inbox for replies from recruiters.

---

## Features
1. **Automated Job Search**: Continually crawls job listings matching your keywords and location (via Adzuna's Developer API).
2. **AI-Powered Tailoring**: Uses Gemini to rewrite resume bullet points to match ATS keywords and draft a customized cover letter for each role.
3. **Professional Word (DOCX) Compilation**: Generates clean, ATS-compliant Word documents programmatically.
4. **Email Recruiter Monitor**: Logs and classifies recruiter emails (interviews, rejections, acknowledgments) in your tracker dashboard automatically.
5. **Windows Task Scheduling**: Registers native background schedules running every 2 days.
6. **Premium Dark Dashboard**: Clean glassmorphism web interface to manage your search parameters, review custom-made resumes, download DOCX files, and update application stages.

---

## Setup Instructions

### 1. Configure the Environment
1. Copy `.env.example` to `.env` in the same directory:
   ```cmd
   copy .env.example .env
   ```
2. Open `.env` and fill in:
   * `GEMINI_API_KEY`: Get one for free at [Google AI Studio](https://aistudio.google.com/).
   * `ADZUNA_APP_ID` & `ADZUNA_APP_KEY`: Get a free developer account at [Adzuna Developer Portal](https://developer.adzuna.com/).
   * `EMAIL_ADDRESS` & `EMAIL_PASSWORD`: To scan email replies, input your email and an App Password. (For Gmail, go to Google Account Security -> App Passwords).

### 2. Onboard Your Base Resume
1. Run the database initializer:
   ```cmd
   python database.py
   ```
2. Start the local server:
   ```cmd
   python app.py
   ```
3. Open your browser and go to: `http://127.0.0.1:5000`
4. Navigate to the **Profile & Agent** tab.
5. Fill in your personal information.
6. Open `base_resume.json` in a text editor, copy its contents, edit it with your real experience details, and paste it into the **Base Resume (JSON)** text area on the web page.
7. Click **Save Setup Settings**.

---

## Usage Guide

* **Find Jobs**: Click "Find Jobs" in the sidebar and press "Check For New Jobs". It will crawl new postings in the background. Refresh the page after a few seconds.
* **Tailor Resume & Cover Letter**: For any job listing, click **Tailor & Apply**. Gemini will analyze the job and generate your match score, custom bullet points, and cover letter in the Workspace section.
* **Download & Apply**: Download your customized Word doc (`.docx`) file from the Workspace header. Click the application link, fill in details, attach your new tailored files, and mark as **Applied**.
* **Automatic Runs**: In the **Profile & Agent** tab, toggle the background scheduler switch. 
  *(Note: To allow background scheduling, start your command line or Flask server as Administrator).*
