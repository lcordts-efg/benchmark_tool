import pyautogui
import time
import os
import logging


def engine_safe_click(location):
    """
    Performs a hardware-level click to prevent 'ghost inputs' in game engines
    (such as Source 2 or REDengine) that frequently ignore standard clicks
    dispatched faster than a single frame (~10ms).

    The fix uses a manual mouseDown → hold → mouseUp sequence instead of
    pyautogui.click(), which dispatches both events in the same tick.
    """
    # Smooth mouse movement to the target — prevents anti-cheat and engine input
    # filters from ignoring cursor positions that teleport instantly.
    pyautogui.moveTo(location, duration=0.2)

    # Brief pause to allow the UI to register the hover state before the click.
    time.sleep(0.1)

    # Hold the mouse button down for 150ms before releasing.
    # This duration reliably triggers button press handlers in Source 2 and REDengine.
    pyautogui.mouseDown()
    time.sleep(0.15)
    pyautogui.mouseUp()


def click_image(image_path: str, confidence: float = 0.8, timeout: int = 20) -> bool:
    """
    Searches for a UI element on screen using template matching and clicks it.

    Uses an active polling loop rather than a single locateOnScreen call,
    so the function handles loading screens and delayed UI renders gracefully.

    Args:
        image_path (str): Relative path to the .png reference image (e.g. 'data/button.png').
        confidence (float): OpenCV match threshold (0.0–1.0). Lower values are more lenient.
        timeout (int): Maximum seconds to keep scanning before giving up.

    Returns:
        bool: True if the element was found and clicked, False if the timeout was reached.
    """
    logging.info(f"Scanning screen for UI element: '{image_path}' (Timeout: {timeout}s)...")
    start_time = time.time()

    # Fail-fast check: catch missing reference images immediately rather than
    # silently looping until timeout with no chance of success.
    if not os.path.exists(image_path):
        logging.error(f"CRITICAL: Reference image missing: '{image_path}'. Check deployment package!")
        return False

    # Polling loop — keeps scanning until the element appears or the timeout expires.
    while time.time() - start_time < timeout:
        try:
            # OpenCV-based template matching via PyAutoGUI.
            location = pyautogui.locateCenterOnScreen(image_path, confidence=confidence)

            if location is not None:
                logging.info(f"UI element '{image_path}' found at {location}. Initiating engine-safe click.")
                engine_safe_click(location)
                return True

        except pyautogui.ImageNotFoundException:
            # Expected during polling — the image is not on screen yet. Continue the loop.
            pass
        except Exception as e:
            # Log unexpected errors (e.g. OpenCV backend issues) instead of silently swallowing
            # them with a bare 'pass', which would make failures impossible to diagnose.
            logging.warning(f"Unexpected error during screen polling for '{image_path}': {e}")

        # 0.5s between scans is sufficient for menu navigation and keeps CPU load low.
        time.sleep(0.5)

    logging.error(f"TIMEOUT: UI element '{image_path}' not found after {timeout} seconds.")
    return False
