// b is the baseURL
var b = new URL("http://localhost:8532/omd");

// gf is getFaviconLinks function
const gf = k =>
    Array.from(k).filter(k =>
        /icon|apple-touch-icon|shortcut icon/.test(k.rel)
    ).map(k => ({ rel: k.rel, href: k.href, sizes: k.sizes }));

// Build query parameters.
var p=new URLSearchParams();
p.append("url",document.URL);
p.append("title",document.title);

// ks is the list of favicon links in the document
var ks = gf(document.getElementsByTagName("link"));
for (const k of ks) {
    // ks2 is the query parameter string for the link
    ks2 = k.rel + "~" + k.href + "~" + k.sizes;
    p.append("favicon",ks2);
}
b.search=p.toString();
console.log(b.toString());

w=window.open(b.toString(),"","");
