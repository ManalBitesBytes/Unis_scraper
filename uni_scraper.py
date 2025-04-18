from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException
import json
import os
import time

class UniScraper:

    def __init__(self):
        chrome_driver_path = r"C:\Users\ManalQatab\Downloads\chromedriver-win64\chromedriver.exe"

        # Initialize the ChromeOptions
        options = webdriver.ChromeOptions()
        options.add_experimental_option('detach', True)

        # Set up the service and driver
        service = Service(chrome_driver_path)

        # Initialize the Chrome WebDriver with options and service
        self.driver = webdriver.Chrome(options=options, service=service)

        # Set the page load timeout
        self.driver.set_page_load_timeout(300)  # Timeout in seconds

    def close(self):
        self.driver.quit()

    def scrape_data(self, url):
        self.driver.get(url)

        # Skip the agreement checkbox and button
        checkbox = WebDriverWait(self.driver, 50).until(
            EC.element_to_be_clickable((By.ID, "chkagree"))
        )
        checkbox.click()

        agree_button = WebDriverWait(self.driver, 50).until(
            EC.element_to_be_clickable((By.ID, "btnagree"))
        )
        agree_button.click()

        # Wait until the countries dropdown is present
        WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.ID, "Countries"))
        )

        # Fetch the dropdown *fresh* after waiting
        dropdown_element = self.driver.find_element(By.ID, "Countries")
        dropdown = Select(dropdown_element)

        # Iterate over all countries (skipping the first placeholder)
        start_after_country = "بريطانيا"
        skip = True

        for index, option in enumerate(dropdown.options):

            value = option.get_attribute("value")
            name = option.text.strip()

            if value == "" or name == "":
                continue

            if skip:
                if name == start_after_country:
                    skip = False
                continue

            if value == "" or name == "":
                continue

            print(f"\nSelecting country: {name} (value={value})")

            try:
                dropdown.select_by_value(value)
                search_btn = WebDriverWait(self.driver, 50).until(
                    EC.element_to_be_clickable((By.ID, "btnSearch"))
                )

                search_btn.click()
                time.sleep(2)
                # Check if 'no-result' is visible
                try:
                    no_result_element = self.driver.find_element(By.CSS_SELECTOR, "div.no-result")
                    is_visible = self.driver.execute_script("return arguments[0].offsetParent !== null;",
                                                            no_result_element)
                    if is_visible:
                        print(f"⚠️ No universities found for {name}. Skipping...\n")
                        continue
                except:
                    pass

                # Pagination and scraping for universities
                start_after_uni = "McMaster University"  # <-- Change to your university name
                skip_uni = True

                page = 1
                while True:
                    print(f"📄 Page {page}")

                    try:
                        WebDriverWait(self.driver, 50).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "table.su-table tbody tr"))
                        )
                    except TimeoutException:
                        print(f"⚠️ Table did not load for {name}, page {page}.")
                        break

                    row_index = 0
                    while True:
                        try:
                            WebDriverWait(self.driver, 50).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "table.su-table"))
                            )

                            rows = self.driver.find_elements(By.CSS_SELECTOR, "table.su-table tbody tr")

                            if row_index >= len(rows):
                                break

                            row = rows[row_index]
                            uni_link = WebDriverWait(row, 50).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, "tr td:nth-child(1) a"))
                            )
                            uni_name = uni_link.text
                            print(f"🎯 Visiting: {uni_name}")

                            if skip_uni and uni_name != start_after_uni:
                                print(f"⏭️ Skipping university: {uni_name}")
                                row_index += 1
                                continue
                            elif skip_uni and uni_name == start_after_uni:
                                print(f"✅ Found starting university: {uni_name}. Beginning scrape.")
                                skip_uni = False

                            self.driver.execute_script("arguments[0].click();", uni_link)
                            page_url = self.driver.current_url

                            # Wait for the detail fields to load
                            WebDriverWait(self.driver, 50).until(
                                EC.presence_of_element_located((By.CLASS_NAME, "CountryGray"))
                            )

                            # --- Extract fields ---
                            try:
                                country = self.driver.find_element(By.CLASS_NAME, "CountryGray").find_element(
                                    By.XPATH, "following-sibling::span"
                                ).text.strip()
                            except:
                                country = None

                            state = None
                            city = None

                            # Get all city/state label blocks
                            location_blocks = self.driver.find_elements(By.CSS_SELECTOR,
                                                                        "div.form_group_title_right.col-xs-12.col-sm-6")

                            for block in location_blocks:
                                try:
                                    label = block.find_element(By.TAG_NAME, "label").text.strip()
                                    value = block.find_element(By.TAG_NAME, "span").text.strip()

                                    if label == "الولاية :":
                                        state = value
                                    elif label == "المدينة :":
                                        city = value
                                except:
                                    continue

                            try:
                                # Locate the label with the website field title
                                website_label = self.driver.find_element(By.XPATH,
                                                                         "//label[contains(text(), 'الموقع الإلكتروني')]")

                                # Go up to its parent, then find the anchor <a> tag inside
                                website_parent = website_label.find_element(By.XPATH,
                                                                            "./ancestor::div[contains(@class, 'form_group_title_right')]")

                                link = website_parent.find_element(By.TAG_NAME, "a")
                                website = link.get_attribute("href")
                            except:
                                website = None

                            # Notes list
                            notes = []
                            try:
                                note_lists = self.driver.find_elements(By.CSS_SELECTOR, "#page-top > div:nth-child(4)")
                                for ul in note_lists:
                                    items = ul.find_elements(By.TAG_NAME, "li")
                                    for li in items:
                                        notes.append(li.text.strip())
                            except:
                                notes = []

                            STATUS_MAP = {
                                "100": "متوفر",
                                "101": "متوقف للتكدس",
                                "102": "مغلق"
                            }

                            study_levels = {
                                "دبلوم": {},
                                "بكالوريوس": {},
                                "دبلوم عالي": {},
                                "ماجستير": {},
                                "دكتوراه": {}
                            }

                            try:
                                table = self.driver.find_element(By.ID, "table-major")
                                rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # skip header

                                for row in rows:
                                    cells = row.find_elements(By.TAG_NAME, "td")
                                    if not cells:
                                        continue

                                    # First column is specialization name
                                    specialization = cells[0].text.strip()

                                    for idx, level in enumerate(study_levels.keys()):
                                        try:
                                            img = cells[idx + 1].find_element(By.TAG_NAME, "img")
                                            src = img.get_attribute("src")
                                            status_code = src.split("/")[-1].split(".")[0]  # e.g., 100 from .../100.png
                                            status = STATUS_MAP.get(status_code, "غير معروف")
                                            study_levels[level][specialization] = status
                                        except:
                                            # No image = Not offered
                                            continue

                            except Exception as e:
                                print(f"❌ Failed to parse study levels: {e}")

                            # You can now print/save this data
                            print(f"📌 Country: {country}")
                            print(f"🏙️ City: {city}")
                            print(f"🌐 Website: {website}")
                            print("📝 Notes:")
                            if notes:
                                for note in notes:
                                    print(" -", note)
                            else:
                                print(" - No notes.")

                            print("📚 Study Levels:")
                            for level, specs in study_levels.items():
                                print(f"  🔹 {level}:")
                                for spec, status in specs.items():
                                    print(f"     - {spec}: {status}")

                            # Save to a JSON file
                            # Create a lock file to prevent concurrent access
                            lock_file = "universities_data_3.json.lock"

                            # Wait for lock to be released if another process has it
                            while os.path.exists(lock_file):
                                time.sleep(0.1)

                            try:
                                # Create lock file
                                with open(lock_file, 'w') as f:
                                    f.write("locked")

                                # Load existing data
                                all_data = {}
                                if os.path.exists("universities_data_3.json"):
                                    try:
                                        with open("universities_data_3.json", "r", encoding="utf-8") as f:
                                            all_data = json.load(f)
                                    except json.JSONDecodeError:
                                        # If file is corrupted, start fresh
                                        print("⚠️ JSON file corrupted, starting fresh.")
                                        all_data = {"Data": {}}

                                Data = all_data.get("Data", {})

                                # Add new data
                                Data[uni_name] = {
                                    "country": country,
                                    "state": state if country == "أمريكا" else None,
                                    "city": city,
                                    "website": website,
                                    "page_url": page_url,
                                    "notes": notes,
                                    "study_levels": study_levels
                                }

                                # Write back to file with proper formatting
                                with open("universities_data_3.json", "w", encoding="utf-8") as f:
                                    json.dump({"Data": Data}, f, ensure_ascii=False, indent=4)

                            finally:
                                # Release lock
                                if os.path.exists(lock_file):
                                    os.remove(lock_file)






                            self.driver.back()

                            time.sleep(1)  # Optional, let JS settle

                            row_index += 1

                        except Exception as e:
                            print(f"❌ Error visiting university: {str(e)}")

                            time.sleep(2)



                            row_index += 1
                            continue

                    # Go to next page
                    try:
                        next_li = self.driver.find_element(By.CSS_SELECTOR, "#pgcon li.active + li")
                        if 'disabled' in next_li.get_attribute('class'):
                            print("⛔ Reached last page.")
                            break
                        next_page_link = WebDriverWait(self.driver, 10).until(lambda d: next_li.find_element(By.TAG_NAME, "a"))
                        self.driver.execute_script("arguments[0].click();", next_page_link)
                        time.sleep(3)
                        page += 1
                    except:
                        print("⛔ No more pages.")
                        break

            except Exception as e:
                print(f"🔥 Fatal error for country {name}: {e}")
                continue





scraper = UniScraper()
scraper.scrape_data('https://ru.moe.gov.sa/Search')
scraper.close()