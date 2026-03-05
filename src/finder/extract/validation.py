"""
This module defines an agent that validates the link, checking whether
the linkedin profile matches the role at the firm we were looking for.
@arg linkedin_url: one of the urls from the list that was found using the google search
@arg expected_role: role from the list, is the same used to run the google search
@arg firm: firm in which we expect the person to be employed in
@returns a bool confirming that the link corresponds (partially) to the input,
the link, and the header title to be used in the header column
"""

from langchain.agents import load_tools
from langchain.agents import initialize_agent
from langchain.llms import OpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from . import linkedin_validator
import json

def is_correct_role_ai(linkedin_url: str, expected_role: str, firm: str) -> bool, str, str, str:
	llm = ChatOpenAI(model="gpt-4o-mini") #Requires the api key to be stored in an env variable
	prompt = f"You are an expert text evaluator. You will be given a" \
			 "title and a snippet from a google result in a web search. " \
			 "These belong to linkedin profiles. You will be also given" \
			 "a corporate role at a firm. Your job is to check whether" \ 
			 "in the title or in the snippet, there is the role/a synonim of" \
			 "the role and the firm you were given in input. Then, you will answer" \
			 "one and only one of the following options in the following cases: \n"\
			 "[Option]TRUE: [Case] if the role/synonim at the firm was found in either the snippet or the title\n"\
			 "[Option]MISSING_FIRM: [Case]  if the role or a synonim was found but the firm was missing\n"\
			 "[Option]DIFFERENT_FIRM: [Case] if the role or synonim was found but the firm was different"
			 "[Option]WRONG_ROLE: [Case]  if the role or a synonim wasn't found but the firm matches \n"\
			 "[Option]FALSE: [Case]  if both the role and the firm were missing\n"\
			 "DO NOT ANSWER WITH LONGER MESSAGES. IT IS VITAL THAT YOU ONLY ANSWER WITH THE OPTIONS"\
			 "LISTED ABOVE. Here there is the role and the firm {firm}{expected_role}"\
			 "\n Here there is the title: {title} \n Here there is the snippet: {snippet}".
	search = DuckDuckGoSearchResults(output_format="json")
	# Search for exact URL to get snippet
	    query = f"site:{linkedin_url}"
	    results_json = search.invoke(query)
	    results = json.loads(results_json)
	    
	    for result in results:
	    	link = result.get('link', '')
	    	if is_linkedin_profile_url(link) == True:
		        snippet = result.get('snippet', '')
		        title = result.get('title', '')
		        
		        # Check if expected role is in the snippet/title
		        agent = initialize_agent(llm, agent="conversational-react-description", verbose = False)
		        check = agent.run(prompt)
		        if check == "TRUE":
		            return True, "Perfect match", link, check, title
		     	elif check == "MISSING_FIRM":
		     		return True, "Matching role, missing firm", link, check, title
		     	elif check == "WRONG_ROLE": 
		     		return True, "Wrong role, matching firm", link, check, title
		     	elif check == "DIFFERENT_FIRM":
		     		return True, "Matching role, different firm", link, check, title
	    
	    return False, "No match", link, check, title
