from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

def scrape(product: str):
    query = product.replace(" ", "+")
    url = f"https://www.amazon.com/s?k={query}"

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    time.sleep(5)  # wait for JS to load
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    results = soup.select(".s-main-slot > .s-result-item")

    for item in results:
        if not item.get("data-asin"):
            continue

        brand_tag = item.select_one("h2.a-size-mini span.a-size-medium")
        title_tag = item.select_one("a.a-link-normal h2 span")

        price_whole = item.select_one(".a-price .a-price-whole")
        price_fraction = item.select_one(".a-price .a-price-fraction")
        rating = item.select_one(".a-icon-alt")
        reviews = item.select_one(".s-link-style .s-underline-text")

        # Debug
        print("BRAND:", brand_tag.text.strip() if brand_tag else "None")
        print("TITLE:", title_tag.text.strip() if title_tag else "None")
        print("------")

        if brand_tag and title_tag and price_whole and price_fraction:
            full_title = f"{brand_tag.text.strip()} {title_tag.text.strip()}"
            return {
                "Website": "Amazon.com",
                "Title": full_title,
                "Price (USD)": f"{price_whole.text.strip()}{price_fraction.text.strip()}",
                "Rating": rating.text.strip() if rating else "N/A",
                "Reviews": reviews.text.strip() if reviews else "N/A"
            }

    return {"error": "No valid products found"}
