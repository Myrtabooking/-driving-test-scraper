from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import time
import json
import logging
from datetime import datetime
import requests
import base64
from selenium.webdriver.chrome.service import Service
import os

logging.basicConfig(
    level=logging.INFO,                          # log to console
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('driving_test_scraper.log'),
        logging.StreamHandler()                  # <-- Console output
    ]
)

# GitHub configuration
GITHUB_TOKEN = os.environ["PAT"]  
GITHUB_API_URL = "https://api.github.com/repos/Myrtabooking/driving-test-times/contents/docs/data.json"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

def update_github_file(data):
    """Update the data.json file in GitHub repository"""
    try:
        # Convert data to JSON string
        json_data = json.dumps(data, indent=4)
        
        # Encode content in base64
        content = base64.b64encode(json_data.encode()).decode()
        
        # Try to get the current file first
        try:
            response = requests.get(GITHUB_API_URL, headers=HEADERS)
            response.raise_for_status()
            current_sha = response.json()["sha"]
            logging.info("Successfully got current file SHA")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                current_sha = None
                logging.info("File doesn't exist yet, will create new")
            else:
                logging.error(f"Error getting current file: {e.response.content}")
                raise
        
        # Prepare the update payload
        payload = {
            "message": f"Update test times - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": content,
        }
        
        if current_sha:
            payload["sha"] = current_sha
        
        # Update the file
        logging.info("Attempting to update file...")
        response = requests.put(GITHUB_API_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        
        logging.info("Successfully updated GitHub repository")
        return True
        
    except Exception as e:
        logging.error(f"Error updating GitHub repository: {e}")
        if hasattr(e, 'response'):
            logging.error(f"Response content: {e.response.content}")
        return False

def scrape_test_times():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/103.0.5060.114 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options) 
    all_locations_data = {}
    
    try:
        driver.get("https://www.myrta.com/wps/portal/extvp/myrta/login/")
        wait = WebDriverWait(driver, 10)

        license_number = wait.until(EC.visibility_of_element_located((By.ID, "widget_cardNumber")))
        license_number.send_keys("24148176")

        password = wait.until(EC.visibility_of_element_located((By.ID, "widget_password")))
        password.send_keys("Secret1234")
        
        time.sleep(1)

        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@id='nextButton_label']")))
        login_button.click()

        book_test_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@class='general-btn' and contains(@href, 'tbsloginredirect')]")))
        book_test_button.click()

        time.sleep(1)
        
        car_radio_button = wait.until(EC.element_to_be_clickable((By.ID, "CAR")))
        driver.execute_script("arguments[0].click();", car_radio_button)

        dt_radio_button = wait.until(EC.element_to_be_clickable((By.ID, "c1tt3")))
        driver.execute_script("arguments[0].click();", dt_radio_button)

        time.sleep(1)

        next_button = wait.until(EC.element_to_be_clickable((By.ID, "nextButton")))
        next_button.click()

        time.sleep(1)
        
        terms_checkbox = wait.until(EC.element_to_be_clickable((By.ID, "checkTerms")))
        terms_checkbox.click()
        
        time.sleep(1)

        next_button = wait.until(EC.element_to_be_clickable((By.ID, "nextButton")))
        next_button.click()

        time.sleep(1)
        
        location_radio_button = driver.find_element(By.ID, "rms_batLocLocSel")
        if not location_radio_button.is_selected():
            location_radio_button.click()

        time.sleep(1)

        def extract_available_times():
            try:
                week_starting = driver.find_element(By.XPATH, "//span[@class='title']").text
                logging.info(f"Week starting: {week_starting}")

                days = driver.find_elements(By.XPATH, "//span[@class='d']")
                day_dates = [day.text for day in days]

                times_by_day = {day: [] for day in day_dates}

                for day_index, day in enumerate(day_dates):
                    available_times = driver.find_elements(By.XPATH, f"//td[contains(@class, 'rms_{day[:3].lower()}')]//a[contains(@class, 'available')]")
                    for time_slot in available_times:
                        times_by_day[day].append(time_slot.text)

                for day, times in times_by_day.items():
                    if times:
                        location_data[day] = times
                        logging.info(f"{day}: {', '.join(times)}")
            except Exception as e:
                logging.error(f"Error extracting times: {e}")

        while True:
            location_dropdown = wait.until(EC.presence_of_element_located((By.ID, "rms_batLocationSelect2")))
            select = Select(location_dropdown)
            location_options = select.options

            location_names = [
                option.text.strip() 
                for option in location_options 
                if option.text.strip().lower() != "choose..." and option.is_enabled()
            ]

            logging.info(f"Found {len(location_names)} locations to process.")
            logging.info("Locations: " + ", ".join(location_names))

            for location_name in location_names:
                try:
                    location_dropdown = wait.until(EC.presence_of_element_located((By.ID, "rms_batLocationSelect2")))
                    select = Select(location_dropdown)
                    select.select_by_visible_text(location_name)
                    
                    logging.info(f"Selected Location: {location_name}")

                    next_button = wait.until(EC.element_to_be_clickable((By.ID, "nextButton")))
                    next_button.click()

                    time.sleep(1.5)

                    no_timeslot_weeks = 0
                    location_data = {}

                    while True:
                        extract_available_times()

                        try:
                            alert_dialog = driver.find_element(By.XPATH, "//div[@role='alertdialog']")
                            alert_text = alert_dialog.text
                            if "There are no timeslots available for this week." in alert_text or "There are no timeslots available at this location." in alert_text:
                                no_timeslot_weeks += 1
                                logging.info(f"No timeslots for week starting. Consecutive weeks with no slots: {no_timeslot_weeks}")
                                if no_timeslot_weeks >= 1:
                                    logging.info("Stopping search for this location after two consecutive weeks with no slots.")
                                    break
                        except:
                            no_timeslot_weeks = 0

                        try:
                            next_week_button = wait.until(EC.element_to_be_clickable((By.ID, "nextWeekButton")))
                            next_week_button.click()
                            time.sleep(1)
                        except:
                            logging.info("No more weeks available or 'Next week' button not found.")
                            break

                    all_locations_data[location_name] = location_data

                    try:
                        back_to_locations_link = wait.until(EC.element_to_be_clickable((By.ID, "anotherLocationLink")))
                        back_to_locations_link.click()
                        time.sleep(4)
                    except:
                        logging.error("Failed to navigate back to location selection. Exiting.")
                        break

                except Exception as e:
                    logging.error(f"An error occurred while processing location '{location_name}': {e}")
                    continue

            break

        return all_locations_data

    except Exception as e:
        logging.error(f"Error in main scraping function: {e}")
        return None

    finally:
        driver.quit()

def main_job():
    """Main function that runs the scraping and GitHub update"""
    try:
        logging.info("Starting scraping job")
        data = scrape_test_times()
        
        if data and any(data.values()):
            # Save locally
            with open('data.json', 'w') as f:
                json.dump(data, f, indent=4)
            logging.info("Data saved locally")
            
            # Update GitHub
            if update_github_file(data):
                logging.info("Job completed successfully")
            else:
                logging.error("Failed to update GitHub")
        else:
            logging.error("Scraping failed")
            
    except Exception as e:
        logging.error(f"Error in main job: {e}")

if __name__ == "__main__":
    main_job()
