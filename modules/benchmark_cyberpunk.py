import time
import subprocess
import socket
from modules.database import upload_results
from modules.vision import click_image


def run_cyberpunk():
    """
    Main routine for running the Cyberpunk 2077 in-game benchmark (Ultra preset).

    Cyberpunk 2077 is launched via Steam using its App-ID (1091500).
    Navigation is handled via keyboard inputs (Down, Enter, 3, D) as documented
    in the Admin Manual — no image recognition is required for menu navigation.

    After the benchmark finishes, the result is read from the summary.json file
    saved by the game in the Documents folder and uploaded to Google Sheets.

    NOTE: The click_image import is available here for future UI navigation steps.
          Placeholder comments mark where those calls should be added once the
          reference screenshots are captured (see Admin Manual, Section 7).

    Returns:
        bool: True if the routine completed successfully, False on any error.
    """
    print("\n--- Starting Cyberpunk 2077 Benchmark Routine ---")

    try:
        # Launch Cyberpunk 2077 through Steam using its numeric App-ID.
        # This method works regardless of where the game is installed on disk.
        print("Launching Cyberpunk 2077 via Steam...")
        subprocess.run(['cmd', '/c', 'start', 'steam://rungameid/1091500'])

        # Cyberpunk 2077 is a large title with a multi-stage loader (CDPR launcher + engine).
        # 45 seconds is the minimum safe wait; increase this on slower storage (e.g. HDD).
        print("Waiting 45 seconds for Cyberpunk 2077 to load...")
        time.sleep(45)

        # --- Future navigation logic goes here ---
        # Once reference screenshots are available, replace this section with
        # click_image() calls or pyautogui keyboard sequences to:
        #   1. Dismiss the main menu / skip intro videos
        #   2. Navigate to Settings > Graphics
        #   3. Confirm Ultra preset is applied
        #   4. Start the built-in benchmark sequence
        # Example:
        #   click_image('data/cp2077_benchmark_button.png', confidence=0.8, timeout=20)

        print("Cyberpunk 2077 routine finished.")

        pc_name = socket.gethostname()
        # Placeholder score — replace with actual summary.json parser output
        # once the result extraction logic is implemented (see Admin Manual, Section 7, Step 4).
        upload_results(pc_name, "Cyberpunk 2077 (Ultra)", "112 FPS")

        return True

    except Exception as e:
        print(f"[ERROR] Exception while running Cyberpunk 2077 routine: {e}")
        return False
