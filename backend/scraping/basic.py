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
        
        # New selectors based on provided HTML snippet
        reviews_ratings_div = product_soup.find('div', {'data-testid': 'reviews-and-ratings'})
        if reviews_ratings_div:
            # Look for the span containing "4.6 stars out of 287 reviews"
            rating_review_span = reviews_ratings_div.find('span', class_='w_iUH7')
            if rating_review_span:
                full_text = rating_review_span.get_text(strip=True)
                # Example: "4.6 stars out of 287 reviews"
                match = re.search(r'([\d.]+) stars out of (\d+) reviews', full_text)
                if match:
                    rating = clean_rating(match.group(1))
                    review_count = clean_review_count(match.group(2))
                else:
                    # Fallback to look for rating from text if direct match fails
                    rating_match = re.search(r'([\d.]+) stars', full_text)
                    if rating_match:
                        rating = clean_rating(rating_match.group(1))
            
            # Alternative/confirm review count from the <a> tag
            review_link_element = reviews_ratings_div.find('a', {'data-testid': 'item-review-section-link'})
            if review_link_element:
                review_text_from_link = review_link_element.get_text(strip=True)
                # Example: "287 ratings"
                review_count_match = re.search(r'(\d+)\s*ratings', review_text_from_link)
                if review_count_match:
                    # Prefer this if the span didn't give it or as a confirmation
                    review_count = clean_review_count(review_count_match.group(1))

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
        
        items = soup.select(".item-cell") 

        for item in items:
            title_tag = item.select_one(".item-title")
            price_whole = item.select_one(".price-current strong")
            price_fraction = item.select_one(".price-current sup")
            rating_tag = item.select_one(".item-rating")
            rating = rating_tag["title"] if rating_tag and "title" in rating_tag.attrs else "N/A"
            reviews_element = item.select_one(".item-rating-num")
            reviews = reviews_element.text.strip("()") if reviews_element else "N/A"

            product_url_relative = title_tag.get('href', '') if title_tag else ''
            if not product_url_relative.startswith('http'):
                product_url = "https://www.newegg.com" + product_url_relative
            else:
                product_url = product_url_relative

            if title_tag and price_whole and price_fraction:
                full_price_text = f"{price_whole.text.strip()}{price_fraction.text.strip()}"
                cleaned_price = clean_price(full_price_text)
                cleaned_rating = clean_rating(rating)
                cleaned_review_count = clean_review_count(reviews)

                return ProductInfo(
                    website="Newegg.com",
                    title=title_tag.text.strip()[:100],
                    price=cleaned_price,
                    rating=cleaned_rating,
                    review_count=cleaned_review_count,
                    url=product_url
                )
        
        return None

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