const fs = require("node:fs");
const zlib = require("node:zlib");
const file = process.argv[2];
const bytes = fs.readFileSync(file);
const raw = bytes.toString("latin1");
const streamRE = /(\d+)\s+\d+\s+obj\b([\s\S]*?)stream\r?\n([\s\S]*?)\r?\nendstream/g;
const summaries = [];
let match;
while ((match = streamRE.exec(raw))) {
  let data = Buffer.from(match[3], "latin1");
  if (/\/FlateDecode\b/.test(match[2])) {
    try { data = zlib.inflateSync(data); } catch { continue; }
  }
  const text = data.toString("latin1");
  if (!/\bBT\b/.test(text)) continue;
  const count = (re) => (text.match(re) || []).length;
  summaries.push({
    object: Number(match[1]), bytes: data.length,
    textBlocks: count(/\bBT\b/g),
    showText: count(/\bTj\b/g),
    showTextArray: count(/\bTJ\b/g),
    hexTextOps: count(/<[0-9a-fA-F\s]+>\s*Tj/g),
    literalTextOps: count(/\([^\n]*?\)\s*Tj/g),
  });
}
console.log(JSON.stringify({
  bytes: bytes.length,
  pages: (raw.match(/\/Type\s*\/Page\b/g) || []).length,
  flateStreams: (raw.match(/FlateDecode/g) || []).length,
  toUnicodeMaps: (raw.match(/\/ToUnicode/g) || []).length,
  fontDictionaries: (raw.match(/\/Type\s*\/Font/g) || []).length,
  textStreams: summaries,
}, null, 2));
