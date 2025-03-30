from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


def Glogin(mail_address, password, driver):
    # Login Page
    driver.get(
        'https://accounts.google.com/ServiceLogin?hl=en&passive=true&continue=https://www.google.com/&ec=GAZAAQ')

    # input Gmail
    driver.find_element(By.ID, "identifierId").send_keys(mail_address)
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

def run():
    # Configuration

    google_email = 'kunal@chirpworks.ai'
    google_password = 'Eternity211!'
    meet_link = "https://meet.google.com/fed-iitv-sxq?disableJoin=false"

    # Set up WebDriver
    opt = Options()
    opt.add_argument('--disable-blink-features=AutomationControlled')
    opt.add_argument('--start-maximized')
    opt.add_experimental_option("prefs", {
        "profile.default_content_setting_values.media_stream_mic": 1,
        "profile.default_content_setting_values.media_stream_camera": 1,
        "profile.default_content_setting_values.geolocation": 0,
        "profile.default_content_setting_values.notifications": 1
    })
    driver = webdriver.Chrome(options=opt)
    # driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, 20)

    try:
        # Navigate to Google Meet
        driver.get(meet_link)

        # Wait for the Google Meet page to load
        time.sleep(5)

        # Disable camera and mic if not already disabled
        try:
            mic_button = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="button" and @data-tooltip="Turn off microphone (Cmd + D)"]')))
            if "off" not in mic_button.get_attribute("data-tooltip").lower():
                mic_button.click()
                print("Microphone turned off.")
        except:
            print("Microphone already off or not found.")

        try:
            camera_button = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="button" and @data-tooltip="Turn off camera (Ctrl + E)"]')))
            if "off" not in camera_button.get_attribute("data-tooltip").lower():
                camera_button.click()
                print("Camera turned off.")
        except:
            print("Camera already off or not found.")

        # Join the meeting
        join_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@data-tooltip, "Join now")]')))
        join_button.click()

        print("Successfully joined the meeting with mic and camera off.")

        # Keep the browser open
        time.sleep(300)  # Keep the browser open for 5 minutes

    finally:
        driver.quit()


if __name__ == "__main__":
    # assign email id and password
    mail_address = 'kunal@chirpworks.ai'
    password = 'Eternity211!'

    # create chrome instance
    opt = Options()
    opt.add_argument('--disable-blink-features=AutomationControlled')
    opt.add_argument('--start-maximized')
    opt.add_experimental_option("prefs", {
        "profile.default_content_setting_values.media_stream_mic": 1,
        "profile.default_content_setting_values.media_stream_camera": 1,
        "profile.default_content_setting_values.geolocation": 0,
        "profile.default_content_setting_values.notifications": 1
    })
    driver = webdriver.Chrome(options=opt)

    # login to Google account
    Glogin(mail_address, password, driver)
    run()
