import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

app = FastAPI()

API_KEY_NAME = "access_token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Your Gumroad Product permalink
GUMROAD_PRODUCT_ID = "gsjvly"

@app.get("/scrape")
def scrape_target(url: str, api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=403, 
            detail="Missing API Key. Please include your access_token."
        )
    
    # Verify the license key with Gumroad's official API
    response = requests.post(
        "https://api.gumroad.com/v2/licenses/verify",
        data={
            "product_id": GUMROAD_PRODUCT_ID,
            "license_key": api_key
        }
    )
    
    data = response.json()
    
    # Check if the license is valid and not refunded/chargebacked
    if not data.get("success") or data.get("purchase", {}).get("chargebacked"):
        raise HTTPException(
            status_code=403, 
            detail="Invalid or expired license key."
        )
    
    # --- ACTUAL SCRAPING LOGIC ---
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        page_response = requests.get(url, headers=headers, timeout=10)
        page_response.raise_for_status()
        
        soup = BeautifulSoup(page_response.text, "html.parser")
        
        # Extract page title
        page_title = soup.title.string.strip() if soup.title else "No title found"
        
        # Extract main headings (h1 and h2)
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2"])]
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to scrape the target URL: {str(e)}"
        )
    
    # Return the real extracted data
    return {
        "status": "success",
        "target": url,
        "extracted_data": {
            "page_title": page_title,
            "headings": headings
        }
    }