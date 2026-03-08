from finder.search import query_builder
from finder.extract import linkedin_validator, validation
from finder.storage import writers
from finder import models
from finder.logger import setup_logger
from dataclasses import replace
from pathlib import Path
import logging
import yaml, csv
import os



logger = logging.getLogger("finder.main")

def main():
	setup_logger(level=logging.INFO)
	#-----------------------------------------
	#Opening documents and defining paths
	#-----------------------------------------
	output_csv_path = Path(os.path.join(os.path.dirname(os.getcwd()), "data/Output/Urls.csv"))
	input_roles_path = os.path.join(os.path.dirname(os.getcwd()), "data/Input/roles.yaml")
	with open(input_roles_path, "r") as file:
		roles_data = yaml.safe_load(file)

	priorities = [
	    roles_data["Highest priority"],
	    roles_data["Medium priority"],
	    roles_data["Lower priority"]
	]

	# Load firms already processed in the output CSV
	already_done = set()
	if output_csv_path.exists():
		with open(output_csv_path, newline="", encoding="utf-8") as f:
			for row in csv.DictReader(f):
				already_done.add(row["firm"])

	firms = []
	input_firms_path = os.path.join(os.path.dirname(os.getcwd()), "data/Input/firms.csv")
	with open(input_firms_path, newline = "") as f:
		firms_csv = csv.DictReader(f)
		for row in firms_csv:
			if row["firms"] not in already_done:
				firms.append(row["firms"])

	logger.info(f"Loaded {len(firms)} new firms ({len(already_done)} already processed) and {len(priorities)} priority tiers")

	for i, firm in enumerate(firms, 1):
		logger.info(f"Processing firm {i}/{len(firms)}: \"{firm}\"")
		temporary_firm = models.RoleResult(firm = firm, role = "N/A")

		#-------------------------
		# Web search
		#-------------------------
		max_profiles = 2
		matches_found = 0
		for roles in priorities:
			for role in roles:
				logger.info(f"Searching: firm=\"{firm}\" role=\"{role}\"")
				query = query_builder.query_builder_firm(firm, role)

				#----------------------------
				# Search and validation
				#----------------------------

				goat_tuple = validation.is_correct_role_ai(query, role, firm)
				if (goat_tuple[0] == True):
					status_map = {"TRUE": models.ResultStatus.TOTAL_MATCH,
						"MISSING_FIRM": models.ResultStatus.MISSING_FIRM}
					result = replace(temporary_firm, role = role,
						linkedin_url = goat_tuple[2], name = goat_tuple[4],
						status = status_map.get(goat_tuple[3], models.ResultStatus.NOT_MATCH))
					logger.info(f"MATCH for \"{firm}\": role=\"{role}\" url={goat_tuple[2]} status={goat_tuple[3]}")
					result.to_row()
					writers.append_urls_csv([result], output_csv_path)
					logger.info(f"Appended result to CSV: \"{firm}\" — {role}")
					matches_found += 1
					if matches_found >= max_profiles:
						break
			if matches_found >= max_profiles:
				break

		if matches_found == 0:
			logger.warning(f"No match found for \"{firm}\", writing N/A row")
			temporary_firm = replace(temporary_firm, role = "N/A",
				linkedin_url = "N/A", name = "N/A",
				status = models.ResultStatus.NOT_MATCH)
			temporary_firm.to_row()
			writers.append_urls_csv([temporary_firm], output_csv_path)

if __name__ == "__main__":
	main()
