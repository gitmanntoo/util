// This script copies details about the page into the clipboard.
var b = new URL("http://localhost:8532/pdf");

var p = new URLSearchParams();
p.append("mode","text");
p.append("url",document.URL);
p.append("title",document.title);

// Copy the page HTML and URL to the clipboard.
var c = {
    url: document.URL,
    html: document.documentElement.outerHTML,
};
navigator.clipboard.writeText(JSON.stringify(c)).then(function() {
    // alert('Page HTML copied to clipboard.');
}, function(err) {
    console.error('Could not copy text: ', err);
    p.append("error",err);
});

b.search=p.toString();
console.log(b.toString());

w=window.open(b.toString(),"","");
