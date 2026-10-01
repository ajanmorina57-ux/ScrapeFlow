import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urljoin

app = FastAPI(
    title="ScrapeFlow API",
    description="High-speed web scraping endpoint for metadata, headings, clean text, and HTML elements.",
    version="1.1.0"
)

# Enable CORS for web frontend clients
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
def scrape_target(
    url: str = Query(..., description="Target webpage URL to scrape"),
    include_metadata: bool = Query(True, description="Extract meta description, OpenGraph tags, and canonical URL"),
    include_links: bool = Query(False, description="Extract all outbound links on the page"),
    include_images: bool = Query(False, description="Extract all image src URLs on the page"),
    selector: str = Query(None, description="Optional CSS selector to target specific HTML elements (e.g., '.article-body')"),
    x_rapidapi_proxy_secret: str = Header(None, alias="X-RapidAPI-Proxy-Secret")
):
    # 1. RapidAPI Security Check
    if not RAPIDAPI_PROXY_SECRET or x_rapidapi_proxy_secret != RAPIDAPI_PROXY_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Direct access not allowed. Please call this endpoint via RapidAPI."
        )

    # 2. Normalize URL format
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # 3. Fetch Page Content
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch target URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Page parsing failed: {str(e)}")

    # 4. Core Extraction
    page_title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"
    headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]

    # Clean text extraction (Stripping noise for LLM friendliness)
    soup_copy = BeautifulSoup(response.text, "html.parser")
    for element in soup_copy(["script", "style", "nav", "footer", "header", "noscript"]):
        element.decompose()
    clean_text = " ".join(soup_copy.get_text(separator=" ").split())[:2000]  # First 2000 chars

    data = {
        "page_title": page_title,
        "headings": headings,
        "clean_text_preview": clean_text
    }

    # 5. Optional Feature: Metadata & OpenGraph
    if include_metadata:
        meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        og_image = soup.find("meta", attrs={"property": "og:image"})
        canonical = soup.find("link", attrs={"rel": "canonical"})

        data["metadata"] = {
            "description": meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None,
            "og_image": og_image["content"].strip() if og_image and og_image.get("content") else None,
            "canonical_url": canonical["href"].strip() if canonical and canonical.get("href") else None
        }

    # 6. Optional Feature: Custom CSS Selector
    if selector:
        selected_elements = [el.get_text(strip=True) for el in soup.select(selector) if el.get_text(strip=True)]
        data["custom_selector_matches"] = selected_elements

    # 7. Optional Feature: Links Extraction
    if include_links:
        links = set()
        for a in soup.find_all("a", href=True):
            full_url = urljoin(url, a["href"])
            if full_url.startswith("http"):
                links.add(full_url)
        data["links"] = list(links)[:100]  # Cap at 100 links

    # 8. Optional Feature: Images Extraction
    if include_images:
        images = set()
        for img in soup.find_all("img", src=True):
            full_img_url = urljoin(url, img["src"])
            if full_img_url.startswith("http"):
                images.add(full_img_url)
        data["images"] = list(images)[:50]  # Cap at 50 images

    return {
        "status": "success",
        "target": url,
        "extracted_data": data
    }

