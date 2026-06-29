"""
Full wizard flow for creating a new Party in Salesforce Health NZ FPIM.

Page sequence:
  0  Parties list → click New
  1  Record type  → Legal Entity (default) → Next
  2  Legal Entity details                  → Next
  3  Provider Site details                 → Save and Create Address
  4  Address search                        → Next
  5  Address type                          → Save Address
  6  Email                                 → Save
  7  Phone                                 → Save
  8  Completion: Finish → Sync with ALM → validate → back to Parties
"""

import logging
import os
import time
from typing import Any, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
)

logger = logging.getLogger(__name__)

# Normalise label text the same way in JS and XPath:
# strip asterisks (required-field markers) then collapse whitespace.
_JS_FIND_INPUT = """
(function(labelText) {
    function clean(t){ return t.replace(/\\*/g,'').replace(/\\s+/g,' ').trim(); }
    function matches(el){ var c = clean(el.textContent); return c === labelText || c.startsWith(labelText); }
    function search(root) {
        var candidates = root.querySelectorAll(
            'label, span.slds-form-element__label, legend, .slds-form-element__label'
        );
        for (var i = 0; i < candidates.length; i++) {
            var el = candidates[i];
            if (matches(el)) {
                var forId = el.getAttribute('for');
                if (forId) {
                    var byId = root.getElementById
                        ? root.getElementById(forId)
                        : root.querySelector('#' + CSS.escape(forId));
                    if (byId) return byId;
                }
                var container = el.closest(
                    '.slds-form-element, lightning-input, lightning-textarea, lightning-combobox, lightning-input-field'
                );
                if (container) {
                    var inp = container.querySelector(
                        'input:not([type="hidden"]), textarea, select'
                    );
                    if (inp) return inp;
                }
            }
        }
        var children = root.querySelectorAll('*');
        for (var j = 0; j < children.length; j++) {
            if (children[j].shadowRoot) {
                var found = search(children[j].shadowRoot);
                if (found) return found;
            }
        }
        return null;
    }
    return search(document);
})(arguments[0]);
"""

_JS_FIND_COMBOBOX = """
(function(labelText) {
    function clean(t){ return t.replace(/\\*/g,'').replace(/\\s+/g,' ').trim(); }
    function matches(el){ var c = clean(el.textContent); return c === labelText || c.startsWith(labelText); }
    function search(root) {
        var candidates = root.querySelectorAll(
            'label, span.slds-form-element__label, .slds-form-element__label'
        );
        for (var i = 0; i < candidates.length; i++) {
            var el = candidates[i];
            if (matches(el)) {
                var container = el.closest(
                    '.slds-form-element, lightning-combobox, lightning-input-field'
                );
                if (container) {
                    var btn = container.querySelector(
                        'button[aria-haspopup="listbox"], select, button[role="combobox"]'
                    );
                    if (btn) return btn;
                }
            }
        }
        var children = root.querySelectorAll('*');
        for (var j = 0; j < children.length; j++) {
            if (children[j].shadowRoot) {
                var found = search(children[j].shadowRoot);
                if (found) return found;
            }
        }
        return null;
    }
    return search(document);
})(arguments[0]);
"""

_JS_FIND_CHECKBOX = """
(function(labelText) {
    function clean(t){ return t.replace(/\\*/g,'').replace(/\\s+/g,' ').trim(); }
    function matches(el){ var c = clean(el.textContent); return c === labelText || c.startsWith(labelText); }
    function search(root) {
        var candidates = root.querySelectorAll(
            'label, span.slds-form-element__label, .slds-form-element__label'
        );
        for (var i = 0; i < candidates.length; i++) {
            var el = candidates[i];
            if (matches(el)) {
                var forId = el.getAttribute ? el.getAttribute('for') : null;
                if (forId) {
                    var cb = document.getElementById(forId);
                    if (cb && cb.type === 'checkbox') return cb;
                }
                var container = el.closest('.slds-form-element, .slds-checkbox, lightning-input');
                if (container) {
                    var cb = container.querySelector('input[type="checkbox"]');
                    if (cb) return cb;
                }
            }
        }
        var children = root.querySelectorAll('*');
        for (var j = 0; j < children.length; j++) {
            if (children[j].shadowRoot) {
                var found = search(children[j].shadowRoot);
                if (found) return found;
            }
        }
        return null;
    }
    return search(document);
})(arguments[0]);
"""


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_party_creation(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    party_data: Dict[str, Any],
    screenshots_dir: str = "screenshots",
) -> None:
    name = party_data.get("LE_NAME", "?")
    logger.info("══ Starting party: %s", name)

    _click_new_button(driver, wait)
    _page_record_type(driver, wait, screenshots_dir)
    _page_legal_entity(driver, wait, party_data, screenshots_dir)
    _page_provider_site(driver, wait, party_data, screenshots_dir)
    _page_address_search(driver, wait, party_data, screenshots_dir)
    _page_address_type(driver, wait, party_data, screenshots_dir)
    _page_email(driver, wait, party_data, screenshots_dir)
    _page_phone(driver, wait, party_data, screenshots_dir)
    _page_finish_and_sync(driver, wait, screenshots_dir)

    logger.info("══ Completed party: %s", name)


# ─────────────────────────────────────────────────────────────────────────────
# Navigation helpers (called from main)
# ─────────────────────────────────────────────────────────────────────────────

def navigate_to_parties(driver: webdriver.Firefox, wait: WebDriverWait) -> None:
    """Navigate to Parties list via the nav link (fast SPA transition), then immediately
    refresh the page to flush any residual wizard DOM from the previous record.
    Two 30-second waits rather than one slow full cold-load."""
    link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[title="Parties"]')))
    link.click()
    _wait_for_parties_list(wait)
    driver.refresh()
    _wait_for_parties_list(wait)
    time.sleep(2)
    logger.info("Parties list ready")


def click_parties_link(driver: webdriver.Firefox, wait: WebDriverWait) -> None:
    """Alias used after Sync – delegates to navigate_to_parties via stored URL.
    Kept as a separate function so _page_finish_and_sync stays decoupled from config."""
    link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[title="Parties"]')))
    link.click()
    _wait_for_parties_list(wait)
    logger.info("Returned to Parties list via nav link")


def _wait_for_parties_list(wait: WebDriverWait) -> None:
    """Wait for an element that is only present on the Parties list view."""
    wait.until(EC.presence_of_element_located((
        By.CSS_SELECTOR,
        '[data-target-selection-name="sfdc:StandardButton.Account.New"]',
    )))


def close_wizard_tab(driver: webdriver.Firefox, wait: WebDriverWait) -> None:
    """Close the 'New Party' wizard tab without triggering an auto-submit.
    Called when an error occurs mid-wizard to prevent incomplete record creation."""
    try:
        close_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            '//div[contains(@class,"slds-context-bar__item")]'
            '[.//span[normalize-space(.)="New Party"]]'
            '//button[contains(@class,"close") or @title="Close New Party"]',
        )))
        close_btn.click()
        logger.info("Wizard tab closed to prevent incomplete submission")
        # Handle any 'Leave page?' confirmation dialog
        try:
            leave_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
                By.XPATH, '//button[normalize-space(.)="Leave" or normalize-space(.)="Leave Page"]',
            )))
            leave_btn.click()
            logger.info("Leave-page dialog confirmed")
        except TimeoutException:
            pass
    except TimeoutException:
        logger.warning("Could not find wizard tab close button – navigating to Parties directly")


# ─────────────────────────────────────────────────────────────────────────────
# Step 0 – New button
# ─────────────────────────────────────────────────────────────────────────────

def _click_new_button(driver: webdriver.Firefox, wait: WebDriverWait) -> None:
    logger.info("Clicking New button")
    btn = wait.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR,
        '[data-target-selection-name="sfdc:StandardButton.Account.New"] a[role="button"]',
    )))
    btn.click()


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 – Record type (Legal Entity is default → Next)
# ─────────────────────────────────────────────────────────────────────────────

def _page_record_type(
    driver: webdriver.Firefox, wait: WebDriverWait, screenshots_dir: str
) -> None:
    logger.info("Page 1: record type – Legal Entity default → Next")
    wait.until(EC.presence_of_element_located((
        By.XPATH, '//*[contains(text(),"Legal Entity")]',
    )))
    _screenshot(driver, screenshots_dir, "page1_record_type")
    _click_button(driver, wait, "Next")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 – Legal Entity details
# ─────────────────────────────────────────────────────────────────────────────

def _page_legal_entity(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    data: Dict[str, Any],
    screenshots_dir: str,
) -> None:
    logger.info("Page 2: Legal Entity details")
    _wait_for_label(driver, wait, "Legal Entity Name")
    # GST Registered is the last always-present field – waiting for it ensures
    # the full form is rendered before we start filling (important for cached loads).
    _wait_for_label(driver, wait, "GST Registered")
    _screenshot(driver, screenshots_dir, "page2_legal_entity")

    _fill_text(driver, wait, "Legal Entity Name", data.get("LE_NAME"))
    _fill_text(driver, wait, "NZBN",              data.get("LE_HSAAP_NZBN__C"))
    _fill_text(driver, wait, "FPIM Supplier Number", data.get("LE_HSAAP_SUPPLIER_NUMBER__C"))
    _fill_picklist(driver, wait, "Party Type",    data.get("LE_HSAAP_PROVIDER_TYPE__C"))
    _fill_text(driver, wait, "Trading Name",      data.get("LE_HSAAP_TRADING_NAME__C"))
    _fill_text(driver, wait, "HPI",               data.get("LE_HSAAP_HPI__C"))

    gst = _str(data.get("LE_HSAAP_GST_REGISTERED__C"))
    _fill_picklist(driver, wait, "GST Registered", gst)
    if gst.upper() == "YES":
        _fill_text(driver, wait, "GST Number", data.get("LE_HSAAP_GST_NUMBER__C"))

    _click_button(driver, wait, "Next")


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 – Provider Site details
# ─────────────────────────────────────────────────────────────────────────────

def _page_provider_site(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    data: Dict[str, Any],
    screenshots_dir: str,
) -> None:
    logger.info("Page 3: Provider Site details")
    _wait_for_label(driver, wait, "Provider Site Name")
    # Payee Number is the last field on this page – waiting for it ensures the full
    # form is rendered before filling (avoids race condition on subsequent records).
    _wait_for_label(driver, wait, "Payee Number")
    _screenshot(driver, screenshots_dir, "page3_provider_site")

    _fill_text(driver, wait, "Provider Site Name", data.get("PS_NAME"))
    _fill_text(driver, wait, "FPIM Site Name",     data.get("PS_HSAAP_SITE_NAME__C"))
    _fill_text(driver, wait, "PerOrg ID",          data.get("PS_HSAAP_PERORG_ID__C"))

    gst = _str(data.get("PS_HSAAP_GST_REGISTERED__C"))
    _fill_picklist(driver, wait, "GST Registered", gst)
    if gst.upper() == "YES":
        _fill_text(driver, wait, "GST Number", data.get("PS_HSAAP_GST_NUMBER__C"))

    _fill_text(driver, wait, "Payee Number", data.get("PS_HSAAP_PAYEE_NUMBER__C"))
    _click_button(driver, wait, "Save & Create Address")


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 – Address search
# ─────────────────────────────────────────────────────────────────────────────

def _page_address_search(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    data: Dict[str, Any],
    screenshots_dir: str,
) -> None:
    logger.info("Page 4: Address search")
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[name="addressSearch"]')))
    _screenshot(driver, screenshots_dir, "page4_address")

    address = _str(data.get("CPA_STREET"))
    if address:
        search_box = driver.find_element(By.CSS_SELECTOR, 'input[name="addressSearch"]')
        search_box.clear()
        search_box.send_keys(address)
        first_result = wait.until(EC.element_to_be_clickable((
            By.XPATH, '(//div[@role="option"])[1]',
        )))
        first_result.click()
        logger.info("Address selected: %s", address)
        # Wait for the selection to register before clicking Next
        time.sleep(5)
    else:
        logger.warning("CPA_STREET is empty – address left blank")

    _click_button(driver, wait, "Next")


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 – Address type
# ─────────────────────────────────────────────────────────────────────────────

def _page_address_type(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    data: Dict[str, Any],
    screenshots_dir: str,
) -> None:
    logger.info("Page 5: Address type")
    _screenshot(driver, screenshots_dir, "page5_address_type")
    _wait_for_label(driver, wait, "Address Type")

    _fill_picklist(driver, wait, "Address Type", data.get("CPA_ADDRESS_TYPE"))
    # "Is Primary" is checked by default – leave it
    _click_button(driver, wait, "Save Address")


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 – Email
# ─────────────────────────────────────────────────────────────────────────────

def _page_email(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    data: Dict[str, Any],
    screenshots_dir: str,
) -> None:
    logger.info("Page 6: Email")
    _wait_for_label(driver, wait, "Email address")
    _screenshot(driver, screenshots_dir, "page6_email")

    _fill_text(driver, wait, "Email address", data.get("CPE_EMAIL_ADDRESS"))

    notif = _str(data.get("CPE_HSAAP_OUTCOME_NOTIFICATIONS__C"))
    if notif.upper() in ("TRUE", "YES", "1"):
        _check_checkbox(driver, wait, "CDA Outcome Notifications")

    _click_button(driver, wait, "Save")


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 – Phone
# ─────────────────────────────────────────────────────────────────────────────

def _page_phone(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    data: Dict[str, Any],
    screenshots_dir: str,
) -> None:
    logger.info("Page 7: Phone")
    _wait_for_label(driver, wait, "Telephone number")
    _screenshot(driver, screenshots_dir, "page7_phone")

    _fill_text(driver, wait, "Telephone number", data.get("CPP_TELEPHONE"))
    _fill_picklist(driver, wait, "Phone Type",   data.get("CPP_TELEPHONE_TYPE"))
    _click_button(driver, wait, "Save")


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 – Finish, Sync with ALM, validate, return to Parties
# ─────────────────────────────────────────────────────────────────────────────

def _page_finish_and_sync(
    driver: webdriver.Firefox, wait: WebDriverWait, screenshots_dir: str
) -> None:
    logger.info("Page 8: Finish")
    wait.until(EC.presence_of_element_located((
        By.XPATH, '//*[contains(text(),"Provider setup is complete")]',
    )))
    _screenshot(driver, screenshots_dir, "page8_complete")
    logger.info("Completion message confirmed")

    _click_button(driver, wait, "Finish")

    logger.info("Sync with ALM – clicking trigger")
    _click_button(driver, wait, "Sync with ALM")
    time.sleep(2)

    logger.info("Sync with ALM – confirming")
    _click_button(driver, wait, "Sync")
    time.sleep(2)

    logger.info("Reloading and validating Party Status")
    driver.refresh()

    try:
        wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            'img[alt="Synced with ALM"], img[src*="HSAAP_ProviderSyncedWithALM"]',
        )))
        logger.info("Party Status: Synced with ALM ✓")
    except TimeoutException:
        logger.warning("Could not confirm 'Synced with ALM' status – check manually")


# ─────────────────────────────────────────────────────────────────────────────
# Field interaction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fill_text(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    label: str,
    value,
) -> None:
    if not _has_value(value):
        logger.debug("Skipping '%s' – no value", label)
        return
    value = _str(value)
    logger.debug("Filling '%s' = '%s'", label, value)

    # Retry up to 3 times (1 s apart) in case the input renders after the label.
    elem = None
    for attempt in range(4):
        elem = _input_by_label(driver, label)
        if elem is not None:
            break
        if attempt < 3:
            time.sleep(1)

    if elem is None:
        logger.warning("Field '%s' not found – skipped", label)
        return
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", elem)
        elem.clear()
        elem.send_keys(value)
    except ElementNotInteractableException:
        logger.warning("Field '%s' not interactable – skipped", label)


def _fill_picklist(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    label: str,
    value,
) -> None:
    if not _has_value(value):
        logger.debug("Skipping picklist '%s' – no value", label)
        return
    value = _str(value)
    logger.debug("Filling picklist '%s' = '%s'", label, value)

    # Try native <select> via shadow DOM JS
    trigger = driver.execute_script(_JS_FIND_COMBOBOX, label)
    if trigger is None:
        # Fallback: XPath-based container
        trigger = _combobox_trigger_xpath(driver, label)

    if trigger is None:
        logger.warning("Picklist '%s' not found – skipped", label)
        return

    tag = trigger.tag_name.lower()
    if tag == "select":
        try:
            Select(trigger).select_by_visible_text(value)
            return
        except Exception as exc:
            logger.warning("Select '%s' failed: %s", label, exc)
            return

    # Lightning combobox button – click to open, then pick option
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", trigger)
        trigger.click()
        option = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            f'//lightning-base-combobox-item[normalize-space(.)="{value}"]'
            f' | //*[@role="option"][normalize-space(.)="{value}"]',
        )))
        option.click()
    except TimeoutException:
        logger.warning("Picklist option '%s' for field '%s' not found", value, label)
    except Exception as exc:
        logger.warning("Picklist '%s' error: %s", label, exc)


def _check_checkbox(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    label: str,
) -> None:
    """Check a checkbox by clicking its LABEL element (more reliable than clicking the
    hidden input because SLDS hides the real <input> with CSS and requires a label click
    to properly trigger LWC's event listeners)."""
    logger.debug("Checking checkbox '%s'", label)
    t = f'normalize-space(translate(., "*", ""))'

    def _is_checked(for_id: str) -> bool:
        try:
            return driver.find_element(By.ID, for_id).is_selected()
        except Exception:
            return False

    # Strategy 1: XPath – find label with matching text, click it
    for xpath in [
        # Prefer label[for=...] so we can also read current state
        f'//label[@for][starts-with({t}, "{label}")]',
        # Fallback: any label with matching text (including outer wrapper labels)
        f'//label[starts-with({t}, "{label}")]',
    ]:
        try:
            lbl = driver.find_element(By.XPATH, xpath)
            for_id = lbl.get_attribute("for") or ""
            if for_id and _is_checked(for_id):
                logger.debug("Checkbox '%s' already checked", label)
                return
            driver.execute_script("arguments[0].scrollIntoView({block:'center'})", lbl)
            driver.execute_script("arguments[0].click()", lbl)
            logger.debug("Checkbox '%s' checked via label click", label)
            return
        except NoSuchElementException:
            continue

    # Strategy 2: JS shadow-DOM traversal – find label, click it
    js_label = """
(function(labelText) {
    function clean(t){ return t.replace(/\\*/g,'').replace(/\\s+/g,' ').trim(); }
    function matches(el){ var c = clean(el.textContent); return c === labelText || c.startsWith(labelText); }
    function search(root) {
        var labels = root.querySelectorAll('label, span.slds-form-element__label');
        for (var i = 0; i < labels.length; i++) {
            if (matches(labels[i])) return labels[i];
        }
        var children = root.querySelectorAll('*');
        for (var j = 0; j < children.length; j++) {
            if (children[j].shadowRoot) {
                var found = search(children[j].shadowRoot);
                if (found) return found;
            }
        }
        return null;
    }
    return search(document);
})(arguments[0]);
"""
    lbl = driver.execute_script(js_label, label)
    if lbl:
        for_id = lbl.get_attribute("for") or ""
        if for_id and _is_checked(for_id):
            logger.debug("Checkbox '%s' already checked", label)
            return
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", lbl)
        driver.execute_script("arguments[0].click()", lbl)
        logger.debug("Checkbox '%s' checked via JS label click", label)
        return

    logger.warning("Checkbox '%s' not found – skipped", label)


def _click_button(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    text: str,
) -> None:
    logger.debug("Clicking button '%s'", text)
    btn = wait.until(EC.element_to_be_clickable((
        By.XPATH,
        f'//button[normalize-space(.)="{text}"]'
        f' | //button[@title="{text}"]'
        f' | //a[@role="button"][normalize-space(.)="{text}"]',
    )))
    btn.click()
    try:
        WebDriverWait(driver, 2).until(EC.staleness_of(btn))
    except TimeoutException:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# DOM / shadow-DOM lookup helpers
# ─────────────────────────────────────────────────────────────────────────────

def _wait_for_label(
    driver: webdriver.Firefox, wait: WebDriverWait, label_text: str
) -> None:
    """Wait until a label whose text (asterisks stripped) starts-with label_text is present.
    Uses starts-with so that info-icon buttons that add extra text to textContent don't break the match."""
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((
        By.XPATH,
        f'//*[starts-with(normalize-space(translate(., "*", "")), "{label_text}")]',
    )))
    logger.debug("Label '%s' found", label_text)


def _input_by_label(driver: webdriver.Firefox, label: str) -> Optional[Any]:
    """Find a VISIBLE input/textarea by label text.
    Uses find_elements (not find_element) so we can skip hidden/stale elements left
    in the DOM from a previously completed wizard – the root cause of fields being
    silently missed on the second and subsequent records."""
    t = f'normalize-space(translate(., "*", ""))'

    def _first_visible(elements):
        for el in elements:
            try:
                if el.is_displayed():
                    return el
            except Exception:
                continue
        return None

    # Strategy 1: label[for] → find input by id, return first visible match
    for lbl in driver.find_elements(By.XPATH, f'//label[starts-with({t}, "{label}")]'):
        try:
            if not lbl.is_displayed():
                continue
            for_id = lbl.get_attribute("for")
            if not for_id:
                continue
            elem = _first_visible(driver.find_elements(By.ID, for_id))
            if elem:
                return elem
        except Exception:
            continue

    # Strategy 2: visible label → ancestor slds-form-element → first visible input
    for lbl in driver.find_elements(By.XPATH, f'//label[starts-with({t}, "{label}")]'):
        try:
            if not lbl.is_displayed():
                continue
            container = lbl.find_element(
                By.XPATH, 'ancestor::div[contains(@class,"slds-form-element")][1]'
            )
            elem = _first_visible(container.find_elements(
                By.XPATH, './/input[not(@type="hidden")] | .//textarea'
            ))
            if elem:
                return elem
        except Exception:
            continue

    # Strategy 3: any visible element with matching text → ancestor → first visible input
    for el in driver.find_elements(By.XPATH, f'//*[starts-with({t}, "{label}")]'):
        try:
            if not el.is_displayed():
                continue
            container = el.find_element(
                By.XPATH, 'ancestor::div[contains(@class,"slds-form-element")][1]'
            )
            elem = _first_visible(container.find_elements(
                By.XPATH, './/input[not(@type="hidden")] | .//textarea'
            ))
            if elem:
                return elem
        except Exception:
            continue

    # Strategy 4: JS shadow-DOM traversal as last resort
    return driver.execute_script(_JS_FIND_INPUT, label)


def _combobox_trigger_xpath(driver: webdriver.Firefox, label: str) -> Optional[Any]:
    """XPath fallback to locate a picklist trigger button by label."""
    t = f'normalize-space(translate(., "*", ""))'
    for xpath in [
        f'//label[starts-with({t}, "{label}")]/ancestor::div[contains(@class,"slds-form-element")][1]//select',
        f'//label[starts-with({t}, "{label}")]/ancestor::div[contains(@class,"slds-form-element")][1]//button[@aria-haspopup="listbox"]',
        f'//span[starts-with({t}, "{label}")]/ancestor::div[contains(@class,"slds-form-element")][1]//select',
    ]:
        try:
            return driver.find_element(By.XPATH, xpath)
        except NoSuchElementException:
            continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _str(value) -> str:
    return str(value).strip() if value is not None else ""


def _has_value(value) -> bool:
    return value is not None and _str(value) != ""


def take_screenshot(driver: webdriver.Firefox, screenshots_dir: str, name: str) -> None:
    _screenshot(driver, screenshots_dir, name)


def _screenshot(driver: webdriver.Firefox, screenshots_dir: str, name: str) -> None:
    if not screenshots_dir:
        return
    os.makedirs(screenshots_dir, exist_ok=True)
    path = os.path.join(screenshots_dir, f"{name}.png")
    driver.save_screenshot(path)
    logger.info("Screenshot: %s", path)
