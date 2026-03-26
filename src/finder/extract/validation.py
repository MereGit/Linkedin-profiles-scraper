"""
This module defines an agent that validates the link, checking whether
the linkedin profile matches the person at the firm we were looking for.
@arg query: one of the urls from the list that was found using the web search
@arg person_name: name of the person we are looking for
@arg firm: firm in which we expect the person to be employed in
@returns a bool confirming that the link corresponds (partially) to the input,
the link, and the check label
"""

import logging
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from ddgs.exceptions import DDGSException
from datetime import datetime
from typing import Tuple
from . import linkedin_validator
import json
import tiktoken

logger = logging.getLogger("finder.extract.validation")

def is_correct_person_ai(query: str, person_name: str, firm: str) -> Tuple[bool, str, str, str, float]:
	link = "N/A"
	check = "FALSE"
	llm_ag = ChatOpenAI(model="gpt-5-mini") #Requires the api key to be stored in an env variable
	wrapper_ddg = DuckDuckGoSearchAPIWrapper(region="it-it", max_results=25)
	search = DuckDuckGoSearchResults(api_wrapper=wrapper_ddg, output_format="json")
	# Search for exact URL to get snippet
	logger.debug(f"DuckDuckGo search - {query}")
	try:
		results_json = search.invoke(query)
		results = json.loads(results_json)
	except DDGSException:
		logger.warning(f"DuckDuckGo returned no results for {query}")
		return False, "No match", link, check, 0.0
	logger.debug(f"DuckDuckGo returned {len(results)} results")

	for result in results:
		link = result.get('link', '')
		if linkedin_validator.is_linkedin_profile_url(link) == True:
			logger.debug("Found a LinkedIn profile in DuckDuckGo results, running LLM validation")
			snippet = result.get('snippet', '')
			title = result.get('title', '')
			prompt = (
				f" You are an expert text evaluator. You will be given a"
				f" title and a snippet from a linkedin profile found in a web search."
				f" Your job is to check whether the person's name and the firm"
				f" match what we are looking for."
				f" You will be given a person's name and a firm."
				f" Check if the title or snippet refers to the same person"
				f" (the name should match or be very close) AND the same firm."
				f" The FIRM you find from the online search has to be very similar"
				f" to the one given in input. Don't be key sensitive, and at the same time"
				f" don't accept very different variations of the name given as a title, unless"
				f" we are referring to a group (If input is Lavazza and you find Lavazza group"
				f" it is fine, if you find Lavazzer for instance no) or they are excluding"
				f" acronyms, codes corporate types (s.p.a./s.r.l and so on)."
				f" Ensure that the firm is based in Italy: if I look for Marco Rossi at Lavazza"
				f" it shouldn't pick a profile of a Marco Rossi at Lavazza in the US."
				f" Also be sure that they are currently employed at the firm: if in the snippet"
				f" you find that the person is a former employee and they are now"
				f" ({(datetime.today().strftime('%Y-%m-%d'))}) employed elsewhere, you should answer FALSE."
				f" You will answer one and only one of the following options:\n"
				f" [Option]TRUE: if the person's name AND the firm are found in the snippet or title\n"
				f" [Option]FALSE: otherwise\n"
				f" DO NOT ANSWER WITH LONGER MESSAGES. IT IS VITAL THAT YOU ONLY ANSWER WITH THE OPTIONS"
				f" LISTED ABOVE."
				f" Here there is the firm: {firm}. Here is the person's name: {person_name}"
				f" \n Here there is the title: {title} \n Here there is the snippet: {snippet}"
			)

			# Check if person matches the snippet/title
			logger.debug(f"Prompt sent to LLM:\n{prompt}")
			logger.info(f"LLM validation for {link} | person=\"{person_name}\" firm=\"{firm}\"")
			try:
				encoding = tiktoken.encoding_for_model("gpt-5-mini")
			except KeyError:
				encoding = tiktoken.get_encoding("o200k_base")
			input_tokens = len(encoding.encode(prompt))
			response = llm_ag.invoke(prompt)
			check = response.content.strip()
			output_tokens = len(encoding.encode(check))
			input_cost = (input_tokens / 1_000_000) * 0.25
			output_cost = (output_tokens / 1_000_000) * 2.00
			total_cost = input_cost + output_cost
			logger.debug(f"LLM cost: {input_tokens} input tokens + {output_tokens} output tokens = ${total_cost:.6f}")
			logger.debug(f"LLM response: \"{check}\"")
			if check == "TRUE":
				logger.info(f"Validation result: Perfect match (status={check})")
				return True, "Perfect match", link, check, total_cost
		else:
			logger.debug("Result link is not a LinkedIn profile.")


	logger.warning(f"No LinkedIn profile found in DuckDuckGo results for {query}")
	return False, "No match", link, check, 0.0
