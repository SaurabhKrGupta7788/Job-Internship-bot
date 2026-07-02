import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# App settings
PORT = int(os.getenv("PORT", 5000))
SECRET_KEY = os.getenv("SECRET_KEY", "jobcraft_secret_key_default_12345")

# APIs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# Job Search Defaults
DEFAULT_KEYWORDS = os.getenv("DEFAULT_KEYWORDS", "python,developer,engineer,analyst")
DEFAULT_COUNTRY = os.getenv("DEFAULT_COUNTRY", "in")  # Default to India, can be changed in settings
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "remote")

# Email Settings
EMAIL_IMAP_SERVER = os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") # App password if using 2FA

# Output folder for customized documents
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Path to database file
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "jobs.db"))

# PinchTab Server Configuration
PINCHTAB_SERVER_URL = os.getenv("PINCHTAB_SERVER_URL", "http://127.0.0.1:9000")

# Dry-Run Controller Settings
# Set DRY_RUN = True to fill form fields and upload files, but skip clicking final "Submit" buttons
DRY_RUN = os.getenv("DRY_RUN", "False").lower() in ("true", "1", "yes")

def is_configured():
    """Checks if essential API keys are provided."""
    return bool(GEMINI_API_KEY)

