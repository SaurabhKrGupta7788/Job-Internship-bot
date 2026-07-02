import re
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:5000"

def test_dashboard_smoke(page: Page):
    """
    Smoke test: Ensure the main dashboard loads with HTTP 200.
    """
    response = page.goto(BASE_URL)
    assert response.status == 200, f"Expected 200 OK, got {response.status}"
    
    # Verify the title contains JobCraft or similar
    expect(page).to_have_title(re.compile("JobCraft|Dashboard", re.IGNORECASE))

def test_dashboard_elements(page: Page):
    """
    Critical user journeys: Verify primary form elements exist on the dashboard.
    """
    page.goto(BASE_URL)
    
    # Check for the dashboard metrics
    expect(page.locator("#metric-total")).to_be_visible()
    expect(page.locator("#metric-applied")).to_be_visible()
    
    # Check for the table
    expect(page.locator("#recent-jobs-table")).to_be_visible()
    
def test_dashboard_action_buttons(page: Page):
    """
    Verify the action buttons exist when switching to Find Jobs section.
    """
    page.goto(BASE_URL)
    
    # Click to Find Jobs section
    page.locator("li.nav-item", has_text="Find Jobs").click()
    
    expect(page.locator("#btn-toggle-tailor")).to_be_visible()
    expect(page.locator("#btn-toggle-search")).to_be_visible()
