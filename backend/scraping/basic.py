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
        rating_tag = item.select_one(".item-rating")
        rating = rating_tag["title"] if rating_tag and "title" in rating_tag.attrs else "N/A"
        reviews = item.select_one(".item-rating-num")

        if title_tag and price_whole and price_fraction:
            return {
                "Website": "Newegg.com",
                "Title": title_tag.text.strip(),
                "Price (USD)": f"{price_whole.text.strip()}{price_fraction.text.strip()}",
                "Rating": rating,
                "Reviews": reviews.text.strip("()") if reviews else "N/A"
            }

    return {"error": "No valid products found on Newegg"}
