import os
from dotenv import load_dotenv

load_dotenv()

# --- Salesforce ---
SF_BASE_URL = "https://sectorops--act.sandbox.lightning.force.com"
SF_PARTIES_URL = f"{SF_BASE_URL}/lightning/o/Account/list?filterName=__Recent"
SF_USERNAME = os.getenv("SF_USERNAME", "")
SF_PASSWORD = os.getenv("SF_PASSWORD", "")

# --- Browser ---
HEADLESS = False          # Set True to run without a visible browser window
BROWSER_TIMEOUT = 30      # Max seconds to wait for elements
MFA_WAIT_SECONDS = 60     # Seconds to pause for manual MFA completion (set 0 to skip)

# --- Excel ---
EXCEL_FILE = "data/party_data.xlsx"
EXCEL_SHEET = "Sheet1"    # Sheet name containing party data

# --- Excel column names (must match headers in the Excel sheet exactly) ---
# Page 2 – Legal Entity
# LE_NAME, LE_HSAAP_NZBN__C, LE_HSAAP_SUPPLIER_NUMBER__C,
# LE_HSAAP_PROVIDER_TYPE__C, LE_HSAAP_TRADING_NAME__C,
# LE_HSAAP_HPI__C, LE_HSAAP_GST_REGISTERED__C, LE_HSAAP_GST_NUMBER__C
#
# Page 3 – Provider Site
# PS_NAME, PS_HSAAP_SITE_NAME__C, PS_HSAAP_PERORG_ID__C,
# PS_HSAAP_GST_REGISTERED__C, PS_HSAAP_GST_NUMBER__C, PS_HSAAP_PAYEE_NUMBER__C
#
# Page 4 – Address
# CPA_STREET
#
# Page 5 – Address type
# CPA_ADDRESS_TYPE  (values: MAILING / PHYSICAL)
#
# Page 6 – Email
# CPE_EMAIL_ADDRESS, CPE_HSAAP_OUTCOME_NOTIFICATIONS__C  (TRUE to check)
#
# Page 7 – Phone
# CPP_TELEPHONE, CPP_TELEPHONE_TYPE  (values: MAIN / OTHER)

# --- Screenshots ---
SCREENSHOTS_DIR = "screenshots"   # Saved on error; set None to disable
