"""
Executes the web search.
@arg query(str): a string with the query that is used during the websearch.
@returns iterable containing the list of resulting links
"""


import logging
import random
import time
from googlesearch import search

logger = logging.getLogger("finder.search.web_search")

def safe_search_with_backoff(query):
    """Search with human-like delays and retry logic"""

    try:
        delay = random.uniform(3, 8)
        logger.debug(f"Sleeping {delay:.1f}s before search")
        time.sleep(delay)

        logger.info(f"Executing Google search: \"{query}\"")
        results = search(query, num_results = 10,
            unique = True, lang = "it", region = "eu", safe = None, advanced = True)
        results_list = list(results)
        logger.info(f"Search returned {len(results_list)} results")

        # Check for CAPTCHA or block
        for result in results_list:
            if "unusual traffic" in result.description.lower():
                wait_time =  60
                logger.warning(f"CAPTCHA/block detected! Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue

        return results_list

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return None
