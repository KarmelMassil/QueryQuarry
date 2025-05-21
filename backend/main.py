# backend/main.py
from fastapi import FastAPI, Query
from backend.scraping import basic, llm, firecrawl

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Scraper is running"}

@app.get("/scrape/")
def scrape(product: str = Query(...), method: str = Query(...)):
    if method == "basic":
        return basic.scrape(product)
    elif method == "llm":
        return llm.scrape(product)
    elif method == "firecrawl":
        return firecrawl.scrape(product)
    else:
        return {"error": "Invalid method"}
