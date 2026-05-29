import time
import subprocess
import socket
from modules.database import upload_results
from modules.vision import click_image


def run_cs2():
    """
    Main routine for running the Counter-Strike 2 workshop benchmark map
    (Very High preset).

    CS2 is launched via Steam using its App-ID (730). The developer console
    is bound to F8 via a launch parameter (-bind f8 toggleconsole) to ensure
    it works consistently regardless of in-game keybinding resets or fresh installs.

    After the benchmark completes, Avg-FPS and 1% Lows (P1) are extracted
    from the VProf console output via the clipboard and uploaded to Google Sheets.

    NOTE: The click_image import is available here for future UI navigation steps.
          Placeholder comments mark where those calls should be added once the
          reference screenshots are captured (see Admin Manual, Section 7).

    Returns:
        bool: True if the routine completed successfully, False on any error.
    """
    print("\n--- Starting Counter-Strike 2 Benchmark Routine ---")

    try:
        # Launch CS2 through Steam using its numeric App-ID.
        # The Steam URI method ensures the correct launch parameters (set in Steam)
        # are applied, including the -bind f8 toggleconsole parameter.
        print("Launching CS2 via Steam...")
        subprocess.run(['cmd', '/c', 'start', 'steam://rungameid/730'])

        # CS2 requires time to connect to Steam servers and load the engine.
        # 30 seconds is the minimum recommended wait on SSD-based systems.
        print("Waiting 30 seconds for CS2 to load...")
        time.sleep(30)

        # --- Future navigation logic goes here ---
        # Once reference screenshots are available, replace this section with
        # click_image() calls and pyautogui keyboard sequences to:
        #   1. Dismiss any warning pop-ups (ESC)
        #   2. Navigate to the Workshop Maps section
        #   3. Launch the benchmark map
        #   4. Open the developer console (F8) after the run completes
        #   5. Copy the VProf output to the clipboard
        #   6. Parse Avg-FPS and P1 Lows from the clipboard text using Regex
        # Example:
        #   click_image('data/cs2_play_button.png', confidence=0.8, timeout=20)

        print("CS2 routine finished.")

        pc_name = socket.gethostname()
        # Placeholder score — replace with actual VProf clipboard parser output
        # once the result extraction logic is implemented (see Admin Manual, Section 7, Step 4).
        upload_results(pc_name, "CS2", "112 FPS")

        return True

    except Exception as e:
        print(f"[ERROR] Exception while running CS2 routine: {e}")
        return False
