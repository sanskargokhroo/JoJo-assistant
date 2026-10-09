"""
🌐 JoJo AGI: Web Perception Engine
Gives JoJo live internet browsing, information retrieval, and reading capabilities:
- DuckDuckGo web search
- Webpage content scraping, cleaning & markdown conversion
- Wikipedia quick fact retrieval
"""

import urllib.request
import urllib.parse
import json
import re
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

def web_search(query: str, max_results: int = 5) -> str:
    """Searches the live web for the given query and returns top results with titles, links, and snippets."""
    clean_q = query.strip()
    if not clean_q:
        return "⚠️ Search query cannot be empty."

    # Method 1: DuckDuckGo Lite
    try:
        url = 'https://lite.duckduckgo.com/lite/'
        data = urllib.parse.urlencode({'q': clean_q}).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'User-Agent': USER_AGENT,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # In DDG Lite: results are in tables with class 'result-snippet' and links
        snippets = soup.find_all('td', class_='result-snippet')
        links = soup.find_all('a', class_='result-link')
        
        for i in range(min(len(snippets), len(links), max_results)):
            title = links[i].get_text().strip()
            href = links[i].get('href', '')
            snip = snippets[i].get_text().strip()
            results.append(f"[{i+1}] {title}\n    Link: {href}\n    Snippet: {snip}")

        if results:
            return f"🔎 Search Results for '{clean_q}':\n\n" + "\n\n".join(results)
    except Exception as e:
        print(f"⚠️ DDG Lite search error: {e}")

    # Method 2: Wikipedia Summary Fallback
    wiki_res = wikipedia_summary(clean_q)
    if wiki_res and "Not found" not in wiki_res:
        return f"🔎 Wikipedia Result for '{clean_q}':\n{wiki_res}"

    return f"⚠️ No search results found for '{clean_q}' or search service unreachable."

def read_webpage(url: str, max_length: int = 3500) -> str:
    """Fetches the content of a public webpage, extracts clean text, and returns a readable summary."""
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    try:
        req = urllib.request.Request(clean_url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove noisy elements
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "aside", "svg"]):
            element.extract()

        # Extract title and body text
        title = soup.title.string.strip() if soup.title and soup.title.string else "No Title"
        lines = (line.strip() for line in soup.get_text().splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        if len(text) > max_length:
            text = text[:max_length] + "\n...[Content truncated for length]"

        return f"📄 Webpage: {title}\nURL: {clean_url}\n\n{text}"
    except Exception as e:
        return f"⚠️ Could not read webpage '{clean_url}': {str(e)}"

def wikipedia_summary(query: str) -> str:
    """Retrieves a direct factual summary from Wikipedia API."""
    try:
        encoded = urllib.parse.quote(query.strip())
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        title = data.get("title", "")
        extract = data.get("extract", "")
        if extract:
            return f"📘 {title}: {extract}"
        return "Not found on Wikipedia."
    except Exception:
        return "Not found on Wikipedia."
