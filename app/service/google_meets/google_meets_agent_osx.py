from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import subprocess
import time
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.support.wait import WebDriverWait


# Function to set up Chrome with options
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--use-fake-ui-for-media-stream")  # Automatically grant mic/camera access
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def Glogin(email, password, driver):
    # Login Page
    driver.get(
        'https://accounts.google.com/ServiceLogin?hl=en&passive=true&continue=https://www.google.com/&ec=GAZAAQ')

    # input Gmail
    driver.find_element(By.ID, "identifierId").send_keys(email)
    driver.find_element(By.ID, "identifierNext").click()
    driver.implicitly_wait(10)

    # input Password
    driver.find_element(By.XPATH,
                        '//*[@id="password"]/div[1]/div/div[1]/input').send_keys(password)
    driver.implicitly_wait(10)
    driver.find_element(By.ID, "passwordNext").click()
    driver.implicitly_wait(10)

    # go to google home page
    driver.get('https://google.com/')
    driver.implicitly_wait(100)


# Function to join a Google Meet
def join_meet(meeting_url, email, password):
    driver = setup_driver()
    Glogin(email, password, driver)

    # driver.get("https://accounts.google.com/signin")
    #
    # # Login to Google Account
    # driver.find_element(By.ID, "identifierId").send_keys(email)
    # driver.find_element(By.ID, "identifierNext").click()
    # time.sleep(3)  # Wait for password field
    # driver.find_element(By.NAME, "password").send_keys(password)
    # driver.find_element(By.ID, "passwordNext").click()
    # time.sleep(8)  # Wait for Google account login process to complete

    # Join Google Meet
    driver.get(meeting_url)
    time.sleep(10)  # Wait for the page to load completely

    # Turn off mic and camera
    try:
        mic_button = driver.find_element(By.XPATH, "//div[@role='button' and @data-is-muted='false']")
        mic_button.click()
        time.sleep(1)
        cam_button = driver.find_element(By.XPATH, "//div[@role='button' and contains(@aria-label, 'Turn off camera')]")
        cam_button.click()
        time.sleep(1)
    except Exception as e:
        print("Mic/Camera buttons not found or already disabled:", e)

    wait = WebDriverWait(driver, 20)
    # Join the meeting
    join_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//button[span[contains(text(), "Join now")]]'))
    )
    join_button.click()
    time.sleep(5)

    print("Joined the Google Meet successfully!")

    # Keep the session open
    return driver


# Function to record audio on macOS
def record_audio(output_file, device_index):
    # Use ffmpeg's avfoundation for macOS
    command = [
        "ffmpeg",
        "-y",  # Overwrite output file
        "-f", "avfoundation",  # Use avfoundation for macOS
        "-i", f":{device_index}",  # Select device index
        "-t", "60",  # Record for 1 minute (adjust as needed)
        output_file
    ]
    subprocess.run(command)


if __name__ == "__main__":
    # Input Google Meet details
    meeting_url = 'https://meet.google.com/fed-iitv-sxq'
    email = 'kunal@chirpworks.ai'
    password = 'Eternity211!'

    # Specify the output file and device index
    output_file = "recording.mp3"
    device_index = 0  # Update this based on the device index for system audio (check from list_audio_devices)

    # Join the Meet
    driver = join_meet(meeting_url, email, password)

    # Start recording audio
    print("Recording audio...")
    record_audio(output_file, device_index)
    print("Recording saved to:", output_file)

    # Close the browser
    driver.quit()
