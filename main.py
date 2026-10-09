import os
from copy import copy
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ScrapeFlow API",
    description="High-speed web scraping endpoint for metadata, headings, clean text, and HTML elements.",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RAPIDAPI_PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")


@app.get("/")
@app.head("/")
def read_root():
    return {
        "status": "online",
        "service": "ScrapeFlow API",
        "docs": "/docs"
    }


@app.get("/scrape")
async def scrape_target(
    url: str = Query(..., description="Target webpage URL to scrape"),
    include_metadata: bool = Query(True, description="Extract meta description, OpenGraph tags, and canonical URL"),
    include_links: bool = Query(False, description="Extract all outbound links on the page"),
    include_images: bool = Query(False, description="Extract all image src URLs on the page"),
    selector: Optional[str] = Query(None, description="Optional CSS selector to target specific HTML elements (e.g., '.article-body')"),
    x_rapidapi_proxy_secret: Optional[str] = Header(None, alias="X-RapidAPI-Proxy-Secret")
):
    # 1. Security Check
    if not RAPIDAPI_PROXY_SECRET or x_rapidapi_proxy_secret != RAPIDAPI_PROXY_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Direct access not allowed. Please call this endpoint via RapidAPI."
        )

    # 2. Normalize URL format
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # 3. Async Fetching
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html_content = response.text

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Target page returned HTTP status {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch target URL: {str(e)}")

    # 4. Parsing HTML
    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Page parsing failed: {str(e)}")

    # Core Extraction
    page_title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"
    headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]

    # Clean text preview (Single-pass DOM decomposition)
    text_soup = copy(soup)
    for element in text_soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
        element.decompose()
    clean_text = " ".join(text_soup.get_text(separator=" ").split())[:2000]

    data = {
        "page_title": page_title,
        "headings": headings,
        "clean_text_preview": clean_text
    }

    # 5. Metadata & OpenGraph
    if include_metadata:
        meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        og_image = soup.find("meta", attrs={"property": "og:image"})
        canonical = soup.find("link", attrs={"rel": "canonical"})

        data["metadata"] = {
            "description": meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None,
            "og_image": og_image["content"].strip() if og_image and og_image.get("content") else None,
            "canonical_url": canonical["href"].strip() if canonical and canonical.get("href") else None
        }

    # 6. Custom CSS Selector
    if selector:
        selected_elements = [el.get_text(strip=True) for el in soup.select(selector) if el.get_text(strip=True)]
        data["custom_selector_matches"] = selected_elements

    # 7. Outbound Links Extraction
    if include_links:
        links = set()
        for a in soup.find_all("a", href=True):
            full_url = urljoin(url, a["href"])
            if full_url.startswith(("http://", "https://")):
                links.add(full_url)
                if len(links) >= 100:
                    break
        data["links"] = list(links)

    # 8. Images Extraction
    if include_images:
        images = set()
        for img in soup.find_all("img", src=True):
            full_img_url = urljoin(url, img["src"])
            if full_img_url.startswith(("http://", "https://")):
                images.add(full_img_url)
                if len(images) >= 50:
                    break
        data["images"] = list(images)

    return {
        "status": "success",
        "target": url,
        "extracted_data": data
    }
