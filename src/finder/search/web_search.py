"""
Executes the web search.
@arg query(str): a string with the query that is used during the websearch.
@returns iterable containing the list of resulting links
"""


import random
import time
from googlesearch import search

def safe_search_with_backoff(query):
    """Search with human-like delays and retry logic"""

    try:
        # Random delay between 3-8 seconds
        time.sleep(random.uniform(3, 8))
        
        results = search(query, num_results = 10, 
            unique = True, lang = "it", region = "eu", safe = None, advanced = True)
        results_list = list(results)

        # Check for CAPTCHA or block
        for result in results_list:
            if "unusual traffic" in result.lower():
                wait_time = (attempt + 1) * 60  # Exponential backoff
                print(f"Detected block. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
        
        return results_list
            
    
    return None