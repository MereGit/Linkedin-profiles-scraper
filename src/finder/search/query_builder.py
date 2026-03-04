"""
Builds the queries in the loop of the main function.
@arg firm (str): firm of the role we want to search for.
@arg role(str): role we want to search for.
@returns str containing the query
"""

def query_builder_firm (firm:str, role:str) -> str:
	"""Simple concatenation of strings"""
	try:
		query = f"Linkedin profile: {firm} {role}" 
		return query
	except Exception as e:
		print(f"Invalid query: {e}")

	return None
