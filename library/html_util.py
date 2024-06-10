from dataclasses import dataclass
from typing import NamedTuple

from bs4 import BeautifulSoup

from library import url_util


# List of link rel values for favicons.
FAVICON_REL = [
    "icon",
    "apple-touch-icon",
    "shortcut icon",
]

COMMON_FAVICON_FILES = [
    "favicon.ico",
    "favicon.png",
    "favicon.svg",
    "favicon.jpg",
    "favicon.gif",
]


@dataclass
class RelLink:
    href: str
    rel: str = None
    sizes: str = None
    height: int = 0
    width: int = 0


def get_favicon_links(page_url, html_string):
    """Get the favicon links for the page URL."""

    soup = BeautifulSoup(html_string, 'html.parser')
    head = soup.find('head')

    # Keep track of href already seen.
    seen = set()

    # Try to find links in <head>.
    links = []
    if head:
        for link in head.find_all('link'):
            href = str(url_util.make_absolute_urls(page_url, link.get('href')))
            sizes = link.get('sizes')
            rel = link.get('rel')

            if href in seen:
                continue
            seen.add(href)

            # Make sure rel is a list.
            if not isinstance(rel, list):
                rel = [rel]
            
            for r in rel:
                if r in FAVICON_REL:
                    links.append(RelLink(href, rel, sizes))
                    break

        if links:
            return links

    # Fallback to common favicon files.
    for f in COMMON_FAVICON_FILES:
        if url_util.check_url_exists(url_util.make_absolute_urls(page_url, f)):
            links.append(RelLink(url_util.make_absolute_urls(page_url, f)))
            return links
        
    # No favicon links found.
    return []


def get_common_favicon_links(page_url):
    """Get the common favicon links for the page URL."""

    # Build links for the common favicon files.
    links = []
    for f in COMMON_FAVICON_FILES:
        links.append(RelLink(url_util.make_absolute_urls(page_url, f)))

    return links

