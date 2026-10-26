"""Cache TTL per /avito/* endpoint (cache.py, keyed on the validated
params). Avito is a live classifieds site: ads are bumped, repriced, sold
and closed all day, so listing data is cached briefly; reference data
(locations, the category tree) barely moves. The seller endpoints share ONE
cached profile parse (api._seller), so details + ads + reviews of the same
seller cost one profile page fetch.
"""
from datetime import timedelta

# Search results reorder as ads are posted and bumped (newest-first moves by the minute).
SEARCH_CACHE = timedelta(minutes=30)
# An ad's price, status and view counters change during the day.
AD_CACHE = timedelta(hours=1)
# A seller's profile page (name, rating, counts, profile key) moves slowly,
# and it is the flakiest surface to fetch (rendered without its state on
# about half the loads, 2026-10-24), so one good parse is kept half a day.
SELLER_CACHE = timedelta(hours=12)
# A seller's active ads list changes as they post / close ads.
SELLER_ADS_CACHE = timedelta(hours=1)
# Reviews accumulate slowly (a few a week for busy sellers).
SELLER_REVIEWS_CACHE = timedelta(hours=12)
# The location directory is static (ids are permanent).
LOCATIONS_CACHE = timedelta(days=7)
# A location slug -> id mapping never changes; one 1.7 MB page read per slug.
LOCATION_SLUG_CACHE = timedelta(days=30)
# The category navigation tree changes with site releases, rarely.
CATEGORY_TREE_CACHE = timedelta(hours=24)
