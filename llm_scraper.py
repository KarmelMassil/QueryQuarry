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
import asyncio

class LLMScraper:
    def __init__(self):
        load_dotenv()
        
        # Initialize Gemini client
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def extract_with_llm(self, html_content: str, website_name: str, product_url: str) -> Optional[Dict]:
        """Use Gemini to extract product information from HTML"""
        try:
            # Truncate HTML to avoid token limits (keep first 30000 characters for Gemini)
            truncated_html = html_content[:30000] if len(html_content) > 30000 else html_content
            
            prompt = f"""
            You are a highly accurate web scraper assistant. Your goal is to extract product information from the provided HTML content from {website_name}.
            
            Carefully examine the HTML and find the following four pieces of information. Be precise and return "N/A" if any piece of information is genuinely not found.
            
            1. Product title/name: Look for the main product title, often in a large heading (e.g., H1) or a prominent span with id like 'productTitle'.
            2. Price: Find the current selling price. It will typically be formatted as a dollar amount (e.g., $123.45). Look for classes containing 'price', 'cost', or spans with price information. Extract the full number, including cents if present.
            3. Average rating: Look for the star rating, usually a number out of 5 (e.g., 4.2). Often found in spans with 'rating' or 'star' in the class name.
            4. Review count: Find the total number of customer reviews or ratings, usually followed by "reviews" or "ratings". Look for spans or links containing review counts.
            
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
            
            response = self.model.generate_content(
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
            
            return {
                "website": website_name,
                "title": extracted_data.get("title", "N/A")[:100],
                "price": extracted_data.get("price", "N/A"),
                "rating": extracted_data.get("rating", "N/A"),
                "review_count": extracted_data.get("review_count", "N/A"),
                "url": product_url
            }
            
        except Exception as e:
            print(f"Error with Gemini extraction: {e}")
            return None

    def scrape_amazon(self, product_name: str) -> Optional[Dict]:
        """Scrape Amazon using LLM to extract from search results page directly"""
        try:
            search_url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(product_name)}"
            print(f"Searching Amazon: {search_url}")
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the first product result container (same as basic scraper)
            product_container = soup.find('div', {'data-component-type': 's-search-result'})
            if not product_container:
                print("No product container found on Amazon search page")
                return None
            
            # Convert just the first product container to HTML string for LLM
            product_html = str(product_container)
            print(f"Found Amazon product container, sending to LLM")
            
            # Extract product URL for reference
            link_element = product_container.find('a', class_='a-link-normal')
            product_url = search_url  # Default fallback
            if link_element:
                href = link_element.get('href', '')
                if href:
                    product_url = "https://www.amazon.com" + href
            
            # Use LLM to extract information from the product container HTML
            return self.extract_from_search_container(product_html, "Amazon.com", product_url)
            
        except Exception as e:
            print(f"Error scraping Amazon with LLM: {e}")
            return None

    def extract_from_search_container(self, container_html: str, website_name: str, product_url: str) -> Optional[Dict]:
        """Use Gemini to extract product information from a single search result container"""
        try:
            prompt = f"""
            You are extracting product information from a single search result container from {website_name}.
            
            This HTML represents ONE product from search results. Extract these 4 pieces of information:
            
            1. TITLE: Product name/title
            - Look for <h2> tags or spans with product titles
            - Often in elements with classes like "s-title-text" or similar
            - Get the full product name
            
            2. PRICE: Current price
            - Look for price information in spans or divs
            - May be in elements with "price" in the class name
            - Format as $XX.XX if possible
            - Sometimes split between dollars and cents
            
            3. RATING: Star rating (e.g., 4.2 out of 5)
            - Look for rating information, often in spans with "a-icon-alt"
            - May contain text like "4.2 out of 5 stars"
            - Extract just the number
            
            4. REVIEW COUNT: Number of reviews/ratings
            - Look for review counts, often in parentheses or links
            - May be near rating information
            - Extract just the number
            
            HTML Container:
            {container_html}
            
            Return ONLY this JSON:
            {{
                "title": "product title",
                "price": "$XX.XX",
                "rating": "X.X", 
                "review_count": "XXXX"
            }}
            
            Use "N/A" if any information is not found. No explanations.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=500,
                )
            )
            
            llm_response = response.text.strip()
            print(f"LLM Response: {llm_response}")
            
            # Clean the response
            if llm_response.startswith('```json'):
                llm_response = llm_response.replace('```json', '').replace('```', '').strip()
            elif llm_response.startswith('```'):
                llm_response = llm_response.replace('```', '').strip()
            
            # Parse JSON
            try:
                extracted_data = json.loads(llm_response)
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Raw LLM response: {llm_response}")
                return None
            
            return {
                "website": website_name,
                "title": extracted_data.get("title", "N/A")[:100],
                "price": extracted_data.get("price", "N/A"),
                "rating": extracted_data.get("rating", "N/A"),
                "review_count": extracted_data.get("review_count", "N/A"),
                "url": product_url
            }
            
        except Exception as e:
            print(f"Error with Gemini extraction: {e}")
            return None

    def scrape_walmart(self, product_name: str) -> Optional[Dict]:
        """Scrape Walmart using LLM for data extraction from search results"""
        try:
            search_url = f"https://www.walmart.com/search?q={urllib.parse.quote_plus(product_name)}"
            print(f"Searching Walmart: {search_url}")
            
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find first product link (similar to basic scraper)
            product_link = soup.find('a', href=re.compile(r'/ip/'))
            if not product_link:
                print("No product link found on Walmart search page")
                return None
            
            product_url = "https://www.walmart.com" + product_link.get('href', '')
            print(f"Found Walmart product URL: {product_url}")
            
            time.sleep(2)  # Increased delay for Walmart
            product_response = requests.get(product_url, headers=self.headers, timeout=15)
            product_response.raise_for_status()
            
            # Use improved LLM extraction for Walmart
            return self.extract_with_llm_walmart(product_response.text, "Walmart.com", product_url)
            
        except Exception as e:
            print(f"Error scraping Walmart with LLM: {e}")
            return None

    def extract_with_llm_walmart(self, html_content: str, website_name: str, product_url: str) -> Optional[Dict]:
        """Extract Walmart product info using LLM with improved price detection"""
        try:
            # Use more HTML content for Walmart since price might be deeper in the page
            truncated_html = html_content[:40000] if len(html_content) > 40000 else html_content
            
            prompt = f"""
            Extract product information from this Walmart product page HTML. Walmart prices can be tricky to find.
            
            IMPORTANT - For PRICE specifically, look for these patterns:
            - Spans or divs with classes containing "price", "cost", "amount"
            - Elements with data attributes like data-automation-id="product-price"
            - Price information in <span> tags with dollar signs
            - Current/sale prices (not original/crossed-out prices)
            - Prices in formats like $XX.XX, $X.XX, or even just numbers with $ symbols
            - Look in multiple sections - header, main content, sidebar
            - Check for both integer and decimal prices (some show $25, others $25.99)
            
            For other fields:
            1. TITLE: Main product name (often in <h1> with itemprop="name" or data-automation-id)
            2. RATING: Star rating number (look for rating spans, may be in format like "4.5 out of 5")
            3. REVIEW COUNT: Number of reviews/ratings (often in parentheses or separate spans)
            
            HTML Content:
            {truncated_html}
            
            Return this exact JSON format:
            {{
                "title": "exact product title",
                "price": "$XX.XX",
                "rating": "X.X",
                "review_count": "XXXX"
            }}
            
            CRITICAL: If you find ANY price information (even partial), include it. Use "N/A" only if absolutely no price data exists.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=600,
                )
            )
            
            llm_response = response.text.strip()
            print(f"Walmart LLM Response: {llm_response}")
            
            # Clean the response
            if llm_response.startswith('```'):
                llm_response = re.sub(r'```(?:json)?', '', llm_response).strip()
            
            try:
                extracted_data = json.loads(llm_response)
            except json.JSONDecodeError as e:
                print(f"Walmart JSON decode error: {e}")
                print(f"Raw response: {llm_response}")
                return None
            
            result = {
                "website": website_name,
                "title": extracted_data.get("title", "N/A")[:100],
                "price": extracted_data.get("price", "N/A"),
                "rating": extracted_data.get("rating", "N/A"),
                "review_count": extracted_data.get("review_count", "N/A"),
                "url": product_url
            }
            
            print(f"Walmart extraction result: {result}")
            return result
            
        except Exception as e:
            print(f"Error with Walmart LLM extraction: {e}")
            return None

    def scrape_newegg(self, product_name: str) -> Optional[Dict]:
        """Scrape Newegg using LLM for data extraction from search results"""
        try:
            search_url = f"https://www.newegg.com/p/pl?d={urllib.parse.quote_plus(product_name)}"
            print(f"Searching Newegg: {search_url}")
            
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find first product (similar to basic scraper)
            first_product = soup.find('div', class_='item-cell')
            if not first_product:
                first_product = soup.find('div', class_=re.compile(r'item-container|list-item'))
                if not first_product:
                    print("No product found on Newegg search page")
                    return None
            
            # Get product URL for reference
            title_tag = first_product.select_one(".item-title")
            product_url = search_url  # Default fallback
            if title_tag:
                href = title_tag.get('href', '')
                if href:
                    if not href.startswith('http'):
                        product_url = "https://www.newegg.com" + href
                    else:
                        product_url = href
            
            # Convert product container to HTML for LLM
            product_html = str(first_product)
            print(f"Found Newegg product container, sending to LLM")
            
            return self.extract_from_search_container(product_html, "Newegg.com", product_url)
            
        except Exception as e:
            print(f"Error scraping Newegg with LLM: {e}")
            return None

    async def scrape_with_llm(self, product_name: str) -> List[Dict]:
        """
        Scrape all websites using LLM for the given product
        Returns a list of dictionaries with product information
        """
        results = []
        scrapers = [
            ("Amazon", self.scrape_amazon),
            ("Walmart", self.scrape_walmart),
            ("Newegg", self.scrape_newegg)
        ]
        
        # Run scrapers in parallel using asyncio
        async def run_scraper(name, scraper_func):
            try:
                # Run the synchronous scraper in a thread pool
                result = await asyncio.to_thread(scraper_func, product_name)
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

    # Debug method to help troubleshoot Walmart price extraction
    def debug_walmart_price(self, product_name: str):
        """Debug method to see what HTML content is being sent to LLM for Walmart"""
        try:
            search_url = f"https://www.walmart.com/search?q={urllib.parse.quote_plus(product_name)}"
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            product_link = soup.find('a', href=re.compile(r'/ip/'))
            
            if product_link:
                product_url = "https://www.walmart.com" + product_link.get('href', '')
                time.sleep(2)
                product_response = requests.get(product_url, headers=self.headers, timeout=15)
                product_response.raise_for_status()
                
                # Save a portion of the HTML to see what we're working with
                html_sample = product_response.text[:5000]
                print("=== WALMART HTML SAMPLE (first 5000 chars) ===")
                print(html_sample)
                print("=== END SAMPLE ===")
                
                # Look for price-related elements manually
                soup = BeautifulSoup(product_response.content, 'html.parser')
                price_elements = soup.find_all(text=re.compile(r'\$\d+'))
                print(f"\nFound {len(price_elements)} potential price elements:")
                for i, elem in enumerate(price_elements[:10]):  # Show first 10
                    print(f"{i+1}: {elem.strip()}")
                    
        except Exception as e:
            print(f"Debug error: {e}")