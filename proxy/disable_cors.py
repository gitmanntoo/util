from mitmproxy import http

def response(flow: http.HTTPFlow) -> None:
    # Add headers to responses to disable CORS
    flow.response.headers["Access-Control-Allow-Origin"] = "*"
    flow.response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
    flow.response.headers["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
    flow.response.headers["Access-Control-Allow-Credentials"] = "true"

    # Delete other content control headers.
    flow.response.headers.pop("Content-Security-Policy",None)
    flow.response.headers.pop("Cross-Origin-Opener-Policy",None)

if __name__ == "__main__":
    print("Usage: mitmproxy -s disable_cors.py")