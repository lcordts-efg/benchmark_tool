import pyautogui
import time
import os


def click_image(image_path, confidence=0.8, timeout=20):
    """
    Searches for a reference image on the screen and clicks its center if found.
    Retries every second until the timeout is reached.

    Args:
        image_path (str): Relative path to the .png reference image (e.g. 'data/button.png').
        confidence (float): Match threshold for PyAutoGUI (0.0 - 1.0). Lower values are more lenient.
        timeout (int): Maximum number of seconds to keep scanning before giving up.

    Returns:
        bool: True if the image was found and clicked, False if the timeout was reached.
    """
    print(f"  -> Scanning screen for '{image_path}' (Timeout: {timeout}s)...")
    start_time = time.time()

    # Verify that the reference image file actually exists on disk.
    # Failing early here prevents silent "image not found on screen" loops
    # caused by a missing or misnamed file in the data/ folder.
    if not os.path.exists(image_path):
        print(f"  [ERROR] The image file '{image_path}' does not exist in the directory!")
        return False

    while time.time() - start_time < timeout:
        try:
            # Attempt to locate the center coordinates of the reference image on the screen.
            # PyAutoGUI uses OpenCV under the hood; 'confidence' controls the match threshold.
            location = pyautogui.locateCenterOnScreen(image_path, confidence=confidence)

            if location is not None:
                print(f"  [SUCCESS] Image found at {location}. Initiating click...")
                # Move the mouse smoothly to the target location to mimic human-like behavior.
                # This also helps avoid issues where instant teleportation is ignored by game engines.
                pyautogui.moveTo(location, duration=0.2)
                # Brief pause after the move before clicking, giving the UI time to react
                # (e.g. hover states, button highlights).
                time.sleep(0.5)
                pyautogui.click()
                return True

        except pyautogui.ImageNotFoundException:
            # The image is not visible on screen yet — continue the loop and retry.
            pass
        except Exception as e:
            # Catch unexpected errors (e.g. OpenCV backend issues) without crashing the script.
            # Errors here are non-fatal; the loop will simply retry until the timeout.
            pass

        # Wait 1 second before the next screen scan to reduce CPU load.
        time.sleep(1)

    # The timeout was reached without a successful match.
    print(f"  [TIMEOUT] Could not locate '{image_path}' on screen after {timeout} seconds.")
    return False
