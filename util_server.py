#!/usr/bin/env python3
from collections import namedtuple
from urllib.parse import urlparse, urljoin, urlsplit, urlunsplit, urlunparse
from flask import Flask, request

app = Flask(__name__)


@app.route('/')
def read_root():
    return "Hello, World!"

@app.route('/mirror')
def request_mirror():
    """Mirror request details back to response as plain text."""

    # Build output lines.
    out = [
        f"{request.method} {request.path} {request.scheme}",
        "",
    ]

    out.append("HEADERS")
    for k,v in request.headers.items():
        out.append(f"{k}: {v}")
    out.append("")

    out.append(f"QUERY: {request.query_string}")
    query = request.args.to_dict(flat=False)
    for k,v in query.items():
        out.append(f"{k}: {v}")
    out.append("")

    out.append("DATA:")
    out.append(f"{request.get_data()}")

    return "<pre>{}</prd>".format("\n".join(out))

"""
javascript:p=trustedTypes.createPolicy('myPolicy',{createHTML: (input) => input}); u=new URL(document.URL); u.search=""; t=u.hostname+": "+document.title;  h=p.createHTML("<pre>["+t+"]("+u.toString()+")<pre>"); w=window.open("","",""); w.document.title="MD "+t; w.document.body.innerHTML=h;

javascript:b=new URL("http://localhost:8532/markdown");gf=function(){for(var t=document.getElementsByTagName("link"),e=0;e<t.length;e++)if("icon"==t[e].getAttribute("rel")||"shortcut icon"==t[e].getAttribute("rel"))return t[e].getAttribute("href")};p=new URLSearchParams();p.append("url",document.URL);p.append("title",document.title);p.append("favicon",gf());b.search=p.toString();w=window.open(b.toString(),"","");
"""

# Map of netloc and title_suffix. If match found, use alias.
ALIAS_MAP = {
    # Google
    "mail.google.com": {
        " - Gmail": "Gmail",
    },
    "docs.google.com": {
        " - Google Docs": "Google Docs",
        " - Google Sheets": "Google Sheets",
        " - Google Slides": "Google Slides",
    },
    "drive.google.com": {
        " - Google Drive": "Google Drive",
    },

    # Others
    "chat.openai.com": {
        "": "ChatGPT",
    },
    "www.coursera.org": {
        " | Coursera": "Coursera",
    },
    "developer.mozilla.org": {
        " | MDN": "MDN",
    },
    "stackoverflow.com": {
        " - Stack Overflow": "Stack Overflow",
    },
}

URLTuple = namedtuple("URLTuple", [
    "scheme",
    "netloc",
    "path",
    "params",
    "query",
    "fragment",
])

IMAGE_TYPES = [
    "gif",
    "ico",
    "jpeg",
    "png",
    "svg",
]

@app.route('/markdown')
def make_markdown():
    """Make a markdown link.

    Parameters:
    - dialect: str -- Markdown dialect. Default: obsidian
    - url: str -- URL of source page
    - title: str -- Title of source page
    - favicon: str -- URL of favicon from source page
    """

    # Read query parameters.
    dialect = request.args.get("dialect","obsidian")
    url = request.args.get("url","")
    title = request.args.get("title","")
    favicon = request.args.get("favicon","")

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
    final_favicon = ""
    if favicon:
        favicon_url = urlparse(favicon)
        if favicon_url.netloc == "" or favicon_url.netloc == parsed_url.netloc:
            favicon_url = urlparse(urljoin(parsed_url.geturl(), favicon_url.geturl()))
                                   
        tokens = favicon_url.path.rsplit(".", 1)
        if len(tokens) == 2 and tokens[1] in IMAGE_TYPES:
            favicon_url = urlparse(urljoin(favicon_url.geturl(), favicon_url.path))

        final_favicon = favicon_url.geturl()

    # Build markdown link.
    final_markdown = ""
    if favicon:
        final_markdown = f"![favicon|20]({final_favicon}) "
    final_markdown += f"[{final_title}]({final_url})"

    # out = [
    #     f"{favicon=}",
    #     f"{favicon_url.geturl()}",
    #     f"{favicon_url.netloc}",
    #     f"{final_markdown=}",
    # ]

    return "<pre>{}</prd>".format(final_markdown)


if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0", port=8532)
