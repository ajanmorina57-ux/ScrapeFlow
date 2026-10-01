import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Header

app = FastAPI(title="ScrapeFlow API")

RAPIDAPI_PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")


# 1. Health check endpoint for Render & UptimeRobot
@app.get("/health")
@app.head("/health")
def health_check():
    return {"status": "OK"}


# 2. Main scraping endpoint
@app.get("/scrape")
def scrape_target(
    url: str,
    x_rapidapi_proxy_secret: str = Header(None, alias="X-RapidAPI-Proxy-Secret")
):
    # Verify request came through RapidAPI Gateway
    if not RAPIDAPI_PROXY_SECRET or x_rapidapi_proxy_secret != RAPIDAPI_PROXY_SECRET:
        raise HTTPException(
            status_code=403, 
            detail="Forbidden: Direct access not allowed. Please call this endpoint via RapidAPI."
        )

    # Normalize URLs missing http/https prefixes
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Scraping execution
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        page_response = requests.get(url, headers=headers, timeout=10)
        page_response.raise_for_status()

        soup = BeautifulSoup(page_response.text, "html.parser")

        # Safely parse elements
        page_title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2"]) if h.get_text(strip=True)]

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch target URL: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data extraction failed: {str(e)}"
        )

    return {
        "status": "success",
        "target": url,
        "extracted_data": {
            "page_title": page_title,
            "headings": headings
        }
    }


