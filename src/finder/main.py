from finder.search import query_builder, web_search
from finder.extract import linkedin_validator, validation
from finder.storage import writers
from finder import models
from finder.logger import setup_logger
from dataclasses import replace
from pathlib import Path
import logging
import yaml, csv

logger = logging.getLogger("finder.main")

def main():
	setup_logger(level=logging.INFO)

	#-----------------------------------------
	#Opening documents and defining paths
	#-----------------------------------------
	output_csv_path = Path("data/Output/Urls.csv")
	with open("data/Input/roles.yaml", "r") as file:
		roles_data = yaml.safe_load(file)

	priorities = [
	    roles_data["Highest priority"],
	    roles_data["Medium priority"],
	    roles_data["Lower priority"]
	]

	firms = []
	with open("data/Input/firms.csv", newline = "") as f:
		firms_csv = csv.DictReader(f)
		for row in firms_csv:
			firms.append(row["firms"])

	logger.info(f"Loaded {len(firms)} firms and {len(priorities)} priority tiers")

	for i, firm in enumerate(firms, 1):
		logger.info(f"Processing firm {i}/{len(firms)}: \"{firm}\"")
		temporary_firm = models.RoleResult(firm = firm, role = "N/A")

		#-------------------------
		# Web search
		#-------------------------
		stop = False
		found = False
		for roles in priorities:
			for role in roles:
				logger.info(f"Searching: firm=\"{firm}\" role=\"{role}\"")
				query = query_builder.query_builder_firm(firm, role)
				first_search_results = web_search.safe_search_with_backoff(query)

				if first_search_results is None:
					logger.warning(f"Search returned no results for query \"{query}\"")
					continue

				#------------------------
				# Double Filtering
				#------------------------
				filtered_linkedin_results = []
				for top_results in first_search_results:
					if (linkedin_validator.is_linkedin_profile_url(top_results.url) == True):
						filtered_linkedin_results.append(top_results.url)

				logger.info(f"Google returned {len(first_search_results)} results, {len(filtered_linkedin_results)} are LinkedIn profiles")

				for top_filtered_results in filtered_linkedin_results:
					goat_tuple = validation.is_correct_role_ai(top_filtered_results, role, firm)
					if (goat_tuple[0] == True):
						temporary_firm = replace(temporary_firm, role = role,
							linkedin_url = goat_tuple[2], name = goat_tuple[4],
							status = goat_tuple[3])
						logger.info(f"MATCH for \"{firm}\": role=\"{role}\" url={goat_tuple[2]} status={goat_tuple[3]}")
						temporary_firm.to_row()
						writers.append_urls_csv([temporary_firm], output_csv_path)
						logger.info(f"Appended result to CSV: \"{firm}\" — {role}")
						stop = True
						found = True
						break
			if stop:
				break

		if found == False:
			logger.warning(f"No match found for \"{firm}\", writing N/A row")
			temporary_firm = replace(temporary_firm, role = "N/A",
				linkedin_url = "N/A", name = "N/A",
				status = models.ResultStatus.NOT_MATCH)
			temporary_firm.to_row()
			writers.append_urls_csv([temporary_firm], output_csv_path)
