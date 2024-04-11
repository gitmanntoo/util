// This script extracts the page url, title, and favicon links
// and sends them to the server for processing to create a markdown link.

// b is the baseURL
var b = new URL("http://localhost:8532/pdf");
var p=new URLSearchParams();

// Build query parameters.
p.append("url",document.URL);
p.append("title",document.title);

b.search=p.toString();
console.log(b.toString());

w=window.open(b.toString(),"","");
