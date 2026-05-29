import os
import csv
import time
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Absolute path to the Service Account credentials file.
# Stored under C:\IT\Tools\ and protected by NTFS permissions to prevent
# unauthorised access to the Google Sheets Service Account key.
SECURE_CRED_PATH = r"C:\IT\Tools\Benchmark Tool\config\credentials.json"

# Local fallback file path. Used when the Google Sheets API is unreachable
# (e.g. network dropout on the event floor). Results are queued here and
# can be manually uploaded later.
OFFLINE_QUEUE_FILE = r"C:\IT\Tools\Benchmark Tool\offline_queue.csv"


def save_to_offline_queue(row_data: list):
    """
    Fallback mechanism: saves a result row to a local CSV file when the
    Google Sheets API cannot be reached.

    Prevents data loss during network outages on the event floor.
    The CSV header row is written automatically on first use.

    Args:
        row_data (list): The 9-column result row to persist locally.
    """
    try:
        logging.warning("Initiating local fallback storage (offline queue)...")
        file_exists = os.path.isfile(OFFLINE_QUEUE_FILE)

        with open(OFFLINE_QUEUE_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write the header only when creating the file for the first time.
            if not file_exists:
                writer.writerow(["Timestamp", "Hostname", "GPU", "CPU", "RAM", "Application", "Score1", "Score2", "Score3"])
            writer.writerow(row_data)

        logging.info(f"Successfully saved results locally to {OFFLINE_QUEUE_FILE}")

    except Exception as e:
        logging.error(f"CRITICAL: Failed to write to offline queue: {e}")


def upload_results(
    hostname: str,
    gpu: str,
    cpu: str,
    ram: str,
    application: str,
    score1: str,
    score2: str = "N/A",
    score3: str = "N/A"
):
    """
    Uploads a single benchmark result row to the central Google Sheet.

    Row format (9 columns):
        [Date/Time, Hostname, GPU, CPU, RAM, Application, Score1, Score2, Score3]

    Score mapping per benchmark:
        - Score1: Main score   (CS2 Avg FPS / Cyberpunk Avg FPS / 3DMark Total Score)
        - Score2: Sub-score 1  (CS2 P1 Lows / Cyberpunk Min FPS / Time Spy GPU Score)
        - Score3: Sub-score 2  (Time Spy CPU Score — 'N/A' for all other benchmarks)

    On failure, the function retries up to 3 times with exponential backoff (5s, 10s).
    If all retries fail, the result is saved locally via save_to_offline_queue().

    Args:
        hostname (str):    Machine hostname from socket.gethostname().
        gpu (str):         GPU name from Win32_VideoController CIM instance.
        cpu (str):         CPU name from Win32_Processor CIM instance.
        ram (str):         Total RAM as a formatted string (e.g. '32 GB').
        application (str): Human-readable benchmark name (e.g. '3DMark Steel Nomad').
        score1 (str):      Main benchmark score.
        score2 (str):      First sub-score, or 'N/A' if not applicable.
        score3 (str):      Second sub-score, or 'N/A' if not applicable.

    Returns:
        bool: True on successful upload, False if all retries failed.
    """
    logging.info(f"Preparing to upload {application} results to Google Sheets...")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_data = [current_time, hostname, gpu, cpu, ram, application, score1, score2, score3]

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    # Pre-flight check: verify the credentials file exists before attempting any
    # network calls. A missing credentials.json usually indicates a broken deployment
    # or incorrect NTFS permissions — log a clear error and fall back immediately.
    if not os.path.exists(SECURE_CRED_PATH):
        logging.error(f"CRITICAL: Service Account credentials not found at '{SECURE_CRED_PATH}'.")
        logging.error("Check deployment policies and NTFS permissions.")
        save_to_offline_queue(row_data)
        return False

    # Retry loop with exponential backoff — designed for unstable event-floor networks.
    # Waits 5s after the first failure, 10s after the second, then gives up.
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logging.info(f"API connection attempt {attempt + 1} of {max_retries}...")

            creds = ServiceAccountCredentials.from_json_keyfile_name(SECURE_CRED_PATH, scope)
            client = gspread.authorize(creds)

            # IMPORTANT: Update the spreadsheet name and worksheet tab name here if they change.
            sheet = client.open('Event IT Benchmark Results Sheet').worksheet('Leon Test')

            sheet.append_row(row_data)

            logging.info(f"[SUCCESS] Uploaded {application} score for {hostname} to Cloud.")
            return True

        except gspread.exceptions.APIError as api_err:
            logging.warning(f"Google API rate limit or endpoint error: {api_err}")
        except Exception as e:
            logging.warning(f"Network or connection error during upload: {e}")

        # If this was not the last attempt, wait before retrying.
        if attempt < max_retries - 1:
            sleep_time = (attempt + 1) * 5  # 5s after attempt 1, 10s after attempt 2
            logging.info(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

    # All retries exhausted — persist locally to avoid data loss.
    logging.error("All upload attempts failed. Network drops or API offline.")
    save_to_offline_queue(row_data)
    return False
