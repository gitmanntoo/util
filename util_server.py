#!/usr/bin/env python3
import os
import json
from pathlib import Path
from collections import namedtuple
from dataclasses import dataclass, asdict, field
import re
from urllib.parse import urlparse, urljoin, urlsplit, urlunsplit, urlunparse

import fitz
from flask import Flask, abort, make_response, render_template, request, send_file, send_from_directory
from jinja2 import Environment, FileSystemLoader
import jsmin
from playwright.sync_api import sync_playwright
import pyperclip
import requests
import yaml

from bs4 import BeautifulSoup

from library import url_util 
from library import html_util


app = Flask(__name__)

STATIC_DIR = Path("static")
SIZE_REGEX = re.compile(r'\b(\d+)x(\d+)\b')

# Initialize template environment.
template_loader = FileSystemLoader('templates')
template_env = Environment(loader=template_loader)


@app.route('/')
def read_root():
    return "Hello, World!"


def get_javascript_file(filename, mode):
    # Read the contents of the file
    try:
        with open(STATIC_DIR / "javascript" / f"{filename}.js", "r") as f:
            contents = f.read()
    except FileNotFoundError:
        abort(404)  # Not found if the file does not exist

    # Minify the contents if set.
    if mode in ("minify","bookmarklet"):
        contents = jsmin.jsmin(contents).strip()

    # Add a bookmarklet if set.
    if mode == "bookmarklet":
        contents = f"javascript:(function(){{{contents}}})();"

    # Return the contents
    return contents


@app.route('/bb')
def get_bookmarklets():
    """
    Return a list of bookmarklet names and javascript.

    Returns
    -------
    str
        A string containing the bookmarklet names and javascript.
        Each bookmarklet is on its own line, with the name in all caps
        followed by the javascript, followed by an empty line.
        The mimetype of the response is text/plain.
    """

    print("debugxxxxx 01")
    out = []
    for name in ("markdown","github","jira","links","clip","html","pdf","text"):
        out.append(name.upper())
        out.append(get_javascript_file(name, "bookmarklet"))
        out.append("")

    outStr = "\n".join(out)
    pyperclip.copy(outStr)

    resp = make_response(outStr)
    resp.headers['Content-Type'] = 'text/plain'
    return resp



@app.route('/javascript/<filename>.js')
def serve_js(filename):
    """
    Serves javascript files from the static directory.
    
    Mode controls the output format:
    - "minify": minified javascript
    - "bookmarklet": a bookmarklet from minified javascript
    - default: unmodified javascript
    """
    # Ensure the filename does not contain path traversals
    if '..' in filename or filename.startswith('/'):
        abort(404)  # Not found

    # Read options
    mode = request.args.get("mode","")
    
    # Return the contents
    outStr = get_javascript_file(filename, mode)
    pyperclip.copy(outStr)

    response = make_response(outStr)
    response.headers['Content-Type'] = 'text/plain'
    
    return response



"""
/mirror endpoints consist of a POST and GET endpoint
- POST collects the URL, HEADERS, and BODY into local variables
- GET matches the URL with the stored URL
    - If the URL matches, the stored HEADERS and BODY are used
    - If URL does not match, the HEADERS and BODY from the request are used
"""
mirror_url = None
mirror_request = None

def request_to_dict(request):
    """Convert a request to a dictionary in a standard way."""
    out = {
        "url": request.args.get("url",request.url),
        "title": request.args.get("title",""),
        "headers": {k:v for k,v in request.headers.items()},
        "query_string": request.query_string,
        "query": {k:v for k,v in request.args.to_dict(flat=True).items()},
        "data": request.get_data(),
    }

    return out

EXCLUDE_ELEMENTS = set((
    "script",
    "style",
))

TextTuple = namedtuple("TextTuple", [
    "indent",
    "name",
    "text",
])

def iterate_elements(element, depth=0):
    out = []
    if hasattr(element, 'name') and element.name is not None:
        # Skip certain types of elements.
        text_content = None
        if element.name not in EXCLUDE_ELEMENTS:
            parent_text = element.get_text(strip=True)

            # Print the element's name and its depth (indentation level)
            if parent_text:
                text_content = TextTuple("\n"+'..' * depth, element.name.upper() + ":", parent_text)
        
        # Iterate over each child, increasing the depth
        child_text = None
        for child in element.children:
            child_text = iterate_elements(child, depth + 1)

        # if child_text:
        #     # Iterate over children in reverse and remove text from the parent.
        #     for c in child_text[::-1]:
        #         if text_content.text.endswith(c.text):
        #             text_content = TextTuple(text_content.indent, text_content.name, text_content.text[:-len(c[2])])

        if text_content:
            out.append(text_content)
        if child_text:
            out.extend(child_text)

    return out


@app.route('/clip')
def get_clipboard():
    """Return the contents of the clipboard."""

    # Read clipboard contents.
    clip = pyperclip.paste()

    # If contents are not valid JSON, return plain text.
    try:
        clip_json = json.loads(clip)
    except json.JSONDecodeError:
        resp = make_response( clip.strip())
        resp.headers['Content-Type'] = 'text/plain'
        return resp
    
    # Compare the clipboard URL to the URL in the request.
    if clip_json.get("url") != request.args.get("url"):
        resp_msg = "ERROR: URL in clipboard does not match request URL.\n{}".format(json.dumps(clip_json, indent=2))
        resp = make_response(resp_msg)
        resp.headers['Content-Type'] = 'text/plain'
        return resp
    
    # JSON is valid and URL matches. Parse and return HTML.
    soup = BeautifulSoup(clip_json["html"], 'html.parser')
    resp = make_response(soup.prettify())
    resp.headers['Content-Type'] = 'text/plain'
    return resp


CONFIG = yaml.safe_load(open("util_server.yml"))
ALIAS_MAP = CONFIG.get("alias_map", {})
IMAGE_TYPES = CONFIG.get("image_types", [])
FAVICON_WIDTH = 20

PDF_TMP_DIR = Path("tmp/pdf")
PDF_FILE = PDF_TMP_DIR / "output.pdf"
PDF_IMAGES_DIR = Path("tmp/pdf/images")

@app.route('/pdf/images/<filename>')
def get_pdf_images(filename):
    return send_from_directory(PDF_IMAGES_DIR, filename)


@app.route('/pdf')
def make_pdf():
    # Read query parameters.
    mode = request.args.get("mode","pdf")
    url = request.args.get("url","")
    if url == "":
        return "Error: No URL provided.", 400
    
    # Read clipboard contents.
    clip = pyperclip.paste()

    # If contents are not valid JSON, return error.
    try:
        clip_json = json.loads(clip)
        if url != clip_json["url"]:
            raise Exception("URL in clipboard does not match request URL.")
        soup = BeautifulSoup(clip_json["html"], 'html.parser')
    except Exception as e:
        return str(e), 400

    # Create the images directory if it doesn't exist.
    os.makedirs(PDF_IMAGES_DIR, exist_ok=True)

    # Write HTML to temporary file.
    html_file = PDF_TMP_DIR / "output.html"
    with open(html_file, "w") as f:
        f.write(soup.prettify())

    full_html_path = html_file.resolve()

    output_path = PDF_FILE

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Load the HTML file
        page.goto(f"file://{full_html_path}")
        
        # Wait for the page to load
        page.wait_for_load_state("load")
        print(f"{page.viewport_size=}")

        # Generate the PDF using the default viewport size.
        page.pdf(path=output_path,scale=1)

        # # Read the PDF and get the number of pages.
        # pdf_doc = fitz.open(output_path)
        # num_pages = pdf_doc.page_count
        # print(f"{num_pages=}")
        # pdf_doc.close()

        # # Adjust the size of the viewport and regenerate the pdf.
        # page.set_viewport_size({"width": page.viewport_size["width"], "height": num_pages * page.viewport_size["height"]})
        # print(f"{page.viewport_size=}")
        # # page.goto(url)
        # page.pdf(path=output_path,scale=1, width=str(page.viewport_size["width"]), height=str(page.viewport_size["height"]))
        
        browser.close()

    if mode in ("html", "text", ):
        # Build a web page with text and images extracted from the PDF.
        # Open the PDF file
        pdf_document = fitz.open(output_path)

        # Extract text and images from the PDF and build a web page.
        html_parts = []

        for page_num in range(pdf_document.page_count):
            # Add page heading
            # html_parts.append(f"<h1>Page {page_num + 1}</h1>")

            page = pdf_document.load_page(page_num)
            
            # Extract text from the page
            text = page.get_text("text")
            html_parts.append(f"<pre>{text}</pre>")

            # Extract images from the page
            if mode in ("html",):
                image_list = page.get_images(full=True)
                for img in image_list:
                    xref = img[0]

                    pix = fitz.Pixmap(pdf_document, xref)
                    pix_filename = f"image_{xref}.png"
                    with open(PDF_IMAGES_DIR / pix_filename, "wb") as fp:
                        fp.write(pix.tobytes())

                    html_parts.append(f'<img src="pdf/images/{pix_filename}"><br>')

                    # base_image = pdf_document.extract_image(xref)
                    # image = base_image["image"]
                    # content_in_order.append(image)

        # Close the PDF file
        pdf_document.close()

        # # Generate HTML content for the web page
        # for content in content_in_order:
        #     if isinstance(content, str):
        #         # Add text content to the HTML
        #         html_parts.append(f"<p>{content}</p>")
        #     else:
        #         # Save the image to a local file
        #         image_path = f"image_{content_in_order.index(content)}.png"
        #         content.save(image_path)

        #         # Add image link to the HTML
        #         # html_content += f'<img src="{image_path}" width="50%" height="50%">'
        #         html_parts.append(f'<img src="{image_path}" width="50%" height="50%">')

        return "\n".join(html_parts)
    else:
        return send_file(output_path, mimetype='application/pdf', as_attachment=True)    


@dataclass
class PageMetadata:
    title: str
    url: str
    host_url: str = None
    host: str = None
    html: str = None
    favicons: list[html_util.RelLink] = field(default_factory=list)
    error: str = None

def get_page_metadata(max_favicon_links: int=1, favicon_width: int=FAVICON_WIDTH) -> PageMetadata:
    """Add metadata to PageMetadata object."""

    # Get metadata from rueqest parameters.
    meta = PageMetadata(
        title=request.args.get("title",""),
        url=request.args.get("url",""),
    )

    # Read clipboard contents.
    clip = pyperclip.paste()

    # If contents are not valid JSON, return plain text.
    try:
        clip_json = json.loads(clip)
        meta.html = clip_json.get("html", "")
    except json.JSONDecodeError as e:
        meta.error = str(e)
        return meta

    # Get the host from the URL
    parsed = urlparse(meta.url)
    meta.host_url = f'{parsed.scheme}://{parsed.netloc}'
    meta.host = parsed.netloc

    # Prettify HTML
    if meta.html:
        soup = BeautifulSoup(meta.html, 'html.parser')
        meta.html = soup.prettify()

    # Extract favicon links from the HTML page in descending order by size.
    favicon_links = html_util.get_favicon_links(meta.url, meta.html)
    meta.favicons =url_util.sort_favicon_links(favicon_links, max_favicon_links, favicon_width)

    return meta


@app.route('/links')
def links():
    """Render the links page.

    Parameters:
    - url: str -- URL of source page
    - title: str -- Title of source page
    """

    meta = get_page_metadata()    

    template = template_env.get_template('links.html')
    rendered_html = template.render(asdict(meta))
    resp = make_response(rendered_html)

    return resp


@app.route('/markdown')
def markdown():
    """Build a markdown link for page.

    Parameters:
    - url: str -- URL of source page
    - title: str -- Title of source page
    - format: str -- Format of link. Default: "obsidian"
        - "obsidian": obsidian link consisting of ![favicon|20] [host title](url)
        - "github": github markdown consisting of [title](url) without any modifications
        - "jira": JIRA format using pipe: [title|url]
    """
    format = request.args.get("format","obsidian")

    # Adjust the number of favicons based on the format.
    if format == "obsidian":
        max_favicon_links = 1
    elif format == "github":
        max_favicon_links = 0
    elif format == "jira":
        max_favicon_links = 0
    else:
        max_favicon_links = 999

    meta = get_page_metadata(max_favicon_links=max_favicon_links)

    # Build HTML and text output tokens.
    html_tokens = []
    text_tokens = []

    if format == "obsidian":
        if meta.favicons:
            html_tokens.append(f'<img src={meta.favicons[0].href} width={FAVICON_WIDTH} />')
            text_tokens.append(f'![favicon|{FAVICON_WIDTH}]({meta.favicons[0].href})')

        # Make title without square brackets.
        title = f'{meta.host} {meta.title}'
        title = title.replace('[','(').replace(']',')')

        html_tokens.append(f'<a href="{meta.url}">{title}</a>')
        text_tokens.append(f'[{title}]({meta.url})') 
    elif format == "github":
        # Make title without square brackets.
        title = f'{meta.title}'
        title = title.replace('[','(').replace(']',')')

        html_tokens.append(f'<a href="{meta.url}">{title}</a>')
        text_tokens.append(f'[{title}]({meta.url})') 
    elif format == "jira":
        # Make title without pipes.
        title = f'{meta.title}'
        title = title.replace('|','-')

        html_tokens.append(f'<a href="{meta.url}">{title}</a>')
        text_tokens.append(f'[{title}|{meta.url}]') 
    else:
        html_tokens.append(f'Format "{format}" is not supported.')
        text_tokens.append(f'Format "{format}" is not supported.')

    # Build HTML and text output strings.
    html_markdown = "".join(html_tokens)
    text_markdown = "".join(text_tokens)

    # Copy the text_markdown to the clipboard.
    pyperclip.copy(text_markdown)

    template = template_env.get_template('markdown.html')
    rendered_html = template.render({
        "html_markdown": html_markdown,
        "text_markdown": text_markdown,
    })
    resp = make_response(rendered_html)

    return resp


if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0", port=8532)

"""
# Create a BeautifulSoup object
soup = BeautifulSoup(html_content, 'html.parser')

# Extract all text from the HTML including script tags
texts = [text for text in soup.find_all(text=True)]

# Extract all text from script tags
script_texts = [script.string for script in soup.find_all('script') if script.string]

# Concatenate and filter out None and empty strings
all_texts = texts + script_texts
filtered_all_texts = [text.strip() for text in all_texts if text.strip()]

# Output the texts
filtered_all_texts

"""