from finder.search import query_builder
from finder.extract import validation
from finder.storage import writers
from finder import models
from finder.logger import setup_logger
from dataclasses import replace
from pathlib import Path
import logging
import math
import csv
import os
import sys
import threading

logger = logging.getLogger("finder.main")


def _process_persons(
	thread_name, persons_chunk, temp_csv_path,
	known_urls, urls_lock,
):
	try:
		for i, (name, firm) in enumerate(persons_chunk, 1):
			try:
				logger.info(f"Processing person {i}/{len(persons_chunk)}: \"{name}\" at \"{firm}\"")
				temporary_person = models.PersonResult(name=name, firm=firm)

				logger.info(f"Searching: person=\"{name}\" firm=\"{firm}\"")
				query = query_builder.query_builder_firm(firm, name)

				goat_tuple = validation.is_correct_person_ai(query, name, firm)
				person_cost = goat_tuple[4]

				if goat_tuple[0] == True:
					url = goat_tuple[2]
					with urls_lock:
						if url in known_urls:
							skip = True
						else:
							known_urls.add(url)
							skip = False
					if skip:
						logger.info(f"Skipping duplicate URL for \"{name}\" at \"{firm}\": {url}")
					else:
						status_map = {"TRUE": models.ResultStatus.TOTAL_MATCH}
						result = replace(temporary_person,
							linkedin_url=url,
							status=status_map.get(goat_tuple[3], models.ResultStatus.NOT_MATCH))
						logger.info(f"MATCH for \"{name}\" at \"{firm}\": url={url} status={goat_tuple[3]}")
						result.to_row()
						writers.append_urls_csv([result], temp_csv_path)
						logger.info(f"Appended result to temp CSV: \"{name}\" at \"{firm}\"")
						logger.info(f"Person \"{name}\" at \"{firm}\" completed — LLM cost: ${person_cost:.6f}")
						continue

				logger.info(f"Person \"{name}\" at \"{firm}\" completed — LLM cost: ${person_cost:.6f}")

				logger.warning(f"No match found for \"{name}\" at \"{firm}\", writing N/A row")
				temporary_person = replace(temporary_person,
					linkedin_url="N/A",
					status=models.ResultStatus.NOT_MATCH)
				temporary_person.to_row()
				writers.append_urls_csv([temporary_person], temp_csv_path)

			except Exception:
				logger.exception(f"Error processing person \"{name}\" at \"{firm}\", skipping")
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

	all_persons = []
	input_persons_path = os.path.join(os.path.dirname(os.getcwd()), "data/Input/persons.csv")
	with open(input_persons_path, newline="") as f:
		persons_csv = csv.DictReader(f)
		for row in persons_csv:
			all_persons.append((row["name"], row["firm"]))

	#-------------------------------
	# Phase 2: Read final CSV state
	#-------------------------------
	final_done_persons, known_urls = writers.read_done_persons_from_csv(output_csv_path)

	logger.info(f"Loaded {len(all_persons)} total persons ({len(final_done_persons)} already in Urls.csv)")

	#--------------------------------------
	# Phase 3: Handle temp CSV state
	#--------------------------------------
	existing_temps = writers.discover_temp_csvs(output_dir)
	old_thread_count = len(existing_temps)

	if old_thread_count == 0:
		# Case A: Fresh run
		logger.info("No temp CSVs found — fresh run")
		pending_persons = [p for p in all_persons if p not in final_done_persons]

	elif old_thread_count == n_threads:
		# Case B: Resume with same thread count
		logger.info(f"Found {old_thread_count} temp CSVs matching thread count — resuming")
		pending_persons = [p for p in all_persons if p not in final_done_persons]

		# Collect all URLs from temp CSVs into known_urls
		temp_done_persons_all = set()
		for temp_path in existing_temps:
			temp_persons, temp_urls = writers.read_done_persons_from_csv(temp_path)
			temp_done_persons_all |= temp_persons
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
		final_done_persons, known_urls = writers.read_done_persons_from_csv(output_csv_path)
		pending_persons = [p for p in all_persons if p not in final_done_persons]

	logger.info(f"{len(pending_persons)} persons pending processing")

	#-----------------------------------------
	# Phase 4: Early exit check
	#-----------------------------------------
	if not pending_persons:
		logger.info("All persons already processed")
		if existing_temps:
			writers.merge_temp_csvs(output_dir, output_csv_path, person_order=all_persons)
			writers.delete_temp_csvs(output_dir)
			logger.info("Merged leftover temp CSVs and cleaned up")
		return

	#-----------------------------------------
	# Phase 5: Split, spawn, join
	#-----------------------------------------
	urls_lock = threading.Lock()

	chunk_size = math.ceil(len(pending_persons) / n_threads)
	persons_split = [pending_persons[i:i + chunk_size] for i in range(0, len(pending_persons), chunk_size)]

	# For Case B (resume), filter each chunk against its temp CSV's done persons
	if old_thread_count == n_threads and old_thread_count > 0:
		filtered_split = []
		for idx, chunk in enumerate(persons_split):
			temp_path = writers.get_temp_csv_path(output_dir, idx)
			done_in_temp, _ = writers.read_done_persons_from_csv(temp_path)
			filtered_chunk = [p for p in chunk if p not in done_in_temp]
			filtered_split.append(filtered_chunk)
		persons_split = filtered_split

	threads = []
	for idx, chunk in enumerate(persons_split):
		if not chunk:
			logger.info(f"Thread-{idx + 1}: no pending persons, skipping")
			continue
		temp_path = writers.get_temp_csv_path(output_dir, idx)
		t = threading.Thread(
			target=_process_persons,
			name=f"Thread-{idx + 1}",
			args=(
				f"Thread-{idx + 1}",
				chunk,
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
	writers.merge_temp_csvs(output_dir, output_csv_path, person_order=all_persons)
	writers.delete_temp_csvs(output_dir)
	logger.info("All threads completed. Results merged and temp files cleaned up.")


if __name__ == "__main__":
	main()
