from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import re
from typing import List, Dict, Optional

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    product_name: str
    scraping_method: str

class ProductInfo(BaseModel):
    website: str
    title: str
    price: str
    rating: str
    review_count: str
    url: str

def get_headers():
    """Get headers to mimic a real browser"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

def clean_price(price_text: str) -> str:
    """Extract price from text"""
    if not price_text:
        return "N/A"
    # Remove extra whitespace and extract price
    price_text = re.sub(r'\s+', ' ', price_text.strip())
    # Look for price patterns like $123.45
    price_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', price_text)
    if price_match:
        return f"${price_match.group(1)}"
    return price_text[:50]  # Limit length

def clean_rating(rating_text: str) -> str:
    """Extract rating from text"""
    if not rating_text:
        return "N/A"
    # Look for rating patterns like 4.5 out of 5
    rating_match = re.search(r'(\d+\.?\d*)\s*(?:out of|/|\s)*\s*\d*', rating_text)
    if rating_match:
        return rating_match.group(1)
    return rating_text[:10]

def clean_review_count(review_text: str) -> str:
    """Extract review count from text"""
    if not review_text:
        return "N/A"
    # Look for numbers followed by review-related words
    review_match = re.search(r'([\d,]+)\s*(?:review|rating|customer)', review_text, re.IGNORECASE)
    if review_match:
        return review_match.group(1)
    # Just look for numbers
    number_match = re.search(r'([\d,]+)', review_text)
    if number_match:
        return number_match.group(1)
    return review_text[:20]

def scrape_amazon(product_name: str) -> Optional[ProductInfo]:
    """Scrape Amazon for product information"""
    try:
        search_url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(product_name)}"
        
        response = requests.get(search_url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the first product result
        product_container = soup.find('div', {'data-component-type': 's-search-result'})
        if not product_container:
            return None
        
        # Get product link
        link_element = product_container.find('a', class_='a-link-normal')
        if not link_element:
            return None
        
        product_url = "https://www.amazon.com" + link_element.get('href', '')
        
        # Get product page
        time.sleep(1)  # Be respectful
        product_response = requests.get(product_url, headers=get_headers(), timeout=10)
        product_response.raise_for_status()
        
        product_soup = BeautifulSoup(product_response.content, 'html.parser')
        
        # Extract information
        title_element = product_soup.find('span', {'id': 'productTitle'})
        title = title_element.get_text(strip=True) if title_element else "N/A"
        
        # Price - try multiple selectors
        price = "N/A"
        price_selectors = [
            '.a-price-whole',
            '.a-offscreen',
            '#price_inside_buybox',
            '.a-price .a-offscreen'
        ]
        
        for selector in price_selectors:
            price_element = product_soup.select_one(selector)
            if price_element:
                price = clean_price(price_element.get_text(strip=True))
                break
        
        # Rating
        rating_element = product_soup.find('span', class_='a-icon-alt')
        rating = clean_rating(rating_element.get_text(strip=True)) if rating_element else "N/A"
        
        # Review count
        review_element = product_soup.find('span', {'id': 'acrCustomerReviewText'})
        review_count = clean_review_count(review_element.get_text(strip=True)) if review_element else "N/A"
        
        return ProductInfo(
            website="Amazon.com",
            title=title[:100],  # Limit title length
            price=price,
            rating=rating,
            review_count=review_count,
            url=product_url
        )
        
    except Exception as e:
        print(f"Error scraping Amazon: {e}")
        return None

def scrape_bestbuy(product_name: str) -> Optional[ProductInfo]:
    """Scrape Best Buy for product information"""
    try:
        search_url = f"https://www.bestbuy.com/site/searchpage.jsp?st={urllib.parse.quote_plus(product_name)}"
        
        response = requests.get(search_url, headers=get_headers(), timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find first product
        product_item = soup.find('li', class_='sku-item')
        if not product_item:
            return None
        
        # Get product link
        link_element = product_item.find('a', class_='image-link')
        if not link_element:
            return None
        
        product_url = "https://www.bestbuy.com" + link_element.get('href', '')
        
        # Get product page
        time.sleep(1)
        product_response = requests.get(product_url, headers=get_headers(), timeout=10)
        product_response.raise_for_status()
        
        product_soup = BeautifulSoup(product_response.content, 'html.parser')
        
        # Extract information
        title_element = product_soup.find('h1', class_='heading-5')
        title = title_element.get_text(strip=True) if title_element else "N/A"
        
        # Price
        price_element = product_soup.find('span', class_='sr-only')
        price = clean_price(price_element.get_text(strip=True)) if price_element else "N/A"
        
        # Rating
        rating_element = product_soup.find('p', class_='visually-hidden')
        rating = clean_rating(rating_element.get_text(strip=True)) if rating_element else "N/A"
        
        # Review count
        review_element = product_soup.find('button', class_='c-button-unstyled')
        review_count = clean_review_count(review_element.get_text(strip=True)) if review_element else "N/A"
        
        return ProductInfo(
            website="BestBuy.com",
            title=title[:100],
            price=price,
            rating=rating,
            review_count=review_count,
            url=product_url
        )
        
    except Exception as e:
        print(f"Error scraping Best Buy: {e}")
        return None

def scrape_walmart(product_name: str) -> Optional[ProductInfo]:
    try:
        search_url = f"https://www.walmart.com/search?q={urllib.parse.quote_plus(product_name)}"
        
        response = requests.get(search_url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        product_link = soup.find('a', href=re.compile(r'/ip/'))
        if not product_link:
            return None
        
        product_url = "https://www.walmart.com" + product_link.get('href', '')
        
        time.sleep(1)
        product_response = requests.get(product_url, headers=get_headers(), timeout=10)
        product_response.raise_for_status()
        
        product_soup = BeautifulSoup(product_response.content, 'html.parser')
        
        title_element = product_soup.find('h1', {'itemprop': 'name'})
        title = title_element.get_text(strip=True) if title_element else "N/A"
        
        price = "N/A"
        price_element = product_soup.find('span', {'data-automation-id': 'price-display'})
        if not price_element:
            price_element = product_soup.find('span', class_='price-characteristic')
        if not price_element:
            price_element = product_soup.select_one('[itemprop="price"], .ProductPrice, .e1z8p20s4')
        
        if price_element:
            price = clean_price(price_element.get_text(strip=True))

        rating = "N/A"
        review_count = "N/A"
        
        rating_element = product_soup.find('span', class_='average-rating-stars') 
        if not rating_element:
            rating_element = product_soup.find('span', {'itemprop': 'ratingValue'})
        if rating_element:
            rating = clean_rating(rating_element.get_text(strip=True))
            
        review_count_element = product_soup.find('span', class_='Reviews-count')
        if not review_count_element:
            review_count_element = product_soup.find('span', {'itemprop': 'reviewCount'})
        if review_count_element:
            review_count = clean_review_count(review_count_element.get_text(strip=True))

        return ProductInfo(
            website="Walmart.com",
            title=title[:100],
            price=price,
            rating=rating,
            review_count=review_count,
            url=product_url
        )
        
    except Exception as e:
        print(f"Error scraping Walmart: {e}")
        return None
    
def scrape_newegg(product_name: str) -> Optional[ProductInfo]:
    try:
        search_url = f"https://www.newegg.com/p/pl?d={urllib.parse.quote_plus(product_name)}"
        
        response = requests.get(search_url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find first product
        product_item = soup.find('div', class_='item-container')
        if not product_item:
            return None
        
        # Get product link
        link_element = product_item.find('a', class_='item-title')
        if not link_element:
            return None
        
        product_url = link_element.get('href', '')
        if not product_url.startswith('http'):
            product_url = "https://www.newegg.com" + product_url
        
        title = link_element.get_text(strip=True)
        
        # Price from search results
        price_element = product_item.find('li', class_='price-current')
        price = clean_price(price_element.get_text(strip=True)) if price_element else "N/A"
        
        # Rating
        rating_element = product_item.find('span', class_='item-rating-num')
        rating = clean_rating(rating_element.get_text(strip=True)) if rating_element else "N/A"
        
        return ProductInfo(
            website="Newegg.com",
            title=title[:100],
            price=price,
            rating=rating,
            review_count="N/A",
            url=product_url
        )
        
    except Exception as e:
        print(f"Error scraping Newegg: {e}")
        return None

@app.post("/scrape")
async def scrape_products(request: ScrapeRequest):
    """Scrape products from multiple websites"""
    if request.scraping_method != "basic":
        raise HTTPException(status_code=400, detail="Only basic scraping is implemented")
    
    results = []
    scrapers = [
        ("Amazon", scrape_amazon),
        ("BestBuy", scrape_bestbuy),
        ("Walmart", scrape_walmart),
        ("Newegg", scrape_newegg)
    ]
    
    for name, scraper_func in scrapers:
        try:
            result = scraper_func(request.product_name)
            if result:
                results.append(result)
        except Exception as e:
            print(f"Error with {name}: {e}")
            continue
    
    if not results:
        raise HTTPException(status_code=404, detail="No products found")
    
    return {"results": results}

@app.get("/")
async def root():
    return {"message": "Basic Scraper API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)