import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import re
from typing import List, Dict, Optional
import asyncio

class BasicScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def clean_price(self, price_text: str) -> str:
        if not price_text:
            return "N/A"
        price_text = re.sub(r'\s+', ' ', price_text.strip())
        price_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', price_text)
        if price_match:
            return f"${price_match.group(1)}"
        return price_text[:50]

    def clean_rating(self, rating_text: str) -> str:
        if not rating_text:
            return "N/A"
        rating_match = re.search(r'(\d+\.?\d*)\s*(?:out of|/|\s)*\s*\d*', rating_text)
        if rating_match:
            return rating_match.group(1)
        return rating_text[:10]

    def clean_review_count(self, review_text: str) -> str:
        if not review_text:
            return "N/A"
        review_match = re.search(r'([\d,]+)\s*(?:review|rating|customer)', review_text, re.IGNORECASE)
        if review_match:
            return review_match.group(1)
        number_match = re.search(r'([\d,]+)', review_text)
        if number_match:
            return number_match.group(1)
        return review_text[:20]

    def scrape_amazon(self, product_name: str) -> Optional[Dict]:
        try:
            search_url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(product_name)}"
            
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            product_container = soup.find('div', {'data-component-type': 's-search-result'})
            if not product_container:
                return None
            
            link_element = product_container.find('a', class_='a-link-normal')
            if not link_element:
                return None
            
            product_url = "https://www.amazon.com" + link_element.get('href', '')
            
            time.sleep(1)
            product_response = requests.get(product_url, headers=self.headers, timeout=10)
            product_response.raise_for_status()
            
            product_soup = BeautifulSoup(product_response.content, 'html.parser')
            
            title_element = product_soup.find('span', {'id': 'productTitle'})
            title = title_element.get_text(strip=True) if title_element else "N/A"
            
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
                    price = self.clean_price(price_element.get_text(strip=True))
                    break
            
            rating_element = product_soup.find('span', class_='a-icon-alt')
            rating = self.clean_rating(rating_element.get_text(strip=True)) if rating_element else "N/A"
            
            review_element = product_soup.find('span', {'id': 'acrCustomerReviewText'})
            review_count = self.clean_review_count(review_element.get_text(strip=True)) if review_element else "N/A"
            
            return {
                "website": "Amazon.com",
                "title": title[:100],
                "price": price,
                "rating": rating,
                "review_count": review_count,
                "url": product_url
            }
            
        except Exception as e:
            print(f"Error scraping Amazon: {e}")
            return None

    def scrape_walmart(self, product_name: str) -> Optional[Dict]:
        try:
            search_url = f"https://www.walmart.com/search?q={urllib.parse.quote_plus(product_name)}"
            
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            product_link = soup.find('a', href=re.compile(r'/ip/'))
            if not product_link:
                return None
            
            product_url = "https://www.walmart.com" + product_link.get('href', '')
            
            time.sleep(1)
            product_response = requests.get(product_url, headers=self.headers, timeout=10)
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
                price = self.clean_price(price_element.get_text(strip=True))

            rating = "N/A"
            review_count = "N/A"
            
            reviews_ratings_div = product_soup.find('div', {'data-testid': 'reviews-and-ratings'})
            if reviews_ratings_div:
                rating_review_span = reviews_ratings_div.find('span', class_='w_iUH7')
                if rating_review_span:
                    full_text = rating_review_span.get_text(strip=True)
                    match = re.search(r'([\d.]+) stars out of (\d+) reviews', full_text)
                    if match:
                        rating = self.clean_rating(match.group(1))
                        review_count = self.clean_review_count(match.group(2))
                    else:
                        rating_match = re.search(r'([\d.]+) stars', full_text)
                        if rating_match:
                            rating = self.clean_rating(rating_match.group(1))
                
                review_link_element = reviews_ratings_div.find('a', {'data-testid': 'item-review-section-link'})
                if review_link_element:
                    review_text_from_link = review_link_element.get_text(strip=True)
                    review_count_match = re.search(r'(\d+)\s*ratings', review_text_from_link)
                    if review_count_match:
                        review_count = self.clean_review_count(review_count_match.group(1))

            return {
                "website": "Walmart.com",
                "title": title[:100],
                "price": price,
                "rating": rating,
                "review_count": review_count,
                "url": product_url
            }
            
        except Exception as e:
            print(f"Error scraping Walmart: {e}")
            return None

    def scrape_newegg(self, product_name: str) -> Optional[Dict]:
        try:
            search_url = f"https://www.newegg.com/p/pl?d={urllib.parse.quote_plus(product_name)}"
            
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Newegg's product listings are often within elements with class 'item-cell' or similar.
            # We need to find the first relevant product.
            # Let's try to be more specific with our search for the first result container.
            first_product = soup.find('div', class_='item-cell')
            if not first_product:
                # Fallback to a broader search if 'item-cell' isn't found
                first_product = soup.find('div', class_=re.compile(r'item-container|list-item')) 
                if not first_product:
                    return None

            # Extract title
            title_tag = first_product.select_one(".item-title")
            title = title_tag.text.strip() if title_tag else "N/A"

            # Extract price
            price = "N/A"
            price_whole = first_product.select_one(".price-current strong")
            price_fraction = first_product.select_one(".price-current sup")
            
            if price_whole and price_fraction:
                full_price_text = f"{price_whole.text.strip()}{price_fraction.text.strip()}"
                price = self.clean_price(full_price_text)
            elif first_product.select_one(".price-current"): # Sometimes price is just in one element
                price = self.clean_price(first_product.select_one(".price-current").text.strip())

            # Extract rating
            rating = "N/A"
            rating_tag = first_product.select_one(".item-rating")
            if rating_tag and "title" in rating_tag.attrs:
                rating = self.clean_rating(rating_tag["title"])
            elif first_product.select_one(".rating-stars"): # Alternative for rating, looking for a common rating pattern
                rating_style = first_product.select_one(".rating-stars").get('style')
                if rating_style and 'width:' in rating_style:
                    # Example: width: 80% means 4 stars if max is 5
                    width_match = re.search(r'width:\s*(\d+)%', rating_style)
                    if width_match:
                        percentage = int(width_match.group(1))
                        rating = str(round((percentage / 100) * 5, 1)) # Convert percentage to 5-star scale

            # Extract review count
            reviews = "N/A"
            reviews_element = first_product.select_one(".item-rating-num")
            if reviews_element:
                reviews = self.clean_review_count(reviews_element.text.strip("()"))
            elif first_product.select_one(".item-rating ~ span"): # Sometimes review count is a sibling
                reviews = self.clean_review_count(first_product.select_one(".item-rating ~ span").text.strip())

            # Get product URL
            product_url_relative = title_tag.get('href', '') if title_tag else ''
            if not product_url_relative.startswith('http'):
                product_url = "https://www.newegg.com" + product_url_relative
            else:
                product_url = product_url_relative

            if title != "N/A" and price != "N/A": # Ensure we got at least title and price
                return {
                    "website": "Newegg.com",
                    "title": title[:100],
                    "price": price,
                    "rating": rating,
                    "review_count": reviews,
                    "url": product_url
                }
            
            return None

        except Exception as e:
            print(f"Error scraping Newegg: {e}")
            return None

    async def scrape_all(self, product_name: str) -> List[Dict]:
        results = []
        scrapers = [
            ("Amazon", self.scrape_amazon),
            ("Walmart", self.scrape_walmart),
            ("Newegg", self.scrape_newegg)
        ]
        
        async def run_scraper(name, scraper_func):
            try:
                result = await asyncio.to_thread(scraper_func, product_name)
                return result
            except Exception as e:
                print(f"Error with {name} scraper: {e}")
                return None
        
        tasks = [run_scraper(name, scraper_func) for name, scraper_func in scrapers]
        
        scraper_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in scraper_results:
            if isinstance(result, dict):
                results.append(result)
            elif isinstance(result, Exception):
                print(f"An exception occurred during scraping: {result}")
        
        return results