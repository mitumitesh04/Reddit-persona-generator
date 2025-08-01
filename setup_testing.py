import subprocess
import sys
import os

def run_command(cmd, check=True):
    """Run a command and return success/failure"""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        return False

def check_python():
    """Check if Python is installed"""
    try:
        version = subprocess.check_output([sys.executable, "--version"], text=True)
        print(f"✅ {version.strip()}")
        return True
    except:
        print("❌ Python not found")
        return False

def install_packages():
    """Install required packages"""
    packages = [
        "pytest",
        "selenium", 
        "streamlit",
        "webdriver-manager",
        "requests"
    ]
    
    print("📦 Installing packages...")
    for package in packages:
        print(f"Installing {package}...")
        if not run_command(f"pip install {package}"):
            print(f"❌ Failed to install {package}")
            return False
    
    print("✅ All packages installed!")
    return True

def create_simple_test():
    """Create a very simple test to verify everything works"""
    test_content = '''
# test_verify.py
# Simple test to verify setup works

def test_basic_math():
    """Simple test that should always pass"""
    assert 2 + 2 == 4

def test_string_operations():
    """Test string operations"""
    text = "Hello World"
    assert "Hello" in text
    assert len(text) == 11

def test_list_operations():
    """Test list operations"""
    numbers = [1, 2, 3, 4, 5]
    assert len(numbers) == 5
    assert sum(numbers) == 15

if __name__ == "__main__":
    print("All basic tests would pass!")
'''
    
    with open("test_verify.py", "w") as f:
        f.write(test_content.strip())
    
    print("✅ Created verification test file")

def run_verification_test():
    """Run a simple test to verify pytest works"""
    print("\n🧪 Running verification test...")
    if run_command("pytest test_verify.py -v"):
        print("✅ Pytest is working correctly!")
        return True
    else:
        print("❌ Pytest test failed")
        return False

def check_chrome():
    """Check if Chrome is available for Selenium"""
    chrome_paths = [
        "google-chrome",
        "chromium-browser", 
        "chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    ]
    
    for chrome_path in chrome_paths:
        if run_command(f"which {chrome_path}", check=False):
            print(f"✅ Chrome found: {chrome_path}")
            return True
    
    print("⚠️  Chrome not found. UI tests might not work.")
    print("   Install Chrome from: https://www.google.com/chrome/")
    return False

def main():
    """Main setup function"""
    print("🚀 Setting up Simple Testing Environment")
    print("=" * 50)
    
    # Check Python
    if not check_python():
        print("Please install Python first")
        return False
    
    # Install packages
    if not install_packages():
        return False
    
    # Check Chrome
    check_chrome()
    
    # Create and run verification test
    create_simple_test()
    if not run_verification_test():
        return False
    
    # Show next steps
    print("\n" + "=" * 50)
    print(" Setup Complete!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Run unit tests: pytest test_backend.py -v")
    print("2. Run UI tests: pytest test_ui.py -v") 
    print("3. Run all tests: pytest -v")
    print("4. Use test runner: python run_tests.py")
    print("\nFiles created:")
    print("- test_verify.py (verification test)")
    print("\nYou're ready to start testing! 🧪")
    
    # Cleanup verification file
    try:
        os.remove("test_verify.py")
    except:
        pass
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)