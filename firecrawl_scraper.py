import urllib.parse
import asyncio
from firecrawl import AsyncFirecrawlApp, ScrapeOptions
from typing import List, Dict, Optional, Any
import os
import re
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class FirecrawlScraper:
    def __init__(self):
        # You need to set your Firecrawl API key as an environment variable
        # or replace "YOUR_API_KEY_HERE" with your actual API key
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "YOUR_API_KEY_HERE")
        
        if self.api_key == "YOUR_API_KEY_HERE":
            print("Warning: Firecrawl API key not configured. Please set FIRECRAWL_API_KEY environment variable.")

    def clean_extracted_data(self, data: Any) -> str:
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

    def format_price(self, price_data: Any) -> str:
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

    def format_rating(self, rating_data: Any) -> str:
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

    def format_review_count(self, review_data: Any) -> str:
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

    async def scrape_with_firecrawl_api(self, product_url: str, website_name: str) -> Optional[Dict]:
        """Scrape using Firecrawl API"""
        try:
            app_firecrawl = AsyncFirecrawlApp(api_key=self.api_key)
            
            # Create extraction schema
            schema = {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The name/title of the product"
                    },
                    "price": {
                        "type": "number",
                        "description": "The price of the product as a number"
                    },
                    "rating": {
                        "type": "number",
                        "description": "The average rating as a number"
                    },
                    "review_count": {
                        "type": "integer",
                        "description": "The number of reviews as an integer"
                    }
                }
            }
            
            # Create a more specific prompt for better extraction
            prompt = f"""
            Extract information about the first product from the {website_name} product page or search results.
            Look for the product name, price, rating, and review count.
            Focus on the most prominently displayed product.
            """
            
            response = await app_firecrawl.extract(
                urls=[product_url],
                prompt=prompt,
                schema=schema,
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
            title = self.clean_extracted_data(product_name) if product_name else "N/A"
            price = self.format_price(product_price)
            rating = self.format_rating(product_data.get('rating'))
            review_count = self.format_review_count(product_data.get('review_count'))
            
            return {
                "website": website_name,
                "title": title[:100],  # Limit title length
                "price": price,
                "rating": rating,
                "review_count": review_count,
                "url": product_url
            }
            
        except Exception as e:
            print(f"Error scraping {website_name} with Firecrawl: {e}")
            import traceback
            traceback.print_exc()  # Print full traceback for debugging
            return None

    async def scrape_amazon(self, product_name: str) -> Optional[Dict]:
        """Scrape Amazon using Firecrawl"""
        if self.api_key == "YOUR_API_KEY_HERE":
            print("Firecrawl API key not configured for Amazon scraping")
            return None
            
        search_url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(product_name)}"
        return await self.scrape_with_firecrawl_api(search_url, "Amazon.com")

    async def scrape_walmart(self, product_name: str) -> Optional[Dict]:
        """Scrape Walmart using Firecrawl"""
        if self.api_key == "YOUR_API_KEY_HERE":
            print("Firecrawl API key not configured for Walmart scraping")
            return None
            
        search_url = f"https://www.walmart.com/search?q={urllib.parse.quote_plus(product_name)}"
        return await self.scrape_with_firecrawl_api(search_url, "Walmart.com")

    async def scrape_newegg(self, product_name: str) -> Optional[Dict]:
        """Scrape Newegg by first getting search results, then scraping the first product page"""
        if self.api_key == "YOUR_API_KEY_HERE":
            print("Firecrawl API key not configured for Newegg scraping")
            return None
            
        try:
            app_firecrawl = AsyncFirecrawlApp(api_key=self.api_key)
            
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
            return await self.scrape_with_firecrawl_api(first_product_url, "Newegg.com")
            
        except Exception as e:
            print(f"Error scraping Newegg: {e}")
            return None

    async def scrape_all(self, product_name: str) -> List[Dict]:
        """
        Scrape all websites for the given product using Firecrawl
        Returns a list of dictionaries with product information
        """
        if self.api_key == "YOUR_API_KEY_HERE":
            print("Firecrawl API key not configured. Please set FIRECRAWL_API_KEY environment variable.")
            return []
            
        results = []
        scrapers = [
            ("Amazon", self.scrape_amazon),
            ("Walmart", self.scrape_walmart),
            ("Newegg", self.scrape_newegg)
        ]
        
        # Run scrapers in parallel using asyncio
        async def run_scraper(name, scraper_func):
            try:
                result = await scraper_func(product_name)
                return result
            except Exception as e:
                print(f"Error with {name}: {e}")
                return None
        
        # Create tasks for all scrapers
        tasks = [run_scraper(name, scraper_func) for name, scraper_func in scrapers]
        
        # Wait for all tasks to complete
        scraper_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in scraper_results:
            if isinstance(result, dict):  # Valid result
                results.append(result)
            elif isinstance(result, Exception):
                print(f"Scraper exception: {result}")
        
        return results