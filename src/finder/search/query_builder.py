def query_builder (firm, role):
	"""Simple concatenation of strings"""
	try:
		query = "Linkedin profile: " + firm + role
		return query
	except Exception as e:
		print(f"Invalid query: {e}")

	return None
