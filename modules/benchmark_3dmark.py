import os
import time
import socket
import pyautogui
import glob
import zipfile
import re
from modules.vision import click_image
from modules.database import upload_results


def get_latest_score():
    """
    Locates the most recently created 3DMark result file in the user's Documents folder,
    reads it as a ZIP archive in memory, and extracts the numeric score from the XML inside.

    3DMark saves results as .3dmark-result files, which are standard ZIP archives
    containing a Result.xml file with a <Score> tag holding the total benchmark score.

    Returns:
        str: The extracted score as a string (e.g. '18423'),
             'N/A' if no result files were found,
             or 'ERROR' if the file could not be parsed.
    """
    # Default save path for 3DMark auto-saves on Windows.
    docs_path = os.path.join(os.environ['USERPROFILE'], 'Documents', '3DMark')
    search_pattern = os.path.join(docs_path, '*.3dmark-result')

    list_of_files = glob.glob(search_pattern)

    if not list_of_files:
        print("  [ERROR] No 3DMark result files found in Documents.")
        return "N/A"

    # Select the newest file by creation timestamp to avoid reading stale results
    # from a previous benchmark session.
    latest_file = max(list_of_files, key=os.path.getctime)
    print(f"  -> Parsing result file: {os.path.basename(latest_file)}")

    try:
        # A .3dmark-result file is a renamed ZIP archive — open it directly with zipfile.
        with zipfile.ZipFile(latest_file, 'r') as z:
            with z.open('Result.xml') as f:
                xml_content = f.read().decode('utf-8')

                # Search for the <Score>...</Score> tag that holds the total benchmark score.
                match = re.search(r'<Score>(\d+)</Score>', xml_content, re.IGNORECASE)

                if match:
                    score = match.group(1)
                    print(f"  [SUCCESS] Extracted score: {score}")
                    return score
                else:
                    print("  [ERROR] Could not find the <Score> tag in Result.xml.")
                    return "ERROR"

    except Exception as e:
        print(f"  [ERROR] Failed to read result file: {e}")
        return "ERROR"


def run_3dmark():
    """
    Main routine for running both 3DMark benchmarks sequentially:
      1. Steel Nomad
      2. Time Spy Extreme

    The function controls 3DMark entirely via image recognition (click_image).
    After each benchmark completes, the score is extracted from the saved result
    file and uploaded to Google Sheets.

    Returns:
        bool: True if both benchmarks completed and results were uploaded,
              False if any critical step (image not found, launch failure) failed.
    """
    print("\n--- Starting 3DMark Full Routine (Steel Nomad + Time Spy Extreme) ---")

    dmark_path = r"C:\IT\Tools\3DMark\3DMark.exe"

    try:
        print(f"Launching standalone 3DMark from: {dmark_path}")

        if os.path.exists(dmark_path):
            os.startfile(dmark_path)
            # Allow enough time for 3DMark to fully load its UI before any clicks are attempted.
            print("Waiting 15 seconds for 3DMark to load...")
            time.sleep(15)

            # ==========================================
            # PART 1: STEEL NOMAD
            # ==========================================
            print("\n--- Phase 1: Steel Nomad ---")

            print("Step 1: Looking for the 'Benchmarks' tab...")
            if not click_image('data/3dmark_benchmarks_tab.png', confidence=0.8, timeout=30):
                return False
            time.sleep(2)

            # Move the mouse into the scrollable benchmark list area before scrolling.
            # PyAutoGUI's scroll() acts on the element under the cursor.
            print("Moving mouse down to scrollable area...")
            pyautogui.move(0, 300, duration=0.2)
            time.sleep(0.5)

            # Scroll down to bring the Steel Nomad entry into view.
            print("Step 2: Scrolling down to reveal Steel Nomad (-500)...")
            pyautogui.scroll(-500)
            time.sleep(2)

            print("Step 3: Looking for 'Steel Nomad' icon...")
            if not click_image('data/3dmark_steel_nomad.png', confidence=0.8, timeout=10):
                return False
            time.sleep(2)

            print("Step 4: Looking for the 'Run' button...")
            if not click_image('data/3dmark_run.png', confidence=0.8, timeout=10):
                return False

            # Steel Nomad is a GPU-intensive benchmark — allow up to 5 minutes for completion.
            # Adjust this value if the benchmark consistently times out on slower hardware.
            print("Steel Nomad benchmark started! Waiting 300 seconds for completion...")
            time.sleep(300)

            # Read the actual score from the auto-saved result file rather than relying
            # on OCR or on-screen parsing, which is less reliable.
            print("Extracting score from saved result file...")
            steel_nomad_score = get_latest_score()

            pc_name = socket.gethostname()
            print(f"Uploading Steel Nomad results ({steel_nomad_score}) for {pc_name} to Google Sheets...")
            upload_results(pc_name, "3DMark Steel Nomad", steel_nomad_score)
            print("Steel Nomad completed successfully.")

            # ==========================================
            # PART 2: TIME SPY EXTREME
            # ==========================================
            print("\n--- Phase 2: Time Spy Extreme ---")

            # Navigate back to the benchmark list to select the next test.
            print("Step 5: Clicking 'Benchmarks' tab again to return to menu...")
            if not click_image('data/3dmark_benchmarks_tab.png', confidence=0.8, timeout=30):
                return False
            time.sleep(2)

            print("Moving mouse down to scrollable area...")
            pyautogui.move(0, 300, duration=0.2)
            time.sleep(0.5)

            # Time Spy Extreme is listed further down in the list than Steel Nomad,
            # so a larger scroll value is needed.
            print("Step 6: Scrolling down to reveal Time Spy Extreme (-800)...")
            pyautogui.scroll(-800)
            time.sleep(2)

            print("Step 7: Looking for 'Time Spy Extreme' icon...")
            if not click_image('data/3dmark_timespy.png', confidence=0.8, timeout=10):
                return False
            time.sleep(2)

            print("Step 8: Looking for the 'Run' button...")
            if not click_image('data/3dmark_run.png', confidence=0.8, timeout=10):
                return False

            print("Time Spy Extreme benchmark started! Waiting 300 seconds for completion...")
            time.sleep(300)

            print("Extracting score from saved result file...")
            time_spy_score = get_latest_score()

            print(f"Uploading Time Spy Extreme results ({time_spy_score}) for {pc_name} to Google Sheets...")
            upload_results(pc_name, "3DMark Time Spy Extreme", time_spy_score)

            print("\n>>> All 3DMark routines finished successfully. <<<")
            return True

        else:
            print(f"[ERROR] Could not find 3DMark executable at: {dmark_path}")
            print("        Please verify the installation path in benchmark_3dmark.py.")
            return False

    except Exception as e:
        print(f"[ERROR] Exception while running 3DMark routine: {e}")
        return False
