import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth
import time
from io import BytesIO
from PIL import Image
import pandas as pd
import random
import zlib
import requests
from minio import Minio
from datetime import date
import boto3
from botocore.client import Config


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

def set_viewport_size(driver, width, height):
    window_size = driver.execute_script("""
        return [window.outerWidth - window.innerWidth + arguments[0],
          window.outerHeight - window.innerHeight + arguments[1]];
        """, width, height)
    driver.set_window_size(*window_size)

@data_loader
def load_data(data_from_scraper_url_list,**kwargs):
    url_array = []
    date_stamp= date.today().isoformat()
    brand_name = kwargs['GOAT_BRAND_NAME']

    service = Service(executable_path=f"{os.getcwd()}/data-lab/chromedriver-linux64/chromedriver")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(service=service, options=options)
    
    # Compressing Meta Urls

    df = data_from_scraper_url_list

    df_bytes = df.to_csv(index=False).encode()
    compressed_data = zlib.compress(df_bytes,level=6)
    # print(csv_buffer.getvalue())
    
    

    s3 = boto3.client('s3', endpoint_url="http://10.10.0.50:6000", aws_access_key_id=kwargs['s3AccessKey'],
                  aws_secret_access_key=kwargs['s3SecretKey'])
    
    s3.upload_fileobj(BytesIO(compressed_data), "sst-data-crawler", f"raw/text/listing/goat/brand/{brand_name}/{date_stamp}/meta_urls.gz")
    print("File meta Uploaded")

    df_list = []
    
    for index, row in df.iterrows():
        print(f"Processing {index+1} of {len(df)}")
        
        time.sleep(random.randrange(2,5))
        try:
        
            # set the view port to use mobile iPad Air 2 View
            set_viewport_size(driver, 21560, 2109)
            driver.execute_script("return [window.innerWidth, window.innerHeight];")
            action = webdriver.ActionChains(driver)
            

            # setting user agents
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            user_agent = random.choice(user_agents)
            options.add_argument(f'user-agent={user_agent}')
            
            
            url = row['URLS']
            stealth(driver,
                    languages=["en-US", "en"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True,
                    )
            driver.get(url)


            price_list = driver.find_elements(By.CSS_SELECTOR,'[data-swiper-slide-index]')
            price_list = list(map(lambda x: x.get_attribute("innerText"), price_list))
            

            product_title_year = driver.find_element(By.CSS_SELECTOR,"[data-qa='product_year']")
            arr_product_title_year = product_title_year.get_attribute("innerText").split("\n")
            product_year,product_name,tags = arr_product_title_year[0],arr_product_title_year[1],arr_product_title_year[2:]
            # print(year,name,tags)
            product_row = {}
            try:

                product_facts_text = driver.find_element(By.CSS_SELECTOR,".FactsWindow__Wrapper-sc-1hjbbqw-1 > .WindowItemLongText__Wrapper-sc-1mxjefz-0")
                product_facts_text = product_facts_text.get_attribute("innerText")
                product_row["facts"] = product_facts_text
            except Exception as productfact_err:
                # print("Error Product Facts",url)
                # print("Error Product Facts",productfact_err)
                product_row["facts"] = product_name
            

            product_features = driver.find_elements(By.CSS_SELECTOR,".FactsWindow__Wrapper-sc-1hjbbqw-1 > div:nth-child(n+4):nth-last-child(n+3)")
            product_features = list(map(lambda x: x.get_attribute("innerText"), product_features))
            

            
            for feature in product_features:
                feature_kv = feature.split("\n")
                key = str(feature_kv[0]).lower().replace(' ','_')
                val = str(feature_kv[1]).lower()
                product_row[key] = val

            product_row["name"] = product_name
            product_row["tags"] = str(",").join(tags)
            product_row["year"] = product_year


            price_product_item_list = []
            
            for price_item in price_list:
                price_item_kv = price_item.split("\n")
                product_item = {}
                size = price_item_kv[0]
                price = price_item_kv[1]
                product_item["size"] = size
                product_item["price"] = price
                product_item.update(product_row)
                
                price_product_item_list.append(product_item)
            price_dataframe = pd.DataFrame(price_product_item_list)
            df_list.append(price_dataframe)

            
            # return price_dataframe   
            
        except Exception as e:
            print("ErrorURL",url)
            print("DETAIL_SCRAPER",e)

        finally:
            pass
            
        
    driver.quit()

    result = pd.concat(df_list,ignore_index=True)
        
    return result
    

