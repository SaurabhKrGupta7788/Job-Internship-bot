import database
from config import DEFAULT_COUNTRY, DEFAULT_KEYWORDS, DEFAULT_LOCATION

try:
    from jobspy import scrape_jobs
except ImportError:
    print("Warning: python-jobspy not installed. Run 'pip install python-jobspy pandas'")
    scrape_jobs = None

def search_jobspy_jobs(keywords=None, country=None, location=None, results_wanted=10):
    """
    Queries major job boards (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs)
    using python-jobspy, differentiating between jobs and internships.
    """
    if not scrape_jobs:
        return []

    # Get search criteria, defaulting to config values
    keywords = keywords or DEFAULT_KEYWORDS
    raw_country = country or DEFAULT_COUNTRY
    location = location or DEFAULT_LOCATION

    country_map = {
        'in': 'india', 'us': 'usa', 'gb': 'uk', 'au': 'australia',
        'ca': 'canada', 'de': 'germany', 'fr': 'france'
    }
    mapped_country = country_map.get(raw_country.lower(), raw_country)

    # Split keywords by comma to search
    keywords_list = [k.strip() for k in keywords.split(",") if k.strip()]
    
    all_jobs = []
    
    # jobspy uses specific site names
    sites = ["linkedin", "indeed", "glassdoor", "zip_recruiter", "google"]

    # We will do two passes: regular job search, and internship search
    for kw in keywords_list:
        entry_level_kw = f"entry level {kw}"
        print(f"Searching for Jobs: '{entry_level_kw}' in location: '{location}'")
        try:
            # 1. Search for Jobs
            jobs_df = scrape_jobs(
                site_name=sites,
                search_term=entry_level_kw,
                location=location,
                results_wanted=results_wanted,
                hours_old=72, 
                country_indeed=mapped_country
            )
            
            if not jobs_df.empty:
                for _, row in jobs_df.iterrows():
                    # Build salary string; if both min and max are empty, set to 'N/A'
                    min_amt = str(row.get('min_amount', '')).strip()
                    max_amt = str(row.get('max_amount', '')).strip()
                    currency = str(row.get('currency', '')).strip()
                    if not min_amt and not max_amt:
                        salary = 'N/A'
                    else:
                        parts = []
                        if min_amt:
                            parts.append(min_amt)
                        if max_amt:
                            parts.append(max_amt)
                        salary = ' - '.join(parts)
                        if currency:
                            salary = f"{salary} {currency}"
                    
                    all_jobs.append({
                        'key': row.get('id', '') or str(row.get('job_url', '')),
                        'title': row.get('title', 'Untitled'),
                        'company': row.get('company', 'Unknown Company'),
                        'description': row.get('description', ''),
                        'location': row.get('location', location),
                        'url': row.get('job_url', ''),
                        'salary': salary,
                        'site': row.get('site', 'Unknown'),
                        'job_type': 'job'
                    })
        except Exception as e:
            print(f"Error scraping jobs for {kw}: {e}")

        # 2. Search for Internships
        internship_kw = f"{kw} internship"
        print(f"Searching for Internships: '{internship_kw}' in location: '{location}'")
        try:
            intern_df = scrape_jobs(
                site_name=sites,
                search_term=internship_kw,
                location=location,
                results_wanted=results_wanted,
                hours_old=72,
                country_indeed=mapped_country
            )
            
            if not intern_df.empty:
                for _, row in intern_df.iterrows():
                    # Check if it really is an internship to avoid duplicates
                    title_lower = str(row.get('title', '')).lower()
                    if 'intern' in title_lower or 'co-op' in title_lower:
                        # Build salary string for internships similarly
                        min_amt = str(row.get('min_amount', '')).strip()
                        max_amt = str(row.get('max_amount', '')).strip()
                        currency = str(row.get('currency', '')).strip()
                        if not min_amt and not max_amt:
                            salary = 'N/A'
                        else:
                            parts = []
                            if min_amt:
                                parts.append(min_amt)
                            if max_amt:
                                parts.append(max_amt)
                            salary = ' - '.join(parts)
                            if currency:
                                salary = f"{salary} {currency}"
                        all_jobs.append({
                            'key': row.get('id', '') or str(row.get('job_url', '')),
                            'title': row.get('title', 'Untitled'),
                            'company': row.get('company', 'Unknown Company'),
                            'description': row.get('description', ''),
                            'location': row.get('location', location),
                            'url': row.get('job_url', ''),
                            'salary': salary,
                            'site': row.get('site', 'Unknown'),
                            'job_type': 'internship'
                        })
        except Exception as e:
            print(f"Error scraping internships for {kw}: {e}")
            
    # Clean up empty salaries and keys
    # Ensure any placeholder salary values are normalized
    for j in all_jobs:
        if not j['salary'] or j['salary'].strip() in ('', '-', '-  '):
            j['salary'] = 'N/A'
        if not j['key']:
            j['key'] = j['url']  # Fallback
                
    return all_jobs

def run_job_search():
    """Runs a job search using details saved in the database profile and updates local DB."""
    profile = database.get_profile()
    
    keywords = profile.get('keywords') if profile else None
    country = profile.get('country') if profile else None
    location = profile.get('location') if profile else None

    # Fetch jobs
    jobs = search_jobspy_jobs(keywords=keywords, country=country, location=location)
    
    if jobs:
        new_inserted = database.add_jobs(jobs)
        print(f"Search complete. Added {new_inserted} new unique jobs to the database.")
        return new_inserted
    else:
        print("No new jobs found or scrape failed.")
        return 0

if __name__ == '__main__':
    # Initialize DB in case it isn't
    database.init_db()
    run_job_search()
