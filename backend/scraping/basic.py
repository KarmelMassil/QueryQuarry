import requests
from bs4 import BeautifulSoup

def scrape_newegg(product: str):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    query = product.replace(" ", "+")
    url = f"https://www.newegg.com/p/pl?d={query}"

    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    items = soup.select(".item-cell")

    for item in items:
        title_tag = item.select_one(".item-title")
        price_whole = item.select_one(".price-current strong")
        price_fraction = item.select_one(".price-current sup")
        rating = item.select_one(".item-rating")  # class="item-rating" with stars
        reviews = item.select_one(".item-rating-num")

        if title_tag and price_whole and price_fraction:
            return {
                "Website": "Newegg.com",
                "Title": title_tag.text.strip(),
                "Price (USD)": f"{price_whole.text.strip()}{price_fraction.text.strip()}",
                "Rating": rating["class"][1] if rating and len(rating["class"]) > 1 else "N/A",
                "Reviews": reviews.text.strip("()") if reviews else "N/A"
            }

    return {"error": "No valid products found on Newegg"}
