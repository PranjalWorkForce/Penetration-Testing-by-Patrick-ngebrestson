#!/usr/bin/env python3
import time
import logging
import shodan

# ==========================================
# CONFIGURATION & LOGGING SETUP
# ==========================================
SHODAN_API_KEY = "YOUR_API_KEY_HERE"

# Configure logging to save errors, rate limits, and failures to 'error.log'
logging.basicConfig(
    filename='error.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ==========================================
# HELPER FUNCTION: RETRY & BACKOFF WRAPPER
# ==========================================
def fetch_page_with_retry(api, query, page_num, max_retries=3):
    """
    Fetches a single Shodan search page with built-in retry logic, 
    exponential backoff, and automatic error logging.
    """
    backoff_delay = 2  # Initial wait time in seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[*] Fetching page {page_num} (Attempt {attempt} of {max_retries})...")
            result = api.search(query, page=page_num)
            return result
            
        except shodan.APIError as e:
            error_string = str(e).lower()
            
            # Check if error is related to rate limiting or server overload
            if "rate limit" in error_string or "too many requests" in error_string:
                warning_msg = f"Rate limit hit on page {page_num}: {e}"
                print(f"[!] {warning_msg}. Retrying in {backoff_delay} seconds...")
                logging.warning(warning_msg)
            else:
                # Other API errors (e.g., invalid query syntax, plan restrictions)
                print(f"[-] Shodan API Error on page {page_num}: {e}")
                logging.error(f"API Error on page {page_num} for query '{query}': {e}")
                return None
            
            # If we reached max retries, log final failure and exit function
            if attempt == max_retries:
                err_msg = f"Max retries reached. Failed to fetch page {page_num} for query: '{query}'"
                print(f"[-] {err_msg}")
                logging.error(err_msg)
                return None
            
            # Wait with exponential backoff before trying again
            time.sleep(backoff_delay)
            backoff_delay *= 2  # Double the wait time (2s -> 4s -> 8s)
            
        except Exception as e:
            print(f"[-] Unexpected error on page {page_num}: {e}")
            logging.error(f"Unexpected error on page {page_num}: {e}")
            return None
            
    return None

# ==========================================
# MAIN ORCHESTRATOR: PAGINATION & GATHERING
# ==========================================
def search_shodan_paginated(query):
    """
    Orchestrates the entire search, calculates total pages,
    and loops through all results while respecting rate limits.
    """
    try:
        # Initialize the Shodan API client
        api = shodan.Shodan(SHODAN_API_KEY)
        
        print(f"[*] Starting Shodan search for query: '{query}'")
        
        # 1. Fetch Page 1 to get total count
        first_page_result = fetch_page_with_retry(api, query, page_num=1)
        if not first_page_result:
            print("[-] Initial search failed. Check 'error.log' for details.")
            return []
            
        total_results = first_page_result.get('total', 0)
        print(f"[+] Total devices found globally: {total_results}")
        
        if total_results == 0:
            return []

        all_matches = []
        all_matches.extend(first_page_result['matches'])
        
        # 2. Calculate total pages (Shodan returns 100 results per page)
        results_per_page = 100
        total_pages = (total_results // results_per_page) + (1 if total_results % results_per_page > 0 else 0)
        
        print(f"[*] Total pages to fetch: {total_pages}")
        
        # Optional Safety Cap: Limit pages during testing to save credits
        # (Change max_pages if you want to scrape everything)
        max_pages_to_fetch = min(total_pages, 10) 
        if total_pages > max_pages_to_fetch:
            print(f"[!] Safety cap active: Limiting fetch to first {max_pages_to_fetch} pages to save API credits.")
        
        # 3. Loop through remaining pages
        for page in range(2, max_pages_to_fetch + 1):
            page_data = fetch_page_with_retry(api, query, page_num=page)
            
            if page_data and 'matches' in page_data:
                all_matches.extend(page_data['matches'])
            else:
                print(f"[!] Skipping or breaking early due to errors on page {page}.")
                break
                
            # Polite delay between page requests to avoid triggering rate limits
            time.sleep(1)
            
        print(f"\n[+] Successfully gathered a total of {len(all_matches)} records.")
        return all_matches

    except Exception as e:
        print(f"[-] A critical error occurred: {e}")
        logging.error(f"Critical execution error: {e}")
        return []

# ==========================================
# EXECUTION ENTRY POINT
# ==========================================
if __name__ == "__main__":
    # Define your search target query
    target_query = 'product:"Apache" country:"NP"'
    
    # Run the automated search script
    results = search_shodan_paginated(target_query)
    
    # Simple printout of the first few results found
    if results:
        print("\n--- Sample Results ---")
        for match in results[:5]:  # Display first 5 matches
            ip = match.get('ip_str')
            port = match.get('port')
            org = match.get('org', 'Unknown Org')
            print(f"IP: {ip}:{port} | Org: {org}")
    else:
        print("[-] No results returned or an error occurred.")
