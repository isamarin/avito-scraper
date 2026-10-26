"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does (paged endpoints carry a
`pagination` block instead of next / previous links); results are written
to output/*.json.
"""
import json
import os

from avito.api import ad_details, ads_search, seller_details
from avito.refs import resolve_seller

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # an ad id or any avito.ru ad link resolves to the same ad
    save("ad_bmw_x5.json", ad_details(ad=7726049894))

    # 50 ads per page; location / category take ids, names, slugs or links
    save("search_iphone_15_pro.json", ads_search(
        query="iphone 15 pro", location={"slug": "moskva"}, category=None, price_min=None,
        price_max=None, filters=None, seller_type=None, with_photos_only=None, delivery_only=None,
        title_only=None, radius=None, sort="relevance", page=1))

    # a profile slug, the 32-character profile key or a profile link
    save("seller_americanauto.json", seller_details(seller=resolve_seller("americanauto")))
