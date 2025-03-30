# import required modules
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


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


def turnOffMicCam(driver):
    # Disable camera and mic if not already disabled
    wait = WebDriverWait(driver, 20)

    # Ensure microphone is off
    try:
        mic_button = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//div[contains(@class, "U26fgb") and @aria-label="Turn off microphone"]'))
        )
        mic_button.click()
        print("Microphone turned off.")
    except Exception as e:
        print(f"Error turning off microphone: {e}")

        # Ensure camera is off
    try:
        camera_button = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//div[contains(@class, "U26fgb") and @aria-label="Turn off camera"]'))
        )
        camera_button.click()
        print("Camera turned off.")
    except Exception as e:
        print(f"Error turning off camera: {e}")


def joinNow(driver):
    # Join meet
    print(1)
    time.sleep(5)
    driver.implicitly_wait(2000)
    driver.find_element(By.CSS_SELECTOR,
                        'div.uArJ5e.UQuaGc.Y5sE8d.uyXBBb.xKiqt').click()
    print(1)


def AskToJoin(driver):
    # Ask to Join meet
    # time.sleep(5)
    # driver.implicitly_wait(2000)
    # driver.find_element(By.XPATH,
    #                     "//*[@id='yDmH0d']/c-wiz/div/div/div[4]/div[3]/div/div[2]/div/div/div[2]/div/div[2]/div/div[1]/div[1]/span").click()
    # Ask to join and join now buttons have same xpaths

    joined = False
    wait = WebDriverWait(driver, 20)
    # Join the meeting
    # try:
    #     join_button = wait.until(
    #         EC.element_to_be_clickable((By.XPATH, '//button[span[contains(text(), "Ask to join")]]'))
    #     )
    #     join_button.click()
    #     joined = True
    #     print("Successfully joined the meeting with mic and camera off.")
    # except Exception as e:
    #     print(f"Error clicking 'Join now' button: {e}")

    if not joined:
        try:
            join_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[span[contains(text(), "Join now")]]'))
            )
            join_button.click()
            joined = True
            print("Successfully joined the meeting with mic and camera off.")
        except Exception as e:
            print(f"Error clicking 'Join now' button: {e}")

    # Keep the browser open
    time.sleep(300)  # Keep the browser open for 5 minutes


def run():
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

    # go to google meet
    driver.get('https://meet.google.com/fed-iitv-sxq')
    driver.refresh()

    turnOffMicCam(driver)
    time.sleep(20)
    AskToJoin(driver)
    # joinNow(driver)


if __name__ == '__main__':
    run()
