import logging
import sys
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import config
from utils.driver_setup import create_driver
from utils.excel_reader import read_party_data
from utils.salesforce_automation import (
    run_party_creation,
    navigate_to_parties,
    close_wizard_tab,
    take_screenshot,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def main() -> None:
    logger.info("Loading party data from: %s", config.EXCEL_FILE)
    records = read_party_data(config.EXCEL_FILE, config.EXCEL_SHEET)
    logger.info("%d record(s) to process", len(records))

    logger.info("Launching browser")
    driver = create_driver(headless=config.HEADLESS)
    wait = WebDriverWait(driver, config.BROWSER_TIMEOUT)

    try:
        logger.info("Navigating to Salesforce")
        driver.get(config.SF_BASE_URL)

        # SSO login if redirected to login page
        try:
            sso_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((
                By.CSS_SELECTOR, 'button[onclick*="Te Whatu Ora Single Sign On"]',
            )))
            logger.info("Login page detected – clicking SSO")
            sso_btn.click()
            # Wait for Salesforce shell to load after SSO redirect
            WebDriverWait(driver, 120).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[title="Parties"]'))
            )
            logger.info("SSO complete – pausing 8s for shell to settle")
            time.sleep(8)
        except Exception:
            logger.info("Already authenticated")

        # Always navigate explicitly to the Parties list before starting
        logger.info("Navigating to Parties list")
        navigate_to_parties(driver, wait)
        logger.info("Parties page ready")

        for idx, party in enumerate(records, 1):
            name = party.get("LE_NAME", f"row {idx}")
            logger.info("─── Record %d / %d: %s", idx, len(records), name)
            try:
                run_party_creation(driver, wait, party, config.SCREENSHOTS_DIR)
            except Exception as exc:
                logger.error("FAILED record %d (%s): %s", idx, name, exc)
                take_screenshot(driver, config.SCREENSHOTS_DIR, f"error_{idx}_{name}")
                close_wizard_tab(driver, wait)
            finally:
                # Return to Parties after every record (success or failure).
                # navigate_to_parties clicks the nav link then refreshes the page,
                # flushing any residual wizard DOM before the next record starts.
                try:
                    navigate_to_parties(driver, wait)
                except Exception:
                    logger.error("Could not return to Parties page – stopping")
                    raise

        logger.info("All %d record(s) processed", len(records))

    finally:
        driver.quit()
        logger.info("Browser closed")


if __name__ == "__main__":
    main()
