# Fixed main.py - correcting method calls
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio

# Import your existing scrapers
from basic_scraper import BasicScraper
from llm_scraper import LLMScraper
from firecrawl_scraper import FirecrawlScraper

app = FastAPI(title="Product Scraper API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class ScrapeRequest(BaseModel):
    product_name: str
    scraping_method: str = "basic"

class ProductResult(BaseModel):
    website: str
    title: str
    price: str
    rating: str
    review_count: str
    url: str

class ScrapeResponse(BaseModel):
    results: List[ProductResult]
    method_used: str
    total_found: int

# Initialize scrapers
basic_scraper = BasicScraper()

# Initialize LLM scraper with error handling
try:
    llm_scraper = LLMScraper()
    llm_available = True
except Exception as e:
    print(f"LLM Scraper not available: {e}")
    llm_scraper = None
    llm_available = False

# Initialize Firecrawl scraper with error handling
try:
    firecrawl_scraper = FirecrawlScraper()
    firecrawl_available = True
except Exception as e:
    print(f"Firecrawl Scraper not available: {e}")
    firecrawl_scraper = None
    firecrawl_available = False

@app.get("/")
async def root():
    return {
        "message": "Product Scraper API",
        "available_methods": ["basic", "llm", "firecrawl"],
        "endpoints": ["/scrape", "/health", "/methods"]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "product-scraper"}

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_products(request: ScrapeRequest):
    """
    Main scraping endpoint that routes to different scraper implementations
    """
    if not request.product_name.strip():
        raise HTTPException(status_code=400, detail="Product name cannot be empty")
    
    try:
        # Route to appropriate scraper based on method
        if request.scraping_method == "basic":
            results = await basic_scraper.scrape_all(request.product_name)
        elif request.scraping_method == "llm":
            if not llm_available or llm_scraper is None:
                raise HTTPException(status_code=503, detail="LLM scraper not available - check GEMINI_API_KEY")
            results = await llm_scraper.scrape_with_llm(request.product_name)  # Correct method name
        elif request.scraping_method == "firecrawl":
            if not firecrawl_available or firecrawl_scraper is None:
                raise HTTPException(status_code=503, detail="Firecrawl scraper not available - check FIRECRAWL_API_KEY")
            results = await firecrawl_scraper.scrape_all(request.product_name)  # Fixed method name
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unknown scraping method: {request.scraping_method}. Available: basic, llm, firecrawl"
            )
        
        # Convert results to ProductResult format if needed
        formatted_results = []
        for result in results:
            if isinstance(result, dict):
                # Convert dict to ProductResult
                formatted_results.append(ProductResult(
                    website=result.get("website", "Unknown"),
                    title=result.get("title", "N/A"),
                    price=result.get("price", "N/A"),
                    rating=result.get("rating", "N/A"),
                    review_count=result.get("review_count", "0"),
                    url=result.get("url", "")
                ))
            elif hasattr(result, 'dict'):
                # If it's already a Pydantic model
                formatted_results.append(result)
            else:
                # Handle other formats
                formatted_results.append(ProductResult(
                    website=str(getattr(result, 'website', 'Unknown')),
                    title=str(getattr(result, 'title', 'N/A')),
                    price=str(getattr(result, 'price', 'N/A')),
                    rating=str(getattr(result, 'rating', 'N/A')),
                    review_count=str(getattr(result, 'review_count', '0')),
                    url=str(getattr(result, 'url', ''))
                ))
        
        return ScrapeResponse(
            results=formatted_results,
            method_used=request.scraping_method,
            total_found=len(formatted_results)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.get("/methods")
async def get_available_methods():
    """Get available scraping methods and their status"""
    methods = {
        "basic": {
            "available": True,
            "description": "Basic web scraping using BeautifulSoup",
            "websites": ["Amazon", "Walmart", "Newegg"]
        },
        "llm": {
            "available": llm_available,
            "description": "LLM-powered intelligent scraping using Gemini",
            "websites": ["Amazon", "Walmart", "Newegg"],
            "requirements": "GEMINI_API_KEY environment variable"
        },
        "firecrawl": {
            "available": firecrawl_available,
            "description": "Firecrawl API for JavaScript-heavy sites",
            "websites": ["Amazon", "Walmart", "Newegg"],
            "requirements": "FIRECRAWL_API_KEY environment variable"
        }
    }
    return methods

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)