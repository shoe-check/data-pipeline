import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth
import time
from io import BytesIO
from PIL import Image
import random
import requests
from minio import Minio


if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

user_agents = [
    # Add your list of user agents here
	'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
]



def scroll_webpage_until_end(driver):
    # Get initial scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Wait for some time to load content
        time.sleep(2)

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        print("Scrolling")
        if new_height == last_height:
            # If heights are the same, it means end of page
            return
        last_height = new_height

def set_viewport_size(driver, width, height):
    window_size = driver.execute_script("""
        return [window.outerWidth - window.innerWidth + arguments[0],
          window.outerHeight - window.innerHeight + arguments[1]];
        """, width, height)
    driver.set_window_size(*window_size)

def create_bucket(minio_client,bucket_name):
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

@data_loader
def load_data_from_api(*args, **kwargs):
    """
    Template for loading data from API
    """

    minio_client = Minio(
    "10.10.0.50:6000",
    access_key=kwargs['s3AccessKey'],
    secret_key=kwargs['s3SecretKey'],
    secure=False  # Change to True if using HTTPS
)
    
    service = Service(executable_path=f"{os.getcwd()}/data-lab/chromedriver-linux64/chromedriver")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(service=service, options=options)
    # set the view port to use mobile iPad Air 2 View
    set_viewport_size(driver, 820, 1180)
    driver.execute_script("return [window.innerWidth, window.innerHeight];")

    # setting user agents
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    user_agent = random.choice(user_agents)
    options.add_argument(f'user-agent={user_agent}')
    
    
    url = 'https://www.reddit.com/r/sneakermarket/'
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )
    driver.get(url)

    create_bucket(minio_client,"sst-shoe-images")
    # Wait for the page to load (adjust sleep time as needed)
    time.sleep(10)

    scroll_webpage_until_end(driver)
    
    image_elements = driver.find_elements(By.CSS_SELECTOR, "#main-content > div:nth-child(3) > faceplate-batch > article > shreddit-post > div[slot='post-media-container'] > shreddit-async-loader > gallery-carousel > ul > li > img")
    print(len(image_elements))
    
    # Download and save webp images
    for idx, img_element in enumerate(image_elements):
        img_src = img_element.get_attribute("src")
        
        if img_src != None and 'webp' in img_src:
            time.sleep(3)
            response = requests.get(img_src)
            img_webp = Image.open(BytesIO(response.content))
            img = img_webp.convert('RGB')
            img = img.resize((640,640))
            
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='jpeg')
            img_byte_arr = img_byte_arr.getvalue()
            
            
            try:
                minio_client.put_object("sst-shoe-images", f"scrape/raw/sneakermarket/image_{idx+1}.jpeg", BytesIO(img_byte_arr),len(img_byte_arr))
                # img.save(f"{os.getcwd()}/data-lab/output/image_{idx+1}.webp")
            except Exception as err:
                print(err)

    # Close the webdriver
    driver.quit()

    return ""


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
