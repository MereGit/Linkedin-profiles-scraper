"""
This module defines an agent that validates the link, checking whether
the linkedin profile matches the role at the firm we were looking for.
@arg query: one of the urls from the list that was found using the google search
@arg expected_role: role from the list, is the same used to run the google search
@arg firm: firm in which we expect the person to be employed in
@returns a bool confirming that the link corresponds (partially) to the input,
the link, and the header title to be used in the header column
"""

import logging
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from ddgs.exceptions import DDGSException
from typing import Tuple
from . import linkedin_validator
import json

logger = logging.getLogger("finder.extract.validation")

def is_correct_role_ai(query: str, expected_role: str, firm: str) -> Tuple[bool, str, str, str, str]:
	link = "N/A"
	check = "FALSE"
	title = "N/A"
	llm_ag = ChatOpenAI(model="gpt-5-mini") #Requires the api key to be stored in an env variable
	wrapper_ddg = DuckDuckGoSearchAPIWrapper(region="it-it", max_results=5)
	search = DuckDuckGoSearchResults(api_wrapper=wrapper_ddg, output_format="json")
	# Search for exact URL to get snippet
	logger.info(f"DuckDuckGo search - {query}")
	try:
		results_json = search.invoke(query)
		results = json.loads(results_json)
	except DDGSException:
		logger.warning(f"DuckDuckGo returned no results for {query}")
		return False, "No match", link, check, title
	logger.debug(f"DuckDuckGo returned {len(results)} results")

	for result in results:
		link = result.get('link', '')
		if linkedin_validator.is_linkedin_profile_url(link) == True:
			logger.info("Found a LinkedIn profile in DuckDuckGo results, running LLM validation")
			snippet = result.get('snippet', '')
			title = result.get('title', '')
			prompt = (
				f" You are an expert text evaluator. You will be given a"
				f" title and a snippet from a google result in a web search."
				f" These belong to linkedin profiles. You will be also given in input"
				f" a corporate role at a firm. Your job is to check whether"
				f" in the title or in the snippet, there is the role/a VERY CLOSE synonim of"
				f" the role and the firm you were given in input. E.g. if the role is Head of HR you"
				f" shouldn't pick a business unit HR, but you could pick a Head of people. Then, you will answer"
				f" one and only one of the following options in the following cases: \n"
				f" [Option]TRUE: [Case] if the role/synonim at the firm was found in either the snippet or the title\n"
				f" [Option]MISSING_FIRM: [Case]  if the role or a synonim was found but the firm was missing\n"
				f" [Option]FALSE: [Case]  in any other case\n"
				f" DO NOT ANSWER WITH LONGER MESSAGES. IT IS VITAL THAT YOU ONLY ANSWER WITH THE OPTIONS"
				f" LISTED ABOVE. Here there is the role and the firm: {firm}, {expected_role}"
				f" \n Here there is the title: {title} \n Here there is the snippet: {snippet}"
			)

			# Check if expected role is in the snippet/title
			logger.debug(f"Prompt sent to LLM:\n{prompt}")
			logger.info(f"LLM validation for {link} | firm=\"{firm}\" role=\"{expected_role}\"")
			response = llm_ag.invoke(prompt)
			check = response.content.strip()
			logger.info(f"LLM response: \"{check}\"")
			if check == "TRUE":
				logger.info(f"Validation result: Perfect match (status={check})")
				return True, "Perfect match", link, check, title
			elif check == "MISSING_FIRM":
				logger.info(f"Validation result: Matching role, missing firm (status={check})")
				return True, "Matching role, missing firm", link, check, title
		else:
			logger.info("Result link is not a LinkedIn profile.")


	logger.warning(f"No LinkedIn profile found in DuckDuckGo results for {query}")
	return False, "No match", link, check, title
