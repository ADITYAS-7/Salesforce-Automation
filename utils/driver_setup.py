import logging
import os
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOCAL_GECKODRIVER = os.path.join(_PROJECT_ROOT, "drivers", "geckodriver.exe")


def create_driver(headless: bool = False) -> webdriver.Firefox:
    options = Options()
    options.set_preference("dom.webnotifications.enabled", False)
    options.set_preference("dom.push.enabled", False)
    options.set_preference("dom.disable_open_during_load", False)

    if headless:
        options.add_argument("-headless")

    options.binary_location = os.path.join(os.environ["LOCALAPPDATA"], "Mozilla Firefox", "firefox.exe")

    # Use the existing Firefox profile so Salesforce session is already logged in.
    # Firefox must be fully closed before running.
    profile_dir = os.path.join(
        os.environ["APPDATA"], "Mozilla", "Firefox", "Profiles", "3bunlml9.default-release"
    )
    options.add_argument("-profile")
    options.add_argument(profile_dir)

    service = Service(_LOCAL_GECKODRIVER)
    driver = webdriver.Firefox(service=service, options=options)
    driver.maximize_window()
    logger.info("Firefox WebDriver initialised (headless=%s)", headless)
    return driver
