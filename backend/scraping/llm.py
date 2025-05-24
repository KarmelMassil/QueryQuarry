from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import re
import json
from typing import List, Dict, Optional
import google.generativeai as genai
import os
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini client
# Make sure to set your API key as an environment variable: GEMINI_API_KEY
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

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

def extract_with_llm(html_content: str, website_name: str, product_url: str) -> Optional[ProductInfo]:
    """Use Gemini to extract product information from HTML"""
    try:
        # Truncate HTML to avoid token limits (keep first 20000 characters for Gemini)
        truncated_html = html_content[:20000] if len(html_content) > 20000 else html_content
        
        prompt = f"""
        You are a web scraper assistant. Extract product information from the following HTML content from {website_name}.
        
        I need you to find and extract EXACTLY these 4 pieces of information:
        1. Product title/name
        2. Price (in USD, format as $XX.XX)
        3. Average rating (number out of 5, like 4.5)
        4. Review count (number of reviews/ratings)
        
        HTML Content:
        {truncated_html}
        
        Please respond with ONLY a valid JSON object in this exact format:
        {{
            "title": "product title here",
            "price": "$XX.XX",
            "rating": "X.X",
            "review_count": "XXX"
        }}
        
        If any information is not found, use "N/A" as the value.
        Do not include any explanations or additional text, just the JSON.
        """
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=500,
            )
        )
        
        llm_response = response.text.strip()
        
        # Clean the response to ensure it's valid JSON
        # Remove any markdown formatting if present
        if llm_response.startswith('```json'):
            llm_response = llm_response.replace('```json', '').replace('```', '').strip()
        elif llm_response.startswith('```'):
            llm_response = llm_response.replace('```', '').strip()
        
        # Parse the JSON response
        try:
            extracted_data = json.loads(llm_response)
        except json.JSONDecodeError:
            print(f"Invalid JSON from Gemini: {llm_response}")
            return None
        
        return ProductInfo(
            website=website_name,
            title=extracted_data.get("title", "N/A")[:100],
            price=extracted_data.get("price", "N/A"),
            rating=extracted_data.get("rating", "N/A"),
            review_count=extracted_data.get("review_count", "N/A"),
            url=product_url
        )
        
    except Exception as e:
        print(f"Error with Gemini extraction: {e}")
        return None

def scrape_amazon_llm(product_name: str) -> Optional[ProductInfo]:
    """Scrape Amazon using LLM for data extraction"""
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
        
        # Use LLM to extract information
        return extract_with_llm(product_response.text, "Amazon.com", product_url)
        
    except Exception as e:
        print(f"Error scraping Amazon with LLM: {e}")
        return None

def scrape_walmart_llm(product_name: str) -> Optional[ProductInfo]:
    """Scrape Walmart using LLM for data extraction"""
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
        
        # Use LLM to extract information
        return extract_with_llm(product_response.text, "Walmart.com", product_url)
        
    except Exception as e:
        print(f"Error scraping Walmart with LLM: {e}")
        return None

def scrape_newegg_llm(product_name: str) -> Optional[ProductInfo]:
    """Scrape Newegg using LLM for data extraction"""
    try:
        search_url = f"https://www.newegg.com/p/pl?d={urllib.parse.quote_plus(product_name)}"
        
        response = requests.get(search_url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find first product item
        first_item = soup.select_one(".item-cell")
        if not first_item:
            return None
        
        # Get product link
        title_tag = first_item.select_one(".item-title")
        if not title_tag:
            return None
        
        product_url_relative = title_tag.get('href', '')
        if not product_url_relative.startswith('http'):
            product_url = "https://www.newegg.com" + product_url_relative
        else:
            product_url = product_url_relative
        
        time.sleep(1)
        product_response = requests.get(product_url, headers=get_headers(), timeout=10)
        product_response.raise_for_status()
        
        # Use LLM to extract information
        return extract_with_llm(product_response.text, "Newegg.com", product_url)
        
    except Exception as e:
        print(f"Error scraping Newegg with LLM: {e}")
        return None

def scrape_bestbuy_llm(product_name: str) -> Optional[ProductInfo]:
    """Scrape Best Buy using LLM for data extraction"""
    try:
        search_url = f"https://www.bestbuy.com/site/searchpage.jsp?st={urllib.parse.quote_plus(product_name)}"
        
        response = requests.get(search_url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find first product link
        product_link = soup.find('a', class_='image-link')
        if not product_link:
            # Try alternative selector
            product_link = soup.select_one('a[href*="/site/"]')
        
        if not product_link:
            return None
        
        product_url = product_link.get('href', '')
        if not product_url.startswith('http'):
            product_url = "https://www.bestbuy.com" + product_url
        
        time.sleep(1)
        product_response = requests.get(product_url, headers=get_headers(), timeout=10)
        product_response.raise_for_status()
        
        # Use LLM to extract information
        return extract_with_llm(product_response.text, "BestBuy.com", product_url)
        
    except Exception as e:
        print(f"Error scraping Best Buy with LLM: {e}")
        return None

@app.post("/scrape")
async def scrape_products(request: ScrapeRequest):
    """Scrape products from multiple websites using LLM"""
    if request.scraping_method not in ["llm", "basic"]:
        raise HTTPException(status_code=400, detail="Only 'llm' and 'basic' scraping methods are supported")
    
    if request.scraping_method == "llm":
        # Check if API key is set
        if not os.getenv("GEMINI_API_KEY"):
            raise HTTPException(
                status_code=500, 
                detail="Gemini API key not set. Please set GEMINI_API_KEY environment variable."
            )
        
        results = []
        scrapers = [
            ("Amazon", scrape_amazon_llm),
            ("Walmart", scrape_walmart_llm),
            ("Newegg", scrape_newegg_llm),
            ("BestBuy", scrape_bestbuy_llm)
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
    
    else:
        # Fallback to basic scraping (you can import from basic.py or implement here)
        raise HTTPException(status_code=400, detail="Basic scraping not implemented in this file")

@app.get("/")
async def root():
    return {"message": "LLM Scraper API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    api_key_status = "Set" if os.getenv("GEMINI_API_KEY") else "Not Set"
    return {
        "status": "healthy",
        "gemini_api_key": api_key_status,
        "supported_methods": ["llm"],
        "supported_websites": ["Amazon.com", "Walmart.com", "Newegg.com", "BestBuy.com"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Different port from basic scraper