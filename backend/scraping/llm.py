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
import os
from dotenv import load_dotenv
import httpx # Import httpx for async HTTP requests

import google.generativeai as genai


load_dotenv() # Load environment variables from .env file

app = FastAPI()

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
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

def clean_price(price_text: str) -> str:
    if not price_text:
        return "N/A"
    price_text = re.sub(r'\s+', ' ', price_text.strip())
    price_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', price_text)
    if price_match:
        return f"${price_match.group(1)}"
    return price_text[:50]

def clean_rating(rating_text: str) -> str:
    if not rating_text:
        return "N/A"
    rating_match = re.search(r'(\d+\.?\d*)\s*(?:out of|/|\s)*\s*\d*', rating_text)
    if rating_match:
        return rating_match.group(1)
    return rating_text[:10]

def clean_review_count(review_text: str) -> str:
    if not review_text:
        return "N/A"
    review_match = re.search(r'([\d,]+)\s*(?:review|rating|customer)', review_text, re.IGNORECASE)
    if review_match:
        return review_match.group(1)
    number_match = re.search(r'([\d,]+)', review_text)
    if number_match:
        return number_match.group(1)
    return review_text[:20]

async def extract_with_llm(html_content: str, website_name: str, product_url: str) -> Optional[ProductInfo]:
    try:
        truncated_html = html_content[:15000] if len(html_content) > 15000 else html_content
        
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
        
        chat_history = []
        chat_history.append({"role": "user", "parts": [{"text": prompt}]})
        payload = {
            "contents": chat_history,
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "price": {"type": "STRING"},
                        "rating": {"type": "STRING"},
                        "review_count": {"type": "STRING"}
                    },
                    "propertyOrdering": ["title", "price", "rating", "review_count"]
                }
            }
        }
        
        apiKey = os.getenv("Gemini_API_KEY")
        if not apiKey:
            raise ValueError("Gemini_API_KEY environment variable not set.")
            
        apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={apiKey}"
        
        async with httpx.AsyncClient() as client: # Use httpx.AsyncClient for async requests
            response = await client.post(
                apiUrl,
                headers={'Content-Type': 'application/json'},
                json=payload # Use json=payload for dict, not data=json.dumps(payload)
            )
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("candidates") and result["candidates"][0].get("content") and result["candidates"][0]["content"].get("parts"):
            llm_response_json_str = result["candidates"][0]["content"]["parts"][0]["text"]
            extracted_data = json.loads(llm_response_json_str)
        else:
            print(f"Unexpected Gemini API response structure: {result}")
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
        print(f"Error with LLM extraction: {e}")
        return None

async def scrape_amazon_llm(product_name: str) -> Optional[ProductInfo]: # Made async
    try:
        search_url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(product_name)}"
        
        async with httpx.AsyncClient() as client: # Use httpx.AsyncClient
            response = await client.get(search_url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        product_container = soup.find('div', {'data-component-type': 's-search-result'})
        if not product_container:
            return None
        
        link_element = product_container.find('a', class_='a-link-normal')
        if not link_element:
            return None
        
        product_url_relative = link_element.get('href', '')
        product_url = urllib.parse.urljoin("https://www.amazon.com", product_url_relative) # Use urljoin
        
        time.sleep(1) # Keep time.sleep as it's for politeness, not directly async issue
        async with httpx.AsyncClient() as client: # Use httpx.AsyncClient
            product_response = await client.get(product_url, headers=get_headers(), timeout=10)
        product_response.raise_for_status()
        
        return await extract_with_llm(product_response.text, "Amazon.com", product_url)
        
    except Exception as e:
        print(f"Error scraping Amazon with LLM: {e}")
        return None

async def scrape_walmart_llm(product_name: str) -> Optional[ProductInfo]: # Made async
    try:
        search_url = f"https://www.walmart.com/search?q={urllib.parse.quote_plus(product_name)}"
        
        async with httpx.AsyncClient() as client: # Use httpx.AsyncClient
            response = await client.get(search_url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        product_link = soup.find('a', href=re.compile(r'/ip/'))
        if not product_link:
            return None
        
        product_url_relative = product_link.get('href', '')
        product_url = urllib.parse.urljoin("https://www.walmart.com", product_url_relative) # Use urljoin
        
        time.sleep(1)
        async with httpx.AsyncClient() as client: # Use httpx.AsyncClient
            product_response = await client.get(product_url, headers=get_headers(), timeout=10)
        product_response.raise_for_status()
        
        return await extract_with_llm(product_response.text, "Walmart.com", product_url)
        
    except Exception as e:
        print(f"Error scraping Walmart with LLM: {e}")
        return None

async def scrape_newegg_llm(product_name: str) -> Optional[ProductInfo]: # Made async
    try:
        search_url = f"https://www.newegg.com/p/pl?d={urllib.parse.quote_plus(product_name)}"
        
        async with httpx.AsyncClient() as client: # Use httpx.AsyncClient
            response = await client.get(search_url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        first_item = soup.select_one(".item-cell")
        if not first_item:
            return None
        
        title_tag = first_item.select_one(".item-title")
        if not title_tag:
            return None
        
        product_url_relative = title_tag.get('href', '')
        product_url = urllib.parse.urljoin("https://www.newegg.com", product_url_relative) # Use urljoin
        
        time.sleep(1)
        async with httpx.AsyncClient() as client: # Use httpx.AsyncClient
            product_response = await client.get(product_url, headers=get_headers(), timeout=10)
        product_response.raise_for_status()
        
        return await extract_with_llm(product_response.text, "Newegg.com", product_url)
        
    except Exception as e:
        print(f"Error scraping Newegg with LLM: {e}")
        return None

@app.post("/scrape")
async def scrape_products(request: ScrapeRequest):
    if request.scraping_method not in ["llm", "basic"]:
        raise HTTPException(status_code=400, detail="Only 'llm' and 'basic' scraping methods are supported")
        
    results = []

    if request.scraping_method == "llm":
        
        if not os.getenv("Gemini_API_KEY"):
            raise HTTPException(
                status_code=500,
                detail="Gemini_API_KEY environment variable not set. Please set it in your .env file."
            )

        scrapers = [
            ("Amazon", scrape_amazon_llm),
            ("Walmart", scrape_walmart_llm),
            ("Newegg", scrape_newegg_llm)
        ]
        
        for name, scraper_func in scrapers:
            try:
                result = await scraper_func(request.product_name)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"Error with {name} (LLM scraping): {e}")
                continue
        
        if not results:
            raise HTTPException(status_code=404, detail="No products found using LLM scraping.")
        
        return {"results": results}
        
    else:
        raise HTTPException(status_code=400, detail="Basic scraping not implemented in this file. Please integrate your basic scraping functions if you want to use this method.")

@app.get("/")
async def root():
    return {"message": "LLM Scraper API is running"}

@app.get("/health")
async def health_check():
    gemini_api_key_status = "Set" if os.getenv("Gemini_API_KEY") else "Not Set"
    return {
        "status": "healthy",
        "gemini_api_key_status": gemini_api_key_status,
        "supported_methods": ["llm"],
        "supported_websites": ["Amazon.com", "Walmart.com", "Newegg.com"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)