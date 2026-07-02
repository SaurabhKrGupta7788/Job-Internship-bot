import asyncio
from playwright.async_api import async_playwright
import os

async def save_linkedin_session():
    print("\n=============================================")
    print("      JobCraft - LinkedIn Authenticator      ")
    print("=============================================")
    print("Launching browser... Please log into LinkedIn.")
    print("You have 90 seconds to complete the login and any 2FA.")
    
    async with async_playwright() as p:
        # Use a persistent context instead of state.json to avoid Playwright cookie bugs
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./chrome_profile",
            headless=False
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Go to LinkedIn login
        await page.goto("https://www.linkedin.com/login")
        
        print("\n--> Waiting for 90 seconds... Please log in now!")
        
        # Wait 90 seconds to allow the user to type credentials and pass 2FA
        await page.wait_for_timeout(90000)
        
        print("\n[SUCCESS] Profile successfully saved to './chrome_profile'!")
        print("The agent will now be able to bypass the login screen.")
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(save_linkedin_session())
