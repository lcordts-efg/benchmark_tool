import os
import time
import socket
import pyautogui
import glob
import zipfile
import re
import subprocess
import logging
from modules.vision import click_image
from modules import googlecloud


def wait_for_new_file(directory: str, extension: str, start_time: float, timeout_sec: int) -> str:
    """
    Polls the filesystem for a newly created file with the given extension.

    Replaces brittle static time.sleep() waits with event-driven file monitoring.
    Only files created after start_time are considered valid — this prevents the
    function from accidentally matching a result file left over from a previous run.

    Args:
        directory (str):   Path to the folder to monitor (e.g. the 3DMark Documents folder).
        extension (str):   File extension to watch for (e.g. '.3dmark-result').
        start_time (float): Unix timestamp of when the current benchmark run was started.
                            Used to filter out pre-existing files.
        timeout_sec (int): Maximum seconds to poll before giving up.

    Returns:
        str: Full path to the newly detected file, or None if the timeout was reached.
    """
    logging.info(f"Monitoring '{directory}' for new '{extension}' files. Timeout: {timeout_sec}s.")
    pattern = os.path.join(directory, f"*{extension}")

    poll_start = time.time()
    while time.time() - poll_start < timeout_sec:
        files = glob.glob(pattern)
        if files:
            latest_file = max(files, key=os.path.getctime)

            # Only accept files created during the current run to avoid uploading
            # a stale result file from a previous session.
            if os.path.getctime(latest_file) > start_time:
                logging.info(f"New result file detected: {os.path.basename(latest_file)}")
                # Brief pause to ensure the OS has fully released the file handle
                # and finished writing all bytes before we attempt to open it.
                time.sleep(2)
                return latest_file

        # Poll every 3 seconds to balance responsiveness and CPU load.
        time.sleep(3)

    logging.error(f"TIMEOUT: No new {extension} file generated within {timeout_sec} seconds.")
    return None


def get_latest_score(file_path: str, benchmark_name: str):
    """
    Parses a 3DMark result file and extracts the relevant scores via regex.

    3DMark saves results as .3dmark-result files, which are ZIP archives containing
    a Result.xml file. Scores are read from named XML tags that differ per benchmark.

    Supported benchmark_name values and their returned scores:
        - 'Steel Nomad':       (overall_score, 'N/A', 'N/A')
        - 'Time Spy Extreme':  (overall_score, 'GPU: <score>', 'CPU: <score>')

    Args:
        file_path (str):      Full path to the .3dmark-result file.
        benchmark_name (str): Name of the benchmark to determine which XML tags to parse.

    Returns:
        tuple[str, str, str]: (score1, score2, score3) — 'N/A' or 'ERROR' for missing values.
    """
    if not file_path or not os.path.exists(file_path):
        logging.error("Invalid file path provided for parsing.")
        return "N/A", "N/A", "N/A"

    logging.info(f"Parsing result file in memory: {os.path.basename(file_path)}")

    try:
        # A .3dmark-result file is a renamed ZIP archive — open it directly.
        with zipfile.ZipFile(file_path, 'r') as z:
            with z.open('Result.xml') as f:
                xml_content = f.read().decode('utf-8')

                if benchmark_name == "Time Spy Extreme":
                    match_overall = re.search(r'<TimeSpyExtreme3DMarkScore>(\d+)</TimeSpyExtreme3DMarkScore>', xml_content, re.IGNORECASE)
                    match_gpu = re.search(r'<TimeSpyExtremeGraphicsScore>(\d+)</TimeSpyExtremeGraphicsScore>', xml_content, re.IGNORECASE)
                    match_cpu = re.search(r'<TimeSpyExtremeCPUScore>(\d+)</TimeSpyExtremeCPUScore>', xml_content, re.IGNORECASE)

                    if match_overall and match_gpu and match_cpu:
                        overall_score = match_overall.group(1)
                        gpu_score = f"GPU: {match_gpu.group(1)}"
                        cpu_score = f"CPU: {match_cpu.group(1)}"
                        logging.info(f"Extracted Time Spy Extreme: Score {overall_score}, {gpu_score}, {cpu_score}")
                        return overall_score, gpu_score, cpu_score
                    else:
                        logging.error("Failed to find XML tags for Time Spy Extreme.")
                        return "ERROR", "ERROR", "ERROR"

                elif benchmark_name == "Steel Nomad":
                    match = re.search(r'<SteelNomadDx123DMarkScore>(\d+)</SteelNomadDx123DMarkScore>', xml_content, re.IGNORECASE)

                    if match:
                        overall_score = match.group(1)
                        logging.info(f"Extracted Steel Nomad: Score {overall_score}")
                        return overall_score, "N/A", "N/A"
                    else:
                        logging.error("Failed to find XML tags for Steel Nomad.")
                        return "ERROR", "ERROR", "ERROR"

    except zipfile.BadZipFile:
        logging.error(f"File '{file_path}' is corrupted or still locked by the OS.")
        return "ERROR", "ERROR", "ERROR"
    except Exception as e:
        logging.error(f"Failed to read result file: {e}")
        return "ERROR", "ERROR", "ERROR"


def run_3dmark():
    """
    Main routine for running both 3DMark benchmarks sequentially:
      1. Steel Nomad
      2. Time Spy Extreme

    Hardware specs (CPU, GPU, RAM) are queried once via PowerShell CIM instances
    at the start of the routine and reused for both uploads.

    Result files are detected via filesystem polling (wait_for_new_file) rather
    than static sleep() calls, making the routine resilient to hardware performance
    variance across different test machines.

    After both benchmarks complete, 3DMark.exe is forcefully terminated to free
    VRAM before the next benchmark module starts.

    Returns:
        bool: True if the routine completed, False on any fatal error.
    """
    logging.info("--- Starting 3DMark Full Routine (Steel Nomad + Time Spy Extreme) ---")

    dmark_path = r"C:\IT\Tools\3DMark\3DMark.exe"
    docs_path = os.path.join(os.environ['USERPROFILE'], 'Documents', '3DMark')

    try:
        if not os.path.exists(dmark_path):
            logging.error(f"Could not find 3DMark executable at: {dmark_path}")
            logging.error("Verify the installation path in benchmark_3dmark.py.")
            return False

        logging.info(f"Launching 3DMark process from: {dmark_path}")
        os.startfile(dmark_path)

        # Static sleep is acceptable here — there is no file or UI event to poll for
        # during the initial application load, so we simply wait for the GUI to render.
        logging.info("Waiting 40 seconds for 3DMark GUI to initialize...")
        time.sleep(40)

        # Query hardware specs via native Windows CIM (WMI) instances.
        # This avoids any dependency on third-party tools like HWiNFO or CPU-Z.
        pc_name = socket.gethostname()
        logging.info("Querying hardware specifications via PowerShell CIM instances...")
        try:
            cpu = subprocess.check_output(
                ['powershell', '-Command', '(Get-CimInstance Win32_Processor).Name']
            ).decode().strip()

            gpu_output = subprocess.check_output(
                ['powershell', '-Command', '(Get-CimInstance Win32_VideoController).Name']
            ).decode().strip()
            # On multi-GPU systems, only the first adapter (primary GPU) is used.
            gpu = gpu_output.split('\n')[0].strip()

            ram_bytes = subprocess.check_output(
                ['powershell', '-Command', '(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory']
            ).decode().strip()
            ram = f"{round(int(ram_bytes) / (1024 ** 3))} GB"

        except Exception as hw_error:
            logging.warning(f"Hardware query failed, falling back to placeholder values: {hw_error}")
            cpu, gpu, ram = "Unknown CPU", "Unknown GPU", "Unknown RAM"

        # ==========================================
        # PART 1: STEEL NOMAD
        # ==========================================
        logging.info("--- Phase 1: Steel Nomad ---")

        if not click_image('data/3dmark_benchmarks_tab.png', timeout=30):
            return False
        time.sleep(2)

        # Move the cursor into the scrollable benchmark list before scrolling.
        # pyautogui.scroll() acts on whichever element is currently under the cursor.
        pyautogui.move(0, 300, duration=0.2)
        time.sleep(0.5)
        pyautogui.scroll(-500)  # Scroll down to bring Steel Nomad into view.
        time.sleep(2)

        if not click_image('data/3dmark_steel_nomad.png', timeout=10):
            return False
        time.sleep(2)
        if not click_image('data/3dmark_run.png', timeout=10):
            return False

        logging.info("Steel Nomad benchmark initiated. Awaiting OS file creation event...")
        run_start_time = time.time()

        # Event-driven wait: poll for the result file instead of sleeping for a fixed
        # 110 seconds. The 180s timeout gives even slow machines plenty of headroom.
        result_file_sn = wait_for_new_file(docs_path, ".3dmark-result", run_start_time, timeout_sec=180)

        if result_file_sn:
            sn_score, sn_gpu, sn_cpu = get_latest_score(result_file_sn, "Steel Nomad")
            googlecloud.upload_results(pc_name, gpu, cpu, ram, "3DMark Steel Nomad", sn_score, sn_gpu, sn_cpu)
        else:
            logging.error("Skipping Google Cloud upload for Steel Nomad due to missing result file.")

        # ==========================================
        # PART 2: TIME SPY EXTREME
        # ==========================================
        logging.info("--- Phase 2: Time Spy Extreme ---")

        if not click_image('data/3dmark_benchmarks_tab.png', timeout=30):
            return False
        time.sleep(2)

        pyautogui.move(0, 300, duration=0.2)
        time.sleep(0.5)
        # Time Spy Extreme is listed further down the list than Steel Nomad,
        # so a larger scroll value is needed.
        pyautogui.scroll(-800)
        time.sleep(2)

        if not click_image('data/3dmark_timespy.png', timeout=10):
            return False
        time.sleep(2)
        if not click_image('data/3dmark_run.png', timeout=10):
            return False

        logging.info("Time Spy Extreme benchmark initiated. Awaiting OS file creation event...")
        run_start_time = time.time()

        # The 500s timeout accounts for the longer Time Spy Extreme render time.
        result_file_tse = wait_for_new_file(docs_path, ".3dmark-result", run_start_time, timeout_sec=500)

        if result_file_tse:
            tse_score, tse_gpu, tse_cpu = get_latest_score(result_file_tse, "Time Spy Extreme")
            googlecloud.upload_results(pc_name, gpu, cpu, ram, "3DMark Time Spy Extreme", tse_score, tse_gpu, tse_cpu)
        else:
            logging.error("Skipping Google Cloud upload for Time Spy Extreme due to missing result file.")

        # Force-kill 3DMark to free VRAM before the next benchmark module (Cyberpunk / CS2) starts.
        # Output is suppressed (>nul 2>&1) to keep the log clean.
        logging.info("Forcefully terminating 3DMark.exe to free VRAM for subsequent suite modules.")
        os.system("taskkill /f /im 3DMark.exe >nul 2>&1")

        logging.info(">>> 3DMark routine completed. <<<")
        return True

    except Exception as e:
        logging.error(f"Fatal exception during 3DMark execution: {e}")
        return False
