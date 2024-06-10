from io import BytesIO
from dataclasses import dataclass
import logging

from PIL import Image
import requests
import tldextract
import urllib.parse
from urllib.parse import urljoin

from library import html_util


DEFAULT_TIMEOUT = 5
# Brave Browser
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def check_url_exists(url):
    """
    Checks if a URL exists.

    Returns True if the URL exists, False otherwise.
    """

    try:
        print(f"Checking if {url} exists")
        response = requests.head(url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=DEFAULT_TIMEOUT)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def get_top_domain_name(url):
    """
    Given a URL, this function extracts the top-level domain (TLD) from the URL.

    Parameters:
        url (str): The URL from which to extract the TLD.

    Returns:
        str: The d

    Raises:
        None

    Example:
        >>> get_top_domain_name("https://www.example.com")
        'example.com'
    """
        
    parsed_url = urllib.parse.urlparse(url)
    subdomain = parsed_url.netloc
    extracted = tldextract.extract(subdomain)

    # Return domain name starting with www if subdomain is 'www'
    if extracted.subdomain == 'www':
        return f'{extracted.subdomain}.{extracted.domain}.{extracted.suffix}'
    else:
        return f'{extracted.domain}.{extracted.suffix}'
    

@dataclass
class ImageSize:
    width: int
    height: int


def get_image_size(url):
    """
    Gets the width and height of an image.

    Returns a named tuple with width and height if the image exists, None otherwise.
    """

    try:
        print(f"Getting image size for {url}")
        response = requests.get(url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=DEFAULT_TIMEOUT)

        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            width, height = image.size
            return ImageSize(width, height)
    except Exception as e:
        # Any exceptions are ignored.
        logging.warning(e)
        pass

    return None


def sort_favicon_links(favicon_links):
    """
    Sort favicon links by size descending. If any links are for common favicon files, they will appear first.
    """

    new_links = []
    for link in favicon_links:
        #  Skip if link is missing 'href'.
        if not link.href:
            continue

        # Fetch the image and get its size.
        s = get_image_size(link.href)
        if s is  None:
            # Failed to get image. Skip.
            continue

        link.width = s.width
        link.height = s.height
        new_links.append(link)

    # Sort by size descending
    new_links.sort(key=lambda x: x.width * x.height, reverse=True)

    # Move any common favicon links to the beginning.
    for link in new_links:
        parsed = urllib.parse.urlparse(link.href)
        if parsed.path.lstrip("/") in html_util.COMMON_FAVICON_FILES:
            new_links.remove(link)
            new_links.insert(0, link)

    return new_links


def make_absolute_urls(page_url, linked_url):
    """Convert relative URLs to absolute URLs."""

    # If the URL is already absolute, return it as is.
    if linked_url.startswith('http://') or linked_url.startswith('https://'):
         return linked_url
    else:
        return str(urljoin(page_url, linked_url))


