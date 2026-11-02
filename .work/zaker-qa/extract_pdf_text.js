const fs = require("node:fs");
const zlib = require("node:zlib");
const input = process.argv[2];
const output = process.argv[3];
if (!input || !output) throw new Error("Pass input PDF and output text paths.");
const source = fs.readFileSync(input);
const latin = source.toString("latin1");
const objectPattern = /(\d+)\s+(\d+)\s+obj\b([\s\S]*?)stream\r?\n([\s\S]*?)\r?\nendstream/g;
const pageTexts = [];
function decodeLiteral(value) {
  return value.replace(/\\([0-7]{1,3}|.)/g, (_, escaped) => {
    if (/^[0-7]{1,3}$/.test(escaped)) return String.fromCharCode(parseInt(escaped, 8));
    return ({ n: "\n", r: "\r", t: "\t", b: "\b", f: "\f", "(": "(", ")": ")", "\\": "\\" })[escaped] ?? escaped;
  });
}
let match;
while ((match = objectPattern.exec(latin))) {
  let bytes = Buffer.from(match[4], "latin1");
  if (/\/FlateDecode\b/.test(match[3])) {
    try { bytes = zlib.inflateSync(bytes); } catch { continue; }
  }
  const content = bytes.toString("latin1");
  if (!/\bBT\b/.test(content)) continue;
  const pieces = [];
  for (const block of content.matchAll(/\bBT\b([\s\S]*?)\bET\b/g)) {
    const body = block[1];
    for (const array of body.matchAll(/\[((?:\\.|[^\]])*)\]\s*TJ/g)) {
      const strings = [...array[1].matchAll(/\(((?:\\.|[^\\)])*)\)/g)].map(x => decodeLiteral(x[1]));
      if (strings.length) pieces.push(strings.join(""));
    }
    for (const single of body.matchAll(/\(((?:\\.|[^\\)])*)\)\s*Tj/g)) pieces.push(decodeLiteral(single[1]));
  }
  if (pieces.length) pageTexts.push({ object: Number(match[1]), text: pieces.join("\n") });
}
const text = pageTexts.map((p, i) => `--- PDF text stream ${i + 1} (object ${p.object}) ---\n${p.text}`).join("\n\n");
fs.writeFileSync(output, text, "utf8");
console.log(JSON.stringify({bytes: source.length, streams: pageTexts.length, textBytes: Buffer.byteLength(text), output}));
