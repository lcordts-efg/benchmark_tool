import os
import time
import socket
import pyautogui
import json
import glob
import subprocess
import logging
from modules.vision import click_image
from modules import googlecloud


def abort_cyberpunk(msg: str):
    """
    Fail-safe shutdown: logs the error and force-kills both the game and the CDPR launcher.

    Prevents zombie processes from blocking subsequent benchmark modules in the suite.
    Without this, a crashed Cyberpunk instance holding the GPU would cause CS2 to fail.

    Args:
        msg (str): Error description to log before terminating.

    Returns:
        bool: Always returns False so callers can use 'return abort_cyberpunk(...)'.
    """
    logging.error(f"CRITICAL: {msg}")
    logging.info("Initiating force-close of Cyberpunk2077.exe and REDprelauncher.exe...")
    os.system("taskkill /f /im Cyberpunk2077.exe >nul 2>&1")
    os.system("taskkill /f /im REDprelauncher.exe >nul 2>&1")
    return False


def game_key_press(key: str, hold_time: float = 0.15):
    """
    Simulates a human-like keypress with a configurable hold duration.

    The REDengine scans inputs once per frame and ignores key events that are
    pressed and released within the same tick. A non-zero hold_time ensures
    the engine registers the input on at least one frame.

    Args:
        key (str):        PyAutoGUI key name (e.g. 'down', 'enter', 'space').
        hold_time (float): Duration in seconds to hold the key before releasing.
    """
    pyautogui.keyDown(key)
    time.sleep(hold_time)
    pyautogui.keyUp(key)


def get_system_hardware() -> tuple:
    """
    Reads local hardware component names via native Windows CIM (WMI) instances.

    Replaces any dependency on third-party tools (e.g. HWiNFO, CPU-Z).
    On multi-GPU systems, only the first adapter returned by Win32_VideoController
    is used as the primary GPU identifier.

    Returns:
        tuple[str, str, str]: (cpu, gpu, ram) — falls back to 'Unknown X' strings on error.
    """
    try:
        cpu = subprocess.check_output(
            ['powershell', '-Command', '(Get-CimInstance Win32_Processor).Name']
        ).decode().strip()

        gpu_output = subprocess.check_output(
            ['powershell', '-Command', '(Get-CimInstance Win32_VideoController).Name']
        ).decode().strip()
        # On multi-GPU systems, take only the first line (primary adapter).
        gpu = gpu_output.split('\n')[0].strip()

        ram_bytes = subprocess.check_output(
            ['powershell', '-Command', '(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory']
        ).decode().strip()
        ram = f"{round(int(ram_bytes) / (1024 ** 3))} GB"

        return cpu, gpu, ram

    except Exception as hw_error:
        logging.warning(f"Hardware query failed: {hw_error}")
        return "Unknown CPU", "Unknown GPU", "Unknown RAM"


def wait_for_cyberpunk_json(base_path: str, start_time: float, timeout_sec: int = 150) -> str:
    """
    Polls the Cyberpunk benchmark results folder for a newly created summary.json.

    Cyberpunk 2077 creates a timestamped subfolder under the benchmarkResults
    directory after each run and writes a summary.json inside it. This function
    monitors that directory and returns the path to the first new JSON file
    created after start_time.

    Args:
        base_path (str):   Path to the benchmarkResults folder in Documents.
        start_time (float): Unix timestamp of when the benchmark run was started.
        timeout_sec (int): Maximum seconds to poll before giving up.

    Returns:
        str: Full path to the detected summary.json, or None if timed out.
    """
    logging.info(f"Monitoring '{base_path}' for new benchmark results. Timeout: {timeout_sec}s.")
    poll_start = time.time()

    while time.time() - poll_start < timeout_sec:
        if os.path.exists(base_path):
            subfolders = [f.path for f in os.scandir(base_path) if f.is_dir()]
            if subfolders:
                latest_folder = max(subfolders, key=os.path.getctime)
                json_file = os.path.join(latest_folder, 'summary.json')

                # Only accept a summary.json that was written during the current run
                # to avoid reading a result left over from a previous session.
                if os.path.exists(json_file) and os.path.getctime(json_file) > start_time:
                    logging.info(f"New summary.json detected in: {latest_folder}")
                    # Give the OS a moment to release the file handle before reading.
                    time.sleep(1)
                    return json_file

        # Poll every 3 seconds — sufficient resolution for a benchmark that takes ~60s.
        time.sleep(3)

    logging.error(f"TIMEOUT: No new Cyberpunk summary.json generated within {timeout_sec}s.")
    return None


def parse_cyberpunk_score(json_file: str):
    """
    Parses Avg FPS and Min FPS from a Cyberpunk 2077 benchmark summary.json file.

    The JSON structure uses a 'Data' key containing 'averageFps' and 'minFps' fields.
    Float values are rounded to one decimal place for cleaner display in the Sheet.

    Args:
        json_file (str): Full path to the summary.json file.

    Returns:
        tuple[str, str]: (avg_fps, min_fps) as strings — 'ERROR' if parsing fails.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            benchmark_data = data.get("Data", {})
            avg_fps = benchmark_data.get("averageFps", "ERROR")
            min_fps = benchmark_data.get("minFps", "ERROR")

            # Round float values to one decimal place for readability in the Google Sheet.
            if isinstance(avg_fps, (int, float)):
                avg_fps = round(avg_fps, 1)
            if isinstance(min_fps, (int, float)):
                min_fps = round(min_fps, 1)

            logging.info(f"Parsed JSON: Avg FPS = {avg_fps}, Min FPS = {min_fps}")
            return str(avg_fps), str(min_fps)

    except Exception as e:
        logging.error(f"Failed to parse Cyberpunk summary.json: {e}")
        return "ERROR", "ERROR"


def run_cyberpunk():
    """
    Main routine for running the Cyberpunk 2077 in-game benchmark (Ultra preset).

    Launch sequence:
      1. Start via Steam protocol → handle CDPR launcher → wait for main menu
      2. Force window focus to prevent input loss in fullscreen
      3. Skip intro sequences via Space
      4. Navigate Settings → Graphics via keyboard only (Down, Enter, 3, D)
      5. Verify Ultra preset is active via image matching; cycle presets if needed
      6. Trigger the built-in benchmark (B → Enter)
      7. Poll for summary.json output, then upload results

    All critical failures call abort_cyberpunk() to force-kill both the game and
    the CDPR launcher, ensuring a clean state for subsequent suite modules.

    Returns:
        bool: True if the routine completed successfully, False on any fatal error.
    """
    logging.info("--- Starting Cyberpunk 2077 Benchmark Routine ---")

    try:
        logging.info("Launching Cyberpunk 2077 via Steam protocol...")
        os.system('start steam://rungameid/1091500')
        time.sleep(10)

        # The CDPR launcher may or may not appear depending on the install configuration.
        # click_image here is intentionally non-fatal — we ignore it if it's not present.
        logging.info("Handling CDPR launcher (optional — ignored if not present)...")
        click_image('data/cp_continue_wo_acc.png', timeout=10)

        if not click_image('data/cp_play.png', timeout=60):
            return abort_cyberpunk("Play button in CDPR launcher not found after 60 seconds.")

        # The REDengine requires substantial time to load all assets after the launcher handoff.
        # 45 seconds is the minimum safe wait; increase on HDD-based systems if needed.
        logging.info("Waiting 45 seconds for REDengine to load the main menu...")
        time.sleep(45)

        # Clicking the center of the screen forces Windows focus onto the fullscreen window.
        # Without this, keyboard inputs can be silently dropped on some systems.
        logging.info("Forcing window focus to prevent keyboard input loss...")
        pyautogui.click(1920 / 2, 1080 / 2)
        time.sleep(1)

        logging.info("Executing intro skip sequence (Space x2)...")
        game_key_press('space', hold_time=0.2)
        time.sleep(3)
        game_key_press('space', hold_time=0.2)
        time.sleep(5)

        # ==========================================
        # CYBERPUNK UI NAVIGATION (keyboard-only)
        # ==========================================

        # Re-confirm focus before the navigation sequence.
        pyautogui.click(1920 / 2, 1080 / 2)
        time.sleep(1)

        # Park the cursor in the bottom-right corner to prevent accidental hover effects
        # from interfering with keyboard-driven menu navigation.
        logging.info("Hiding mouse cursor to prevent UI hover conflicts...")
        pyautogui.moveTo(1900, 1000, duration=0.5)
        time.sleep(1)

        logging.info("Navigating to 'Settings' via keyboard (Down → Enter)...")
        game_key_press('down', hold_time=0.15)
        time.sleep(0.4)
        game_key_press('enter', hold_time=0.2)
        time.sleep(3)

        # Press '3' three times to tab to the GRAPHICS settings page.
        logging.info("Navigating to GRAPHICS tab (3 x '3')...")
        for _ in range(3):
            game_key_press('3', hold_time=0.2)
            time.sleep(0.8)

        # Cycle through presets using 'D' until the Ultra preset reference image is matched.
        # Up to 10 presses are attempted before the routine is aborted.
        logging.info("Cycling graphics presets until 'Ultra' is confirmed on screen...")
        ultra_found = False
        for _ in range(10):
            try:
                if pyautogui.locateOnScreen('data/cp_ultra.png', confidence=0.9):
                    logging.info("Ultra preset successfully confirmed.")
                    ultra_found = True
                    break
            except pyautogui.ImageNotFoundException:
                pass

            game_key_press('d', hold_time=0.1)
            time.sleep(0.6)

        if not ultra_found:
            return abort_cyberpunk("Could not confirm the Ultra preset after 10 attempts.")

        # Trigger the built-in benchmark: 'B' opens the benchmark prompt, Enter confirms.
        logging.info("Initiating benchmark sequence (B → Enter)...")
        game_key_press('b', hold_time=0.2)
        time.sleep(1.5)
        game_key_press('enter', hold_time=0.2)

        # ==========================================
        # EVENT MONITORING & DATA EXTRACTION
        # ==========================================
        run_start_time = time.time()
        docs_path = os.path.join(
            os.environ['USERPROFILE'],
            'Documents', 'CD Projekt Red', 'Cyberpunk 2077', 'benchmarkResults'
        )

        # Event-driven wait: poll for summary.json instead of a fixed sleep.
        result_json = wait_for_cyberpunk_json(docs_path, run_start_time, timeout_sec=150)

        if result_json:
            avg_fps, min_fps = parse_cyberpunk_score(result_json)
            cpu, gpu, ram = get_system_hardware()
            pc_name = socket.gethostname()
            googlecloud.upload_results(pc_name, gpu, cpu, ram, "Cyberpunk 2077", avg_fps, min_fps, "N/A")
        else:
            logging.error("Benchmark did not produce a summary.json file. Upload aborted.")

        # Clean up both the game and the CDPR launcher to leave a fully clear process state.
        logging.info("Executing graceful cleanup of Cyberpunk processes...")
        os.system("taskkill /f /im Cyberpunk2077.exe >nul 2>&1")
        time.sleep(2)
        os.system("taskkill /f /im REDprelauncher.exe >nul 2>&1")

        logging.info(">>> Cyberpunk 2077 routine finished successfully. <<<")
        return True

    except Exception as e:
        return abort_cyberpunk(f"Fatal exception during Cyberpunk execution: {e}")
