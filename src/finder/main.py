from finder.search import query_builder, web_search
from finder.extract import linkedin_validator, validation
from finder.storage import writers
from finder import models
import yaml, csv

def main():

	#-----------------------------------------
	#Opening documents and defining paths
	#-----------------------------------------
	csv_path = "data/Output/Urls.csv"
	with open("../data/Input/roles.yaml", "r") as file:
		roles_data = yaml.safe_load(file)

	priorities = [
	    roles_data["Highest priority"],
	    roles_data["Medium priority"],
	    roles_data["Lower priority"]
	]

	with open("../data/Input/firms.csv", newline = "") as f:
		firms_csv = csv.reader(f)

	firms = []
	for row in firms_csv:
		firms.append(row["firms"])

	for firm in firms:
		temporary_firm = RoleResult(firm = firm, role = "N/A")

		#-------------------------
		# Web search
		#-------------------------
		stop = False
		found = False
		for roles in priorities:
			for role in roles:
				query = query_builder_firm(firm, role)
				first_search_results = safe_search_with_backoff(query)

				#------------------------
				# Double Filtering
				#------------------------
				filtered_linkedin_results = []
				for top_results in first_search_results:
					if (is_linkedin_profile_url(top_results.url) == True):
						filtered_linkedin_results.append(top_results.url)

				for top_filtered_results in filtered_linkedin_results:
					goat_tuple = is_correct_role_ai(top_filtered_results)
					print(goat_tuple[1])
					if (goat_tuple[0] == True):
						temporary_firm = replace(temporary_firm, role = role, 
							linkedin_url = goat_tuple[2], name = goat_tuple[4], 
							status = goat_tuple [3])
						temporary_firm.to_row()
						write_csv(temporary_firm, csv_path)
						stop = True
						found = True
						break
			if stop:
				break
		if stop:
			break
			stop = False

		if found == False :
			temporary_firm = replace(temporary_firm, role = "N/A", 
							linkedin_url = "N/A", name = "N/A", 
							status = "Not found")
						temporary_firm.to_row()
						write_csv(temporary_firm, csv_path)





