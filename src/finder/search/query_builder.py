"""
Builds the queries in the loop of the main function.
@arg firm (str): firm of the person we want to search for.
@arg person_name(str): name of the person we want to search for.
@returns str containing the query
"""

import logging

logger = logging.getLogger("finder.search.query_builder")

def query_builder_firm (firm:str, person_name:str) -> str:
	"""Simple concatenation of strings"""
	try:
		query = f"site:it.linkedin.com/in/ {person_name} {firm}"
		logger.debug(f"Built query: \"{query}\"")
		return query
	except Exception as e:
		logger.error(f"Invalid query: {e}")

	return None
