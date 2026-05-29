import os
import sys
import time
import logging
import argparse

# Module imports
from modules.benchmark_3dmark import run_3dmark
from modules.benchmark_cyberpunk import run_cyberpunk
from modules.benchmark_cs2 import run_cs2

# 1. Ensure the log directory exists before configuring the file handler.
#    exist_ok=True means the call is a no-op if the folder is already present.
LOG_DIR = r"C:\IT\Tools\Benchmark Tool"
os.makedirs(LOG_DIR, exist_ok=True)

# 2. Configure structured logging to both a persistent log file and stdout.
#    The log file (suite_execution.log) is written to the tool directory defined above.
#    This gives technicians a full audit trail after every run.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "suite_execution.log")),
        logging.StreamHandler(sys.stdout)
    ]
)


def show_menu():
    """Prints the CLI selection menu to the console."""
    print("\n" + "=" * 50)
    print(" EFG HIGH-END PC BENCHMARK AUTOMATION SUITE")
    print("=" * 50)
    print("[1] Run Full Suite (3DMark, Cyberpunk 2077, CS2)")
    print("[2] Run 3DMark only")
    print("[3] Run Cyberpunk 2077 only")
    print("[4] Run Counter-Strike 2 only")
    print("[0] Exit program")
    print("=" * 50)


def execute_full_suite():
    """
    Runs all three benchmark modules sequentially.

    Each module is wrapped in its own try/except block so that a crash or failure
    in one benchmark does not prevent the remaining ones from running.
    The full run order is: 3DMark → Cyberpunk 2077 → CS2.

    A complete Full Suite run takes approximately 15–20 minutes.
    """
    logging.info("Initiating Full Suite execution...")

    try:
        logging.info("Starting 3DMark Phase...")
        run_3dmark()
    except Exception as e:
        logging.error(f"CRITICAL: 3DMark module failed: {e}")

    try:
        logging.info("Starting Cyberpunk 2077 Phase...")
        run_cyberpunk()
    except Exception as e:
        logging.error(f"CRITICAL: Cyberpunk 2077 module failed: {e}")

    try:
        logging.info("Starting CS2 Phase...")
        run_cs2()
    except Exception as e:
        logging.error(f"CRITICAL: CS2 module failed: {e}")

    logging.info("Full Suite execution completed.")


def main():
    """
    Main entry point — handles both unattended (--auto) and interactive (CLI) execution modes.

    --auto mode: Bypasses the CLI menu entirely and runs the Full Suite immediately.
                 Intended for use with Windows Task Scheduler for zero-touch deployment.

    Interactive mode: Displays the CLI menu for a technician to select individual benchmarks.

    IMPORTANT: Once a benchmark is running, do not touch the mouse or keyboard.
    The script requires physical control of the cursor. See the User Guide for
    the full list of rules during execution.

    To add a new benchmark to the suite, see Admin Manual Section 7
    ('Adding a New Benchmark Module').
    """
    # argparse enables launching this script non-interactively via Windows Task Scheduler.
    # Pass --auto as a command-line argument to skip the CLI menu entirely.
    parser = argparse.ArgumentParser(description="Automated benchmark suite for high-end event PCs")
    parser.add_argument(
        '--auto',
        action='store_true',
        help="Launches the Full Suite in unattended mode, bypassing the CLI menu"
    )
    args = parser.parse_args()

    # If --auto is set (e.g. triggered by Windows Task Scheduler), skip the menu
    # and run the Full Suite immediately, then exit cleanly.
    if args.auto:
        logging.info("AUTO-MODE DETECTED: Bypassing CLI menu for unattended execution.")
        execute_full_suite()
        sys.exit(0)

    # Standard interactive mode for an on-site technician.
    while True:
        show_menu()
        choice = input("Please select an option (0-4): ")

        if choice == '1':
            execute_full_suite()
            time.sleep(2)

        elif choice == '2':
            logging.info("Initializing 3DMark Standalone...")
            try:
                run_3dmark()
            except Exception as e:
                logging.error(f"3DMark failed: {e}")
            time.sleep(2)

        elif choice == '3':
            logging.info("Initializing Cyberpunk 2077 Standalone...")
            try:
                run_cyberpunk()
            except Exception as e:
                logging.error(f"Cyberpunk failed: {e}")
            time.sleep(2)

        elif choice == '4':
            logging.info("Initializing CS2 Standalone...")
            try:
                run_cs2()
            except Exception as e:
                logging.error(f"CS2 failed: {e}")
            time.sleep(2)

        elif choice == '0':
            logging.info("Exiting program via user input. Goodbye!")
            sys.exit(0)

        else:
            logging.warning("Invalid menu input detected.")
            print("\nInvalid input! Please select a number between 0 and 4.")
            time.sleep(1)


if __name__ == "__main__":
    main()
