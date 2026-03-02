import random
import time
from googlesearch import search

def safe_search_with_backoff(query, max_retries=3):
    """Search with human-like delays and retry logic"""
    
    for attempt in range(max_retries):
        try:
            # Random delay between 3-8 seconds
            time.sleep(random.uniform(3, 8))
            
            results = search(query, num_results = 10, 
                unique = True, lang = "it", region = "eu", safe = None, advanced = True)
            results_list = list(results)

            # Check for CAPTCHA or block
            if "unusual traffic" in response.text.lower():
                wait_time = (attempt + 1) * 60  # Exponential backoff
                print(f"Detected block. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            
            return results_list
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(30)
    
    return None