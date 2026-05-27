from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def scrape_mse_data():
    url = "https://mse.co.mw/market/mainboard"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)

        # If Sucuri challenge page appears, click through it
        if "GoDaddy Security" in page.title() or "Access Denied" in page.title():
            print("[DEBUG] Challenge page detected, attempting to click through...")
            btn = page.locator("input[type=submit], button[type=submit], button, input[type=button]").first
            btn.click()
            page.wait_for_load_state("networkidle", timeout=20000)
            print(f"[DEBUG] After click — title: {page.title()}")

        page.wait_for_selector("tbody", timeout=15000)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find("tbody").find_all("tr")
    # print(rows)

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
        cols = row.find_all("td")
        if len(cols) >= 6:
            # Extract symbol from the <a> tag inside the first <td>
            symbol = cols[0].find("a").text.strip()
            
            if symbol in market_data:
                market_data[symbol].update({
                    "open": cols[1].text.strip().replace(',', ''),
                    "close": cols[2].text.strip().replace(',', ''),
                    "change": float(cols[2].text.strip().replace(',', '')) - float(cols[1].text.strip().replace(',', '')),
                    "pct_change": round((float(cols[2].text.strip().replace(',', '')) - float(cols[1].text.strip().replace(',', ''))) / float(cols[1].text.strip().replace(',', '')) * 100, 4),
                    "volume": cols[4].text.strip().replace(',', ''),
                    "turnover": cols[5].text.strip().replace(',', '')
                })
    
    return market_data

if __name__ == "__main__":
    populated_data = scrape_mse_data()
    import json
    print(json.dumps(populated_data, indent=4))
