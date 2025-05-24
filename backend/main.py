from scraping import basic
from fastapi import FastAPI, Query
app = FastAPI()

@app.get("/scrape/")
def scrape(product: str = Query(...), method: str = Query(...), site: str = Query("amazon")):
    if method == "basic":
        if site == "amazon":
            return basic.scrape(product)
        elif site == "newegg":
            return basic.scrape_newegg(product)
        else:
            return {"error": "Unsupported site for basic scraping"}
    else:
        return {"error": "Invalid method"}
