#!/usr/bin/env python3
import os
import json
from pathlib import Path
from collections import namedtuple
import re
from urllib.parse import urlparse, urljoin, urlsplit, urlunsplit, urlunparse

import fitz
from flask import Flask, abort, make_response, render_template, request, send_file, send_from_directory
import jsmin
from playwright.sync_api import sync_playwright
import yaml

from bs4 import BeautifulSoup


app = Flask(__name__)

STATIC_DIR = Path("static")
SIZE_REGEX = re.compile(r'\b(\d+)x(\d+)\b')

@app.route('/')
def read_root():
    return "Hello, World!"


@app.route('/javascript/<filename>.js')
def serve_js(filename):
    """
    Serves javascript files from the static directory.
    
    If the url contains "minify=true" or "bookmarklet=true", the file will be
    minified and/or converted into a bookmarklet.
    """
    # Ensure the filename does not contain path traversals
    if '..' in filename or filename.startswith('/'):
        abort(404)  # Not found

    # Read options
    query = request.args.to_dict(flat=True)
    minify = query.get("minify", "false") == "true"
    bookmarklet = query.get("bookmarklet", "false") == "true" 
    
    # Define the path to the static directory
    # static_dir = os.path.join(app.root_path, STATIC_DIR)

    # Read the contents of the file
    try:
        with open(STATIC_DIR / "javascript" / f"{filename}.js", "r") as f:
            contents = f.read()
    except FileNotFoundError:
        abort(404)  # Not found if the file does not exist

    # Minify the contents if set.
    if minify or bookmarklet:
        contents = jsmin.jsmin(contents).strip()

    # Add a bookmarklet if set.
    if bookmarklet:
        contents = f"javascript:(function(){{{contents}}})();"

    # Return the contents
    response = make_response(contents)
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


def largest_favicon_link(favicon_links):
    """Get the largest favicon link from a list of links. 
    Each item in the favicon_links must be a dictionary with keys "rel", "href", and "sizes".
    """

    favicon_link = None
    favicon_width = None
    favicon_height = None

    for link in favicon_links:
        link_rel = link.get('rel')
        link_href = link.get('href')
        link_sizes = link.get('sizes')

        #  Skip if link is missing 'rel' or 'href'.
        if not link_href or not link_rel:
            continue

        if not link_rel in ("shortcut icon","icon","apple-touch-icon"):
            continue

        # Get size from 'sizes' attribute.
        if link_sizes:
            m = SIZE_REGEX.search(link_sizes)
            if m:
                width,height = [int(x) for x in m.groups()]
                if favicon_link is None or (width > favicon_width or height > favicon_height):
                    favicon_link = link_href
                    favicon_width = width
                    favicon_height = height
                    continue

        # Get size from 'href' attribute.
        m = SIZE_REGEX.search(link_href)
        if m:
            width,height = [int(x) for x in m.groups()]
            if favicon_link is None or (width > favicon_width or height > favicon_height):
                favicon_link = link_href
                favicon_width = width
                favicon_height = height
                continue

        # If icon has no size, assume it is the largest.
        return link_href

    return favicon_link


@app.route('/mirror', methods=["POST"])
def mirror_post():
    """Save request details."""

    global mirror_url
    global mirror_request

    mirror_url = request.args.get("url")
    mirror_request = request_to_dict(request)

    response = make_response("OK")
    response.headers['Content-Type'] = 'text/plain'

    return response

# javascript: b=new URL("http://localhost:8532/mirror");p=new URLSearchParams();p.append("url",document.URL);b.search=p.toString();d={"html":document.documentElement.outerHTML};fetch(b.toString(),{method:'POST',headers:{'Content-Type':'application/json'},body: JSON.stringify(d)}).catch(e=>{console.error(e)});w=window.open(b.toString(),"","");

@app.route('/mirror', methods=["GET"])
def mirror_get():
    """Mirror request details back to response as plain text."""

    global mirror_url
    global mirror_request

    # Use the stored request if URL matches.
    if mirror_url is not None and mirror_url == request.args.get("url"):
        current_request = mirror_request
    else:
        current_request = request_to_dict(request)

    # Reset the stored request to free up memory.
    mirror_url = None
    mirror_request = None

    # Parse the HTML
    data_json = json.loads(current_request['data'])
    soup = BeautifulSoup(data_json.get('html',''), 'html.parser')
    page_title = soup.title.text

    # Build output lines.
    out = [
        f"URL: {current_request['url']}",
        f"TITLE: {page_title}",
        "",
    ]

    rel_links = soup.find_all("link")
    all_links = []
    for link in rel_links:
        new_link = {
            "rel": link.attrs.get('rel'),
            "href": link.attrs.get('href'),
            "sizes": link.attrs.get('sizes'),
        }
        all_links.append(new_link)

    favicon_link = largest_favicon_link(all_links)

    if favicon_link:
        # Handle relative URLs
        if favicon_link.startswith('/'):
            favicon_link = urljoin(current_request['url'], favicon_link)

        out.append(f"FAVICON: {favicon_link}")
    else:
        out.append(f"FAVICON: NONE")
    out.append("")

    # for rel_type 
    #     favicon_link = soup.find("link", rel=rel_type)
    #     if favicon_link and 'href' in favicon_link.attrs:
    #         out.append(f"FAVICON: {favicon_link}")

    # # If a favicon link is found, print its href attribute
    # favicon_href = "NOT FOUND"
    # if favicon_link and 'href' in favicon_link.attrs:
    #     favicon_href = favicon_link['href']
        

    out.append("HEADERS")
    for k,v in current_request['headers'].items():
        out.append(f"{k}: {v}")
    out.append("")

    out.append(f"QUERY: {current_request['query_string']}")
    for k,v in current_request['query'].items():
        out.append(f"{k}: {v}")
    out.append("")

    out.append("TEXT:")
    text_tuples = iterate_elements(soup)
    out.extend(["".join(x) for x in text_tuples])
    out.append("")

    out.append("HTML:")
    out.append(soup.prettify())
    out.append("")

    resp = make_response("\n".join(out))
    resp.headers["Content-Type"] = "text/plain"

    return resp


"""
javascript:p=trustedTypes.createPolicy('myPolicy',{createHTML: (input) => input}); u=new URL(document.URL); u.search=""; t=u.hostname+": "+document.title;  h=p.createHTML("<pre>["+t+"]("+u.toString()+")<pre>"); w=window.open("","",""); w.document.title="MD "+t; w.document.body.innerHTML=h;

javascript:b=new URL("http://localhost:8532/markdown");gf=function(){for(var t=document.getElementsByTagName("link"),e=0;e<t.length;e++)if("icon"==t[e].getAttribute("rel")||"shortcut icon"==t[e].getAttribute("rel"))return t[e].getAttribute("href")};p=new URLSearchParams();p.append("url",document.URL);p.append("title",document.title);p.append("favicon",gf());b.search=p.toString();w=window.open(b.toString(),"","");
"""

URLTuple = namedtuple("URLTuple", [
    "scheme",
    "netloc",
    "path",
    "params",
    "query",
    "fragment",
])

CONFIG = yaml.safe_load(open("util_server.yml"))
ALIAS_MAP = CONFIG.get("alias_map", {})
IMAGE_TYPES = CONFIG.get("image_types", [])
FAVICON_WIDTH = 20

@app.route('/md')
def make_obsidian_markdown():
    """Make a markdown link for an obsidian page.

    Parameters:
    - mode: str -- Mode for markdown format
        - default: "obsidian" consisting of ![favicon|20] [extended title](url)
        - "simple": simple markdown consisting of [title](url) without any modifications
        - "jira": JIRA format using pipe: [title|url]
    - url: str -- URL of source page
    - title: str -- Title of source page
    - favicon: str -- Repeated favicon links from source page. Consists of `~` delimited strings:
        - Example: <link.ref>~<link.href>~<link.sizes>
    """

    # Read query parameters.
    url = request.args.get("url","")
    title = request.args.get("title","")
    mode = request.args.get("mode","obsidian")

    query = request.args.to_dict(flat=False)
    favicon_links = []
    for f in query.get("favicon",[]):
        tokens = f.split("~")
        new_link = {
            "rel": tokens[0],
            "href": tokens[1],
            "sizes": tokens[2] if len(tokens) > 2 else "",
        }
        favicon_links.append(new_link)

    # Get largest favicon link.
    favicon_link = largest_favicon_link(favicon_links)

    # Parse URL
    parsed_url = urlparse(url)
    final_url = urlunparse(URLTuple(
        scheme=parsed_url.scheme,
        netloc=parsed_url.netloc,
        path=parsed_url.path,
        params="",
        query="",
        fragment=parsed_url.fragment,
    ))

    # Get suffix from title.
    title_tokens = [x.strip() for x in title.rsplit("|", 1)]
    if len(title_tokens) == 2:
        title_prefix = title_tokens[0]
        title_suffix = title_tokens[1]
    else:
        title_prefix = title
        title_suffix = ""

    # Lookup netloc and title_suffix to get alias for title.
    final_title = f"{parsed_url.netloc}: {title}"
    suffix_map = ALIAS_MAP.get(parsed_url.netloc,{})
    for suffix in suffix_map.keys():
        if suffix == "":
            final_title = f"{suffix_map[suffix]}: {title}"
        elif title.endswith(suffix):
            title = title[:-len(suffix)]
            final_title = f"{suffix_map[suffix]}: {title}"

    # If favicon path is an image, remove the search parameters.
    favicon_href = None
    if favicon_link:
        favicon_url = urlparse(favicon_link)
        if favicon_url.netloc == "" or favicon_url.netloc == parsed_url.netloc:
            favicon_url = urlparse(urljoin(parsed_url.geturl(), favicon_url.geturl()))
                                   
        tokens = favicon_url.path.rsplit(".", 1)
        if len(tokens) == 2 and tokens[1] in IMAGE_TYPES:
            favicon_url = urlparse(urljoin(favicon_url.geturl(), favicon_url.path))

        favicon_href = favicon_url.geturl()

    # Build markdown link.
    final_markdown = ""
    if mode == "github":
        # Replace square brackets with parentheses.
        title = title.replace('[','(').replace(']',')')
        final_markdown = f"[{title}]({final_url})"
    elif mode == "jira":
        # Replace pipe with square brackets.
        title = title.replace('|','-')
        final_markdown = f"[{title}|{final_url}]"
    else:
        # obsidian default for everything else
        if favicon_href:
            final_markdown += f"![favicon|{FAVICON_WIDTH}]({favicon_href}) "

        # Replace square brackets with parentheses.
        final_title = final_title.replace('[','(').replace(']',')')

        final_markdown += f"[{final_title}]({final_url})"

    ### DEBUGXXXXX: Print all variables
    # final_markdown = [
    #     f"{final_title=}",
    #     f"{final_url=}",
    #     f"{favicon_link=}",
    #     f"{favicon_href=}",
    #     f"{final_markdown=}",
    #     "",
    #     f"{favicon_links=}",
    # ]

    resp = make_response(final_markdown)
    resp.headers['Content-Type'] = 'text/plain'

    return resp


PDF_TMP_DIR = Path("tmp/pdf")
PDF_FILE = PDF_TMP_DIR / "output.pdf"
PDF_IMAGES_DIR = Path("tmp/pdf/images")

@app.route('/pdf/images/<filename>')
def get_pdf_images(filename):
    return send_from_directory(PDF_IMAGES_DIR, filename)


@app.route('/pdf')
def make_pdf():
    # Read query parameters.
    url = request.args.get("url","")
    if url == "":
        return "Error: No URL provided.", 400
    
    # Create the images directory if it doesn't exist.
    os.makedirs(PDF_IMAGES_DIR, exist_ok=True)

    # Optionally return HTML. Default is to return a PDF file.
    mode = request.args.get("mode","pdf")

    output_path = PDF_FILE

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Load the HTML file
        page.goto(url)
        
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

    if mode == "html":
        # Build a web page with text and images extracted from the PDF.
        # Open the PDF file
        pdf_document = fitz.open(output_path)

        # Extract text and images from the PDF and build a web page.
        html_parts = []

        for page_num in range(pdf_document.page_count):
            # Add page heading
            html_parts.append(f"<h1>Page {page_num + 1}</h1>")

            page = pdf_document.load_page(page_num)
            
            # Extract text from the page
            text = page.get_text("text")
            html_parts.append(f"<pre>{text}</pre>")

            # Extract images from the page
            image_list = page.get_images(full=True)
            for img in image_list:
                xref = img[0]

                pix = fitz.Pixmap(pdf_document, xref)
                pix_filename = f"image_{xref}.png"
                with open(PDF_IMAGES_DIR / pix_filename, "wb") as fp:
                    fp.write(pix.tobytes())

                html_parts.append(f'<img src="pdf/images/{pix_filename}">')

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



if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0", port=8532)
