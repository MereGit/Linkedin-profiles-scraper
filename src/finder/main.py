from finder.search import query_builder
from finder.extract import validation
from finder.storage import writers
from finder import models
from finder.logger import setup_logger
from dataclasses import replace
from pathlib import Path
import logging
import math
import yaml, csv
import os
import sys
import threading

logger = logging.getLogger("finder.main")


def _process_firms(
	thread_name, firms_chunk, priorities, temp_csv_path,
	known_urls, urls_lock,
):
	try:
		for i, firm in enumerate(firms_chunk, 1):
			try:
				logger.info(f"Processing firm {i}/{len(firms_chunk)}: \"{firm}\"")
				temporary_firm = models.RoleResult(firm=firm, role="N/A")

				max_profiles = 2
				matches_found = 0
				firm_cost = 0.0
				found_urls = set()
				for roles in priorities:
					for role in roles:
						logger.info(f"Searching: firm=\"{firm}\" role=\"{role}\"")
						query = query_builder.query_builder_firm(firm, role)

						goat_tuple = validation.is_correct_role_ai(query, role, firm)
						firm_cost += goat_tuple[5]
						if goat_tuple[0] == True:
							url = goat_tuple[2]
							with urls_lock:
								if url in found_urls or url in known_urls:
									skip = True
								else:
									known_urls.add(url)
									skip = False
							if skip:
								logger.info(f"Skipping duplicate URL for \"{firm}\": {url}")
								continue

							status_map = {"TRUE": models.ResultStatus.TOTAL_MATCH}
							result = replace(temporary_firm, role=role,
								linkedin_url=url, name=goat_tuple[4],
								status=status_map.get(goat_tuple[3], models.ResultStatus.NOT_MATCH))
							logger.info(f"MATCH for \"{firm}\": role=\"{role}\" url={url} status={goat_tuple[3]}")
							result.to_row()
							writers.append_urls_csv([result], temp_csv_path)
							logger.info(f"Appended result to temp CSV: \"{firm}\" — {role}")
							found_urls.add(url)
							matches_found += 1
							break  # skip to next priority level
					if matches_found >= max_profiles:
						break

				logger.info(f"Firm \"{firm}\" completed — total LLM cost: ${firm_cost:.6f}")

				if matches_found == 0:
					logger.warning(f"No match found for \"{firm}\", writing N/A row")
					temporary_firm = replace(temporary_firm, role="N/A",
						linkedin_url="N/A", name="N/A",
						status=models.ResultStatus.NOT_MATCH)
					temporary_firm.to_row()
					writers.append_urls_csv([temporary_firm], temp_csv_path)

			except Exception:
				logger.exception(f"Error processing firm \"{firm}\", skipping")
				continue
	except Exception:
		logger.exception(f"[{thread_name}] Fatal error, thread terminating")


def main():
	setup_logger(level=logging.INFO)

	#---------------------
	# Phase 1: Load inputs
	#---------------------
	if len(sys.argv) > 1 and sys.argv[1].isdigit():
		n_threads = int(sys.argv[1])
		logger.info(f"Using {n_threads} threads for processing")
	else:
		n_threads = 1
		logger.info("No valid thread count provided, defaulting to 1 thread")

	output_csv_path = Path(os.path.join(os.path.dirname(os.getcwd()), "data/Output/Urls.csv"))
	output_dir = output_csv_path.parent
	input_roles_path = os.path.join(os.path.dirname(os.getcwd()), "data/Input/roles.yaml")
	with open(input_roles_path, "r") as file:
		roles_data = yaml.safe_load(file)

	priorities = [
	    roles_data["Highest priority"],
	    roles_data["Medium priority"],
	    roles_data["Lower priority"]
	]

	all_firms = []
	input_firms_path = os.path.join(os.path.dirname(os.getcwd()), "data/Input/firms.csv")
	with open(input_firms_path, newline="") as f:
		firms_csv = csv.DictReader(f)
		for row in firms_csv:
			all_firms.append(row["firms"])

	#-------------------------------
	# Phase 2: Read final CSV state
	#-------------------------------
	final_done_firms, known_urls = writers.read_done_firms_from_csv(output_csv_path)

	logger.info(f"Loaded {len(all_firms)} total firms ({len(final_done_firms)} already in Urls.csv)")

	#--------------------------------------
	# Phase 3: Handle temp CSV state
	#--------------------------------------
	existing_temps = writers.discover_temp_csvs(output_dir)
	old_thread_count = len(existing_temps)

	if old_thread_count == 0:
		# Case A: Fresh run
		logger.info("No temp CSVs found — fresh run")
		pending_firms = [f for f in all_firms if f not in final_done_firms]

	elif old_thread_count == n_threads:
		# Case B: Resume with same thread count
		logger.info(f"Found {old_thread_count} temp CSVs matching thread count — resuming")
		pending_firms = [f for f in all_firms if f not in final_done_firms]

		# Collect all URLs from temp CSVs into known_urls
		temp_done_firms_all = set()
		for temp_path in existing_temps:
			temp_firms, temp_urls = writers.read_done_firms_from_csv(temp_path)
			temp_done_firms_all |= temp_firms
			known_urls |= temp_urls

	else:
		# Case C: Thread count mismatch — merge old temps into Urls.csv, restart fresh
		logger.warning(
			f"Thread count mismatch: {old_thread_count} temp CSVs exist "
			f"but {n_threads} threads requested. Merging old temps into Urls.csv."
		)
		# Append old temp rows into Urls.csv so partial work is preserved
		for temp_path in existing_temps:
			temp_rows = writers.read_csv_rows(temp_path)
			if temp_rows:
				writers.append_urls_csv(temp_rows, output_csv_path)
		writers.delete_temp_csvs(output_dir)

		# Re-read the updated Urls.csv
		final_done_firms, known_urls = writers.read_done_firms_from_csv(output_csv_path)
		pending_firms = [f for f in all_firms if f not in final_done_firms]

	logger.info(f"{len(pending_firms)} firms pending processing")

	#-----------------------------------------
	# Phase 4: Early exit check
	#-----------------------------------------
	if not pending_firms:
		logger.info("All firms already processed")
		if existing_temps:
			writers.merge_temp_csvs(output_dir, output_csv_path, firm_order=all_firms)
			writers.delete_temp_csvs(output_dir)
			logger.info("Merged leftover temp CSVs and cleaned up")
		return

	#-----------------------------------------
	# Phase 5: Split, spawn, join
	#-----------------------------------------
	urls_lock = threading.Lock()

	chunk_size = math.ceil(len(pending_firms) / n_threads)
	firms_split = [pending_firms[i:i + chunk_size] for i in range(0, len(pending_firms), chunk_size)]

	# For Case B (resume), filter each chunk against its temp CSV's done firms
	if old_thread_count == n_threads and old_thread_count > 0:
		filtered_split = []
		for idx, chunk in enumerate(firms_split):
			temp_path = writers.get_temp_csv_path(output_dir, idx)
			done_in_temp, _ = writers.read_done_firms_from_csv(temp_path)
			filtered_chunk = [f for f in chunk if f not in done_in_temp]
			filtered_split.append(filtered_chunk)
		firms_split = filtered_split

	threads = []
	for idx, chunk in enumerate(firms_split):
		if not chunk:
			logger.info(f"Thread-{idx + 1}: no pending firms, skipping")
			continue
		temp_path = writers.get_temp_csv_path(output_dir, idx)
		t = threading.Thread(
			target=_process_firms,
			name=f"Thread-{idx + 1}",
			args=(
				f"Thread-{idx + 1}",
				chunk,
				priorities,
				temp_path,
				known_urls,
				urls_lock,
			),
		)
		threads.append(t)

	for t in threads:
		t.start()

	for t in threads:
		t.join()

	#-----------------------------------------
	# Phase 6: Merge and cleanup
	#-----------------------------------------
	writers.merge_temp_csvs(output_dir, output_csv_path, firm_order=all_firms)
	writers.delete_temp_csvs(output_dir)
	logger.info("All threads completed. Results merged and temp files cleaned up.")


if __name__ == "__main__":
	main()
