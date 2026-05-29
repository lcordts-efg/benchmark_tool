import os
import time
import socket
import pyautogui
import re
import subprocess
import logging
# pyperclip removed — clipboard hacks replaced by log file parsing via -condebug.
from modules.vision import click_image
from modules import googlecloud


def wait_for_log_entry(log_file_path: str, search_string: str, timeout_sec: int = 180) -> bool:
    """
    Polls a local log file until a specific keyword appears in its content.

    Enables event-driven flow control: the script proceeds as soon as the engine
    writes the benchmark-complete marker to the log, rather than sleeping for a
    fixed duration that may be too short or too long on different hardware.

    The log file is opened read-only on each poll tick. PermissionErrors are silently
    ignored — they occur when the CS2 engine briefly holds an exclusive write lock
    and resolve automatically on the next tick.

    Args:
        log_file_path (str): Full path to the CS2 console.log file.
        search_string (str): Keyword or pattern to look for (e.g. '[VProf] FPS:').
        timeout_sec (int):   Maximum seconds to poll before giving up.

    Returns:
        bool: True if the keyword was found before the timeout, False otherwise.
    """
    logging.info(f"Monitoring '{log_file_path}' for keyword: '{search_string}'. Timeout: {timeout_sec}s")
    start_time = time.time()

    while (time.time() - start_time) < timeout_sec:
        if os.path.exists(log_file_path):
            try:
                # errors='ignore' prevents Unicode decode failures if the engine
                # writes non-UTF-8 bytes during loading.
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if search_string in content:
                        logging.info(f"Keyword '{search_string}' found in log. Benchmark complete.")
                        # Brief pause to allow VProf to finish writing all result lines
                        # before parse_cs2_log reads the file.
                        time.sleep(2)
                        return True
            except PermissionError:
                # Engine briefly holds an exclusive lock — retry on the next tick.
                pass

        # Poll every 3 seconds to balance responsiveness and I/O load.
        time.sleep(3)

    logging.error(f"TIMEOUT: Keyword '{search_string}' not found in log file within {timeout_sec}s.")
    return False


def parse_cs2_log(log_file_path: str):
    """
    Extracts Avg FPS and 1% Low (P1) values from the CS2 console.log file.

    The CS2 benchmark map writes VProf output to the console at the end of the run.
    The -condebug launch parameter (set in run_cs2) mirrors all console output to
    the console.log file, making it accessible without clipboard interaction.

    Expected log format (example):
        [VProf] FPS: Avg=245.3 ... P1=187.2 ...

    Args:
        log_file_path (str): Full path to the console.log file.

    Returns:
        tuple[str, str]: (avg_fps, p1_lows) as strings — 'ERROR' if parsing fails.
    """
    extracted_fps = "ERROR"
    extracted_p1 = "ERROR"

    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

            # Extract the average FPS value from the VProf output line.
            match_fps = re.search(r'\[VProf\] FPS: Avg=([0-9.]+)', content)
            if match_fps:
                extracted_fps = match_fps.group(1)

            # Extract the 1% Low (P1) value from the same VProf output line.
            match_p1 = re.search(r'P1=([0-9.]+)', content)
            if match_p1:
                extracted_p1 = match_p1.group(1)

        logging.info(f"Extracted from log — Avg FPS: {extracted_fps}, 1% Lows: {extracted_p1}")
        return extracted_fps, extracted_p1

    except Exception as e:
        logging.error(f"Failed to parse CS2 console.log: {e}")
        return "ERROR", "ERROR"


def run_cs2():
    """
    Main routine for running the Counter-Strike 2 workshop benchmark map (Very High preset).

    Key implementation details:
      - CS2 is launched directly via its .exe with -condebug, which mirrors all console
        output to a local console.log file. This replaces the clipboard-based approach
        and eliminates the need for in-game console interaction.
      - The old console.log is deleted before launch to ensure we only read results
        from the current session.
      - After launch, the routine navigates the UI via image recognition to set the
        Very High preset and start the benchmark map.
      - Benchmark completion is detected by polling console.log for the VProf output line.
      - CS2 is force-killed after upload to leave a clean state for subsequent runs.

    Returns:
        bool: True if the routine completed, False on any fatal error.
    """
    logging.info("--- Starting Counter-Strike 2 Benchmark Routine ---")

    cs2_base_path = r"C:\Games\Steam\steamapps\common\Counter-Strike Global Offensive"
    cs2_exe_path = os.path.join(cs2_base_path, r"game\bin\win64\cs2.exe")
    cs2_log_path = os.path.join(cs2_base_path, r"game\csgo\console.log")

    try:
        # Delete the previous console.log before launching CS2.
        # Without this, the parser might find a matching VProf line from a previous session
        # and return immediately without the benchmark actually running.
        if os.path.exists(cs2_log_path):
            try:
                os.remove(cs2_log_path)
                logging.info("Cleared old console.log file.")
            except Exception as e:
                logging.warning(f"Could not delete old console.log: {e}")

        # Launch CS2 with mandatory parameters:
        #   -novid          : Skips the intro video
        #   +con_enable 1   : Enables the developer console
        #   -condebug       : Mirrors all console output to game/csgo/console.log
        # Note: The console key (F8) is bound via Steam launch options, not here.
        logging.info("Launching CS2 with -condebug for automated log-based result extraction...")
        subprocess.Popen([cs2_exe_path, "-novid", "+con_enable", "1", "-condebug"])

        # 35 seconds is the minimum safe wait for CS2 to reach the main menu on SSD.
        # Increase this value if the benchmark map fails to load on slower storage.
        logging.info("Waiting 35 seconds for CS2 to initialize to main menu...")
        time.sleep(35)

        # Click the center of the screen to ensure CS2 has Windows input focus.
        pyautogui.click(1920 / 2, 1080 / 2)
        time.sleep(0.5)

        # Dismiss any pop-ups (e.g. MOTD, update notices) that could block navigation.
        logging.info("Clearing potential pop-ups (ESC x3)...")
        for _ in range(3):
            pyautogui.press('esc')
            time.sleep(1)

        # ==========================================
        # CS2 UI NAVIGATION
        # ==========================================
        logging.info("Navigating UI to configure graphics settings...")
        if not click_image('data/cs2_settings.png'):
            return False
        if not click_image('data/cs2_video.png'):
            return False
        if not click_image('data/cs2_adv_video.png'):
            return False

        # The graphics preset is a dropdown element offset from its label image.
        # We locate the label via image matching, then calculate the dropdown's
        # screen position by adding a fixed horizontal offset to the label's X coordinate.
        try:
            label_pos = pyautogui.locateCenterOnScreen('data/cs2_preset_label.png', confidence=0.8)
            if label_pos:
                # The dropdown control sits approximately 600px to the right of the label.
                click_x = label_pos.x + 600
                click_y = label_pos.y

                pyautogui.moveTo(click_x, click_y, duration=0.2)
                time.sleep(0.2)
                # Use mouseDown/mouseUp instead of click() to ensure the engine registers
                # the input (same ghost-input prevention as engine_safe_click in vision.py).
                pyautogui.mouseDown()
                time.sleep(0.15)
                pyautogui.mouseUp()
                time.sleep(1.5)  # Wait for the dropdown animation to complete.

                if not click_image('data/cs2_dropdown_veryhigh.png', confidence=0.9, timeout=5):
                    logging.error("Dropdown opened but 'Very High' preset option was not found.")
                    return False
            else:
                logging.error("Could not locate the 'Current Video Values Preset' label on screen.")
                return False

        except Exception as e:
            logging.error(f"Exception during dropdown handling: {e}")
            return False

        logging.info("Navigating to the Workshop benchmark map...")
        if not click_image('data/cs2_play.png'):
            return False
        if not click_image('data/cs2_wsmaps.png'):
            return False
        if not click_image('data/cs2_fps_bm.png'):
            return False
        if not click_image('data/cs2_go.png'):
            return False

        # ==========================================
        # BENCHMARK EXECUTION & RESULT MONITORING
        # ==========================================
        logging.info("Benchmark map started. Monitoring console.log for VProf completion marker...")

        # The benchmark map writes '[VProf] FPS: Avg=...' to the console when it finishes.
        # Polling for this keyword replaces a static 130-second sleep.
        if wait_for_log_entry(cs2_log_path, search_string="[VProf] FPS:", timeout_sec=200):

            fps, p1_lows = parse_cs2_log(cs2_log_path)

            # Query hardware specs for the upload row.
            pc_name = socket.gethostname()
            try:
                cpu = subprocess.check_output(
                    ['powershell', '-Command', '(Get-CimInstance Win32_Processor).Name']
                ).decode().strip()
                gpu_output = subprocess.check_output(
                    ['powershell', '-Command', '(Get-CimInstance Win32_VideoController).Name']
                ).decode().strip()
                # On multi-GPU systems, take only the primary adapter.
                gpu = gpu_output.split('\n')[0].strip()
                ram_bytes = subprocess.check_output(
                    ['powershell', '-Command', '(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory']
                ).decode().strip()
                ram = f"{round(int(ram_bytes) / (1024 ** 3))} GB"
            except Exception:
                cpu, gpu, ram = "Unknown CPU", "Unknown GPU", "Unknown RAM"

            googlecloud.upload_results(pc_name, gpu, cpu, ram, "Counter-Strike 2", fps, p1_lows, "N/A")

        else:
            logging.error("Benchmark did not complete or VProf output was missing from log.")

        # Force-kill CS2 to ensure a fully clean process state before the next module.
        logging.info("Forcefully terminating CS2 to ensure clean state...")
        os.system("taskkill /f /im cs2.exe >nul 2>&1")

        logging.info(">>> CS2 routine finished successfully. <<<")
        return True

    except Exception as e:
        logging.error(f"Fatal exception during CS2 execution: {e}")
        return False
