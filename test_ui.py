import pytest
import time
import subprocess
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


# Simple configuration
STREAMLIT_URL = "http://localhost:8501"
TIMEOUT = 10


@pytest.fixture(scope="session")
def start_app():
    """Start Streamlit app for testing"""
    print("Starting Streamlit app...")
    
    # Start app in background
    process = subprocess.Popen([
        "streamlit", "run", "streamlit_app.py",
        "--server.port", "8501"
    ])
    
    # Wait for app to start
    for _ in range(20):
        try:
            response = requests.get(STREAMLIT_URL, timeout=3)
            if response.status_code == 200:
                print("App is ready!")
                break
        except:
            time.sleep(2)
    
    yield
    
    # Stop app
    process.terminate()


@pytest.fixture
def browser():
    """Setup Chrome browser"""
    options = Options()
    options.add_argument("--headless")  # Run without opening browser window
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


class TestBasicUI:
    """Simple UI tests"""
    
    def test_page_loads(self, browser, start_app):
        """Test 1: Check if page loads successfully"""
        browser.get(STREAMLIT_URL)
        
        # Wait for main heading to appear
        heading = WebDriverWait(browser, TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        
        assert "Reddit Persona Generator" in heading.text
        print("✅ Page loaded successfully")
    
    def test_input_field_exists(self, browser, start_app):
        """Test 2: Check if URL input field exists"""
        browser.get(STREAMLIT_URL)
        
        # Find the input field
        input_field = WebDriverWait(browser, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
        )
        
        assert input_field.is_displayed()
        print("✅ Input field found")
    
    def test_can_type_in_input(self, browser, start_app):
        """Test 3: Check if we can type in the input field"""
        browser.get(STREAMLIT_URL)
        
        # Find input and type in it
        input_field = WebDriverWait(browser, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
        )
        
        test_text = "https://www.reddit.com/user/testuser/"
        input_field.send_keys(test_text)
        
        # Check if text was entered
        assert input_field.get_attribute("value") == test_text
        print("✅ Can type in input field")
    
    def test_analyze_button_exists(self, browser, start_app):
        """Test 4: Check if analyze button exists and is clickable"""
        browser.get(STREAMLIT_URL)

        try:
            # Try to find the button
            button = WebDriverWait(browser, TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@data-testid='stMarkdownContainer'][.//p[contains(text(), 'Analyze Profile')]]"))
            )


            # Print its outer HTML if found
            print("\n🔍 Button outerHTML:\n", button.get_attribute("outerHTML"))

            assert button.is_displayed()
            assert button.is_enabled()
            print("✅ Analyze button found and clickable")

        except Exception as e:
            # Print full page source to help debugging
            print("\n❌ Could not find clickable button.")
            print("📄 Page HTML:\n", browser.page_source[:3000])  # Print only first 3000 chars
            raise e

    
    def test_button_click(self, browser, start_app):
        """Test 5: Check if button click works (without full processing)"""
        browser.get(STREAMLIT_URL)
        
        # Enter URL
        input_field = WebDriverWait(browser, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
        )
        input_field.send_keys("https://www.reddit.com/user/spez/")
        
        # Click button
        button = browser.find_element(By.XPATH, "//div[@data-testid='stMarkdownContainer'][.//p[contains(text(), 'Analyze Profile')]]")
        button.click()
        
        # Just wait a moment to see if anything happens
        time.sleep(3)
        
        # Check if page is still responsive (doesn't crash)
        heading = browser.find_element(By.TAG_NAME, "h1")
        assert heading.is_displayed()
        print("✅ Button click works without crashing")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])