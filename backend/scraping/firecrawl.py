from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import urllib.parse
import asyncio
from firecrawl import AsyncFirecrawlApp, ScrapeOptions
from typing import List, Dict, Optional, Any
import os
import re
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()  # Load environment variables from .env file

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

class ProductExtractSchema(BaseModel):
    product_name: str = Field(description="The name/title of the product")
    price: Optional[float] = Field(description="The price of the product as a number")
    rating: Optional[float] = Field(description="The average rating as a number")
    review_count: Optional[int] = Field(description="The number of reviews as an integer")

# You need to set your Firecrawl API key as an environment variable
# or replace "YOUR_API_KEY_HERE" with your actual API key
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "YOUR_API_KEY_HERE")

def clean_extracted_data(data: Any) -> str:
    """Clean and format extracted data"""
    if data is None:
        return "N/A"
    
    if isinstance(data, (int, float)):
        return str(data)
    
    if isinstance(data, str):
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', data.strip())
        return cleaned if cleaned else "N/A"
    
    return str(data)

def format_price(price_data: Any) -> str:
    """Format price data"""
    if price_data is None:
        return "N/A"
    
    if isinstance(price_data, (int, float)):
        return f"${price_data:.2f}"
    
    if isinstance(price_data, str):
        # Look for price patterns
        price_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', price_data)
        if price_match:
            return f"${price_match.group(1)}"
        return price_data[:50]
    
    return str(price_data)

def format_rating(rating_data: Any) -> str:
    """Format rating data"""
    if rating_data is None:
        return "N/A"
    
    if isinstance(rating_data, (int, float)):
        return str(rating_data)
    
    if isinstance(rating_data, str):
        # Look for rating patterns
        rating_match = re.search(r'(\d+\.?\d*)', rating_data)
        if rating_match:
            return rating_match.group(1)
        return rating_data[:10]
    
    return str(rating_data)

def format_review_count(review_data: Any) -> str:
    """Format review count data"""
    if review_data is None:
        return "N/A"
    
    if isinstance(review_data, (int, float)):
        return str(int(review_data))
    
    if isinstance(review_data, str):
        # Look for numbers
        review_match = re.search(r'([\d,]+)', review_data)
        if review_match:
            return review_match.group(1)
        return review_data[:20]
    
    return str(review_data)

async def scrape_with_firecrawl(product_url: str, website_name: str) -> Optional[ProductInfo]:
    """Scrape using Firecrawl API"""
    try:
        app_firecrawl = AsyncFirecrawlApp(api_key=FIRECRAWL_API_KEY)
        
        # Create a more specific prompt for better extraction
        prompt = f"""
        Extract information about first product from the {website_name} product page.
        Look for the product name, price, rating, and review count.
        """
        
        response = await app_firecrawl.extract(
            urls=[product_url],
            prompt=prompt,
            schema=ProductExtractSchema.model_json_schema(),
            agent={"model": "FIRE-1"}
        )
        
        print(f"Firecrawl response for {website_name}: {response}")  # Debug logging
        
        # Handle the ExtractResponse object properly
        if not response or not hasattr(response, 'data') or not response.data:
            print(f"No data in response for {website_name}")
            return None
        
        # The data field contains the extracted information directly as a dictionary
        product_data = response.data
        
        if not product_data:
            print(f"No product data extracted for {website_name}")
            return None
        
        # Check if we have meaningful data (at least product name or price)
        product_name = product_data.get('product_name', '')
        product_price = product_data.get('price')
        
        if not product_name and not product_price:
            print(f"No meaningful product data found for {website_name}")
            return None
        
        # Extract and clean the data
        title = clean_extracted_data(product_name) if product_name else "N/A"
        price = format_price(product_price)
        rating = format_rating(product_data.get('rating'))
        review_count = format_review_count(product_data.get('review_count'))
        
        return ProductInfo(
            website=website_name,
            title=title[:100],  # Limit title length
            price=price,
            rating=rating,
            review_count=review_count,
            url=product_url
        )
        
    except Exception as e:
        print(f"Error scraping {website_name} with Firecrawl: {e}")
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
        return None

async def scrape_amazon_firecrawl(product_name: str) -> Optional[ProductInfo]:
    """Scrape Amazon using Firecrawl"""
    search_url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(product_name)}"
    return await scrape_with_firecrawl(search_url, "Amazon.com")

async def scrape_walmart_firecrawl(product_name: str) -> Optional[ProductInfo]:
    """Scrape Walmart using Firecrawl"""
    search_url = f"https://www.walmart.com/search?q={urllib.parse.quote_plus(product_name)}"
    return await scrape_with_firecrawl(search_url, "Walmart.com")

async def scrape_newegg_firecrawl(product_name: str) -> Optional[ProductInfo]:
    """Scrape Newegg by first getting search results, then scraping the first product page"""
    app_firecrawl = AsyncFirecrawlApp(api_key=FIRECRAWL_API_KEY)
        
        # First, crawl the search results to get all links
    search_url = f"https://www.newegg.com/p/pl?d={urllib.parse.quote_plus(product_name)}"
        
        # Crawl search results to extract links
    search_response = await app_firecrawl.crawl_url(
        url=search_url,
        limit=1,
        scrape_options=ScrapeOptions(
            formats=['links'],
            onlyMainContent=True,
            proxy="stealth"
        )
    )
        
    print(f"Newegg search response: {search_response}")  # Debug logging
        
        # Extract links from the response
    if not search_response or not hasattr(search_response, 'data') or not search_response.data:
        print("No search results data from Newegg")
        return None
        
    # Get the links array from the response
    links = []
    if len(search_response.data) > 0 and hasattr(search_response.data[0], 'links'):
        links = search_response.data[0].links
        print(f"Successfully extracted {len(links)} links from response")
        
    if not links:
        print("No links found in Newegg search results")
        return None
        
    print(f"Found {len(links)} links")
        
        # Filter for actual product URLs
        # Newegg product URLs typically contain "/p/" and have product codes like "N82E16826197551"
    product_urls = []
    for link in links:
        if isinstance(link, str):
            # Look for product URLs that match Newegg's pattern
            if ('/p/N82E' in link or '/p/0TP-' in link or '/p/32K-' in link or '/p/173-' in link) and '#' not in link and '?' not in link:
                product_urls.append(link)
        
    if not product_urls:
        print("No product URLs found in Newegg links")
        print(f"All links: {links[:10]}")  # Print first 10 links for debugging
        return None
        
    # Get the first product URL
    first_product_url = product_urls[0]
    print(f"Found first product URL: {first_product_url}")
        
    # Now scrape the specific product page
    return await scrape_with_firecrawl(first_product_url, "Newegg.com")
        

@app.post("/scrape")
async def scrape_products(request: ScrapeRequest):
    """Scrape products from multiple websites using Firecrawl"""
    if request.scraping_method != "firecrawl":
        raise HTTPException(status_code=400, detail="Only Firecrawl scraping is implemented in this version")
    
    # Check if API key is set
    if FIRECRAWL_API_KEY == "YOUR_API_KEY_HERE":
        raise HTTPException(
            status_code=400, 
            detail="Firecrawl API key not configured. Please set FIRECRAWL_API_KEY environment variable."
        )
    
    results = []
    
    # Only testing Newegg for now
    scrapers = [
        ("Amazon", scrape_amazon_firecrawl),
        ("Walmart", scrape_walmart_firecrawl),
        ("Newegg", scrape_newegg_firecrawl)
    ]
    
    # Run scrapers concurrently for better performance
    tasks = []
    for name, scraper_func in scrapers:
        tasks.append(scraper_func(request.product_name))
    
    # Wait for all scrapers to complete
    scraper_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for i, result in enumerate(scraper_results):
        if isinstance(result, Exception):
            print(f"Error with {scrapers[i][0]}: {result}")
            continue
        
        if result:
            results.append(result)
    
    if not results:
        raise HTTPException(status_code=404, detail="No products found")
    
    return {"results": results}

@app.get("/")
async def root():
    return {"message": "Firecrawl Scraper API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    api_key_status = "configured" if FIRECRAWL_API_KEY != "YOUR_API_KEY_HERE" else "not configured"
    return {
        "status": "healthy",
        "firecrawl_api_key": api_key_status
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Different port to avoid conflict with basic.py