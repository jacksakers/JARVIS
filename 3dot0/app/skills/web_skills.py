"""
Web skills — allows JARVIS to search the internet and read web pages.
Requires: pip install duckduckgo-search requests
"""
import requests
from pydantic import BaseModel, Field
from ddgs import DDGS

from .base_skill import BaseSkill

# ── web_search ───────────────────────────────────────────────────────────────

class WebSearchInput(BaseModel):
    query: str = Field(
        description="The exact search query to look up on the internet."
    )
    max_results: int = Field(
        default=3, 
        description="Number of results to return. Max is 5 to save context space."
    )

class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = (
        "Searches the internet using DuckDuckGo. Returns the title, URL, and a "
        "short text snippet for the top results. Use this to find up-to-date facts, "
        "news, or to find URLs to read deeper into."
    )
    input_model = WebSearchInput

    def execute(self, params: WebSearchInput) -> str:
        try:
            # Enforce a hard limit so the LLM doesn't overflow its context window
            limit = min(params.max_results, 5)
            
            results = DDGS().text(params.query, max_results=limit)
            if not results:
                return f"No search results found for '{params.query}'."

            output = [f"Search Results for '{params.query}':\n"]
            for r in results:
                output.append(f"Title: {r['title']}")
                output.append(f"Snippet: {r['body']}")
                output.append(f"URL: {r['href']}\n")
                
            return "\n".join(output)

        except Exception as exc:
            return f"Web search failed: {exc}"


# ── read_webpage ─────────────────────────────────────────────────────────────

class ReadWebpageInput(BaseModel):
    url: str = Field(
        description="The exact URL (starting with http or https) of the webpage to read."
    )

class ReadWebpageSkill(BaseSkill):
    name = "read_webpage"
    description = (
        "Extracts and reads the clean text content from a specific webpage URL. "
        "Use this if the snippet from the web_search tool did not contain enough information. "
        "Do not use this on YouTube or video links."
    )
    input_model = ReadWebpageInput

    def execute(self, params: ReadWebpageInput) -> str:
        try:
            # We use Jina AI's free reader endpoint. It turns any webpage into LLM-friendly Markdown.
            jina_url = f"https://r.jina.ai/{params.url}"
            
            headers = {
                "Accept": "text/plain",
                "X-Return-Format": "markdown"
            }
            
            response = requests.get(jina_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            content = response.text
            
            # Truncate content to roughly ~4000 characters to protect your context window
            # if len(content) > 4000:
            #     content = content[:4000] + "\n\n...[CONTENT TRUNCATED FOR LENGTH]..."
                
            return content

        except Exception as exc:
            return f"Failed to read webpage. It might be blocked or offline. Error: {exc}"