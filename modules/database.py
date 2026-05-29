import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime


def upload_results(pc_id, benchmark_name, score):
    """
    Uploads a single benchmark result row to the central Google Sheet.

    The row is appended in the following format:
        [Date/Time, Hostname, Benchmark Name, Score]

    NOTE: The current implementation uses a simplified 4-column layout.
    The Admin Manual specifies a 9-column format:
        [Date/Time, Hostname, GPU, CPU, RAM, App, Score1, Score2, Score3]
    Extend this function's signature and row_data list when hardware info
    extraction is added to the benchmark modules.

    Args:
        pc_id (str): The hostname of the test machine (from socket.gethostname()).
        benchmark_name (str): Human-readable name of the benchmark run (e.g. '3DMark Steel Nomad').
        score (str): The extracted benchmark score as a string (e.g. '18423' or '112 FPS').

    Returns:
        bool: True on successful upload, False if any error occurred.
    """
    print(f"\nAttempting to upload results to Google Sheets...")

    # Required OAuth2 scopes for reading and writing Google Sheets via the Sheets & Drive APIs.
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        # Authenticate using the Service Account key file.
        # The credentials.json file must be placed in the script's root directory
        # (C:\IT\Tools\BenchmarkTool) and the target Sheet must be shared with the
        # Service Account's email address (Editor permissions required).
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)

        # Open the target spreadsheet by its exact name and select the target worksheet.
        # IMPORTANT: Update the spreadsheet name and worksheet tab name here if they change.
        sheet = client.open('Event IT Benchmark Results Sheet').worksheet('Leon Test')

        # Build the data row and append it as a new entry at the bottom of the sheet.
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [current_time, pc_id, benchmark_name, score]

        sheet.append_row(row_data)

        print(f"[SUCCESS] Uploaded {benchmark_name} score ({score}) for {pc_id}.")
        return True

    except Exception as e:
        # Covers network failures, invalid credentials, wrong spreadsheet name, etc.
        # The full error is printed to the console for debugging.
        print(f"[ERROR] Failed to upload to Google Sheets: {e}")
        return False
