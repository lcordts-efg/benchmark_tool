import sys
import time

# Import all benchmark module entry points.
# Each module is responsible for launching, navigating, and uploading results
# for its respective benchmark application.
from modules.benchmark_3dmark import run_3dmark
from modules.benchmark_cyberpunk import run_cyberpunk
from modules.benchmark_cs2 import run_cs2


def show_menu():
    """Prints the CLI selection menu to the console."""
    print("\n" + "=" * 40)
    print(" HIGH-END PC BENCHMARK AUTOMATION")
    print("=" * 40)
    print("[1] Run Full Suite (3DMark, Cyberpunk 2077, CS2)")
    print("[2] Run 3DMark only")
    print("[3] Run Cyberpunk 2077 only")
    print("[4] Run Counter-Strike 2 only")
    print("[0] Exit program")
    print("=" * 40)


def main():
    """
    Main entry point — displays the CLI menu and dispatches benchmark runs
    based on user input.

    The Full Suite (option 1) runs all three benchmarks sequentially in the
    following order: 3DMark → Cyberpunk 2077 → CS2.
    A complete Full Suite run takes approximately 15–20 minutes.

    IMPORTANT: Once a benchmark is running, do not touch the mouse or keyboard.
    The script requires physical control of the cursor. See the User Guide for
    the full list of rules during execution.

    To add a new benchmark to the suite, see Admin Manual Section 7
    ('Adding a New Benchmark Module').
    """
    while True:
        show_menu()
        choice = input("Please select an option (0-4): ")

        if choice == '1':
            print("\nStarting Full Suite...")
            run_3dmark()
            run_cyberpunk()
            run_cs2()
            print("\nFull Suite completed successfully!")
            # Brief pause before redisplaying the menu so the user can read the output.
            time.sleep(2)

        elif choice == '2':
            print("\nInitializing 3DMark...")
            run_3dmark()
            time.sleep(2)

        elif choice == '3':
            print("\nInitializing Cyberpunk 2077...")
            run_cyberpunk()
            time.sleep(2)

        elif choice == '4':
            print("\nInitializing CS2...")
            run_cs2()
            time.sleep(2)

        elif choice == '0':
            print("\nExiting program. Goodbye!")
            sys.exit()

        else:
            print("\nInvalid input! Please select a number between 0 and 4.")
            time.sleep(1)


if __name__ == "__main__":
    main()
