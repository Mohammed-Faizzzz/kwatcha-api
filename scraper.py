from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import asyncio

async def scrape_mse_data():
    url = "https://mse.co.mw/market/mainboard"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            if "GoDaddy Security" in await page.title() or "Access Denied" in await page.title():
                print("[DEBUG] Challenge page detected, attempting to click through...")
                btn = page.locator("input[type=submit], button[type=submit], button, input[type=button]").first
                await btn.click()
                await page.wait_for_load_state("networkidle", timeout=20000)

            await page.wait_for_selector("tbody", timeout=15000)
            html = await page.content()
        finally:
            await browser.close()

    soup = BeautifulSoup(html, "html.parser")
    tbody = soup.find("tbody")
    rows = tbody.find_all("tr") if tbody else []
    if not rows:
        print("[Scraper] No rows found in table body")

    market_data = {
        "AIRTEL": {
            "url": "https://mse.co.mw/company/MWAIRT001156",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            }, 
        "BHL": {
            "url": "https://mse.co.mw/company/MWBHL0010029",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "FDHB": {
            "url": "https://mse.co.mw/company/MWFDHB001166",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "FMBCH": {
            "url": "https://mse.co.mw/company/MWFMB0010138",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "ICON": {
            "url": "https://mse.co.mw/company/MWICON001146",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "ILLOVO": {
            "url": "https://mse.co.mw/company/MWILLV010032",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "MPICO": {
            "url": "https://mse.co.mw/company/MWMPI0010116",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "NBM": {
            "url": "https://mse.co.mw/company/MWNBM0010074",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "NBS": {
            "url": "https://mse.co.mw/company/MWNBS0010105",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "NICO": {
            "url": "https://mse.co.mw/company/MWNICO010014",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "NITL": {
            "url": "https://mse.co.mw/company/MWNITL010091",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "OMU": {
            "url": "https://mse.co.mw/company/ZAE000255360",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "PCL": {
            "url": "https://mse.co.mw/company/MWPCL0010053",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "STANDARD": {
            "url": "https://mse.co.mw/company/MWSTD0010041",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "SUNBIRD": {
            "url": "https://mse.co.mw/company/MWSTL0010085",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            },
        "TNM": {
            "url": "https://mse.co.mw/company/MWTNM0010126",
            "open": None,
            "close": None,
            "change": None,
            "volume": None,
            "turnover": None
            }
    }
    
    for row in rows:
        try:
            cols = row.find_all("td")
            if len(cols) < 6:
                continue

            # Extract symbol from the <a> tag inside the first <td>
            symbol_tag = cols[0].find("a")
            if symbol_tag is None:
                continue
            symbol = symbol_tag.text.strip()

            if symbol not in market_data:
                continue

            open_price = float(cols[1].text.strip().replace(',', ''))
            close_price = float(cols[2].text.strip().replace(',', ''))
            pct_change = round((close_price - open_price) / open_price * 100, 4) if open_price else 0.0

            market_data[symbol].update({
                "open": cols[1].text.strip().replace(',', ''),
                "close": cols[2].text.strip().replace(',', ''),
                "change": close_price - open_price,
                "pct_change": pct_change,
                "volume": cols[4].text.strip().replace(',', ''),
                "turnover": cols[5].text.strip().replace(',', '')
            })
        except (ValueError, AttributeError, IndexError) as e:
            print(f"[Scraper] Skipping malformed row: {e}")
            continue

    return market_data

if __name__ == "__main__":
    import json
    populated_data = asyncio.run(scrape_mse_data())
    print(json.dumps(populated_data, indent=4))
