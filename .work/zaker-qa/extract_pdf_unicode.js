const fs = require("node:fs");
const zlib = require("node:zlib");

const input = process.argv[2];
const output = process.argv[3];
if (!input || !output) throw new Error("Pass input PDF and output text paths.");
const source = fs.readFileSync(input);
const raw = source.toString("latin1");
const streams = new Map();
const objects = new Map();

const objectRE = /(\d+)\s+\d+\s+obj\b([\s\S]*?)endobj/g;
let objectMatch;
while ((objectMatch = objectRE.exec(raw))) objects.set(Number(objectMatch[1]), objectMatch[2]);

const streamRE = /(\d+)\s+\d+\s+obj\b([\s\S]*?)stream\r?\n([\s\S]*?)\r?\nendstream/g;
let streamMatch;
while ((streamMatch = streamRE.exec(raw))) {
  let data = Buffer.from(streamMatch[3], "latin1");
  if (/\/FlateDecode\b/.test(streamMatch[2])) {
    try { data = zlib.inflateSync(data); } catch { continue; }
  }
  streams.set(Number(streamMatch[1]), data.toString("latin1"));
}

function utf16beHex(hex) {
  const bytes = Buffer.from(hex.replace(/\s+/g, ""), "hex");
  let result = "";
  for (let i = 0; i + 1 < bytes.length; i += 2) result += String.fromCharCode(bytes.readUInt16BE(i));
  return result;
}
function parseCMap(text) {
  const map = new Map();
  const lengths = new Set();
  for (const block of text.matchAll(/begincodespacerange([\s\S]*?)endcodespacerange/g)) {
    for (const pair of block[1].matchAll(/<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g)) {
      lengths.add(pair[1].length);
    }
  }
  for (const block of text.matchAll(/beginbfchar([\s\S]*?)endbfchar/g)) {
    for (const pair of block[1].matchAll(/<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g)) {
      map.set(pair[1].toUpperCase(), utf16beHex(pair[2]));
    }
  }
  for (const block of text.matchAll(/beginbfrange([\s\S]*?)endbfrange/g)) {
    const rowRE = /<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<([0-9A-Fa-f]+)>|\[([\s\S]*?)\])/g;
    let row;
    while ((row = rowRE.exec(block[1]))) {
      const start = BigInt("0x" + row[1]);
      const end = BigInt("0x" + row[2]);
      const sourceWidth = row[1].length;
      if (row[5] !== undefined) {
        const destinations = [...row[5].matchAll(/<([0-9A-Fa-f]+)>/g)].map(x => x[1]);
        for (let i = 0n; start + i <= end && Number(i) < destinations.length; i++) {
          const code = (start + i).toString(16).toUpperCase().padStart(sourceWidth, "0");
          map.set(code, utf16beHex(destinations[Number(i)]));
        }
      } else {
        const destination = BigInt("0x" + row[4]);
        const destWidth = row[4].length;
        for (let code = start; code <= end; code++) {
          const offset = code - start;
          const codeHex = code.toString(16).toUpperCase().padStart(sourceWidth, "0");
          const destHex = (destination + offset).toString(16).toUpperCase().padStart(destWidth, "0");
          map.set(codeHex, utf16beHex(destHex));
        }
      }
    }
  }
  return { map, lengths: [...lengths].sort((a, b) => b - a) };
}

const fontMaps = new Map();
for (const [objectId, body] of objects) {
  if (!/\/Type\s*\/Font\b/.test(body)) continue;
  const ref = body.match(/\/ToUnicode\s+(\d+)\s+\d+\s+R/);
  if (ref && streams.has(Number(ref[1]))) fontMaps.set(objectId, parseCMap(streams.get(Number(ref[1]))));
}
const tagToFont = new Map();
for (const body of objects.values()) {
  for (const fontBlock of body.matchAll(/\/Font\s*<<([\s\S]*?)>>/g)) {
    for (const ref of fontBlock[1].matchAll(/\/(\S+)\s+(\d+)\s+\d+\s+R/g)) {
      const tag = ref[1];
      const fontId = Number(ref[2]);
      if (fontMaps.has(fontId) && !tagToFont.has(tag)) tagToFont.set(tag, fontId);
    }
  }
}

const allMaps = [...fontMaps.values()];
function decodeHex(hex, fontMap) {
  const clean = hex.replace(/\s+/g, "").toUpperCase();
  const map = fontMap?.map || new Map();
  const lengths = fontMap?.lengths?.length ? fontMap.lengths : [...new Set(allMaps.flatMap(x => x.lengths))].sort((a, b) => b - a);
  let result = "";
  for (let i = 0; i < clean.length;) {
    let found = false;
    for (const size of lengths) {
      const code = clean.slice(i, i + size);
      if (code.length === size && map.has(code)) {
        result += map.get(code);
        i += size;
        found = true;
        break;
      }
    }
    if (!found) {
      const fallback = allMaps.find(x => x.map.has(clean.slice(i, i + 4)))?.map;
      if (fallback) { result += fallback.get(clean.slice(i, i + 4)); i += 4; }
      else { result += "�"; i += Math.min(4, clean.length - i); }
    }
  }
  return result;
}
function decodeLiteral(value, fontMap) {
  const bytes = [];
  for (let i = 0; i < value.length; i++) {
    if (value[i] !== "\\") { bytes.push(value.charCodeAt(i) & 255); continue; }
    i++;
    if (i >= value.length) break;
    if (/[0-7]/.test(value[i])) {
      let octal = value[i];
      for (let n = 0; n < 2 && i + 1 < value.length && /[0-7]/.test(value[i + 1]); n++) octal += value[++i];
      bytes.push(parseInt(octal, 8));
    } else {
      const escaped = value[i];
      const mapped = { n: 10, r: 13, t: 9, b: 8, f: 12, "(": 40, ")": 41, "\\": 92 };
      if (escaped === "\r" && value[i + 1] === "\n") i++;
      else if (escaped === "\n" || escaped === "\r") {}
      else bytes.push(mapped[escaped] ?? escaped.charCodeAt(0));
    }
  }
  return decodeHex(Buffer.from(bytes).toString("hex"), fontMap);
}
function decodeArray(arrayBody, fontMap) {
  let result = "";
  const tokenRE = /\(((?:\\.|[^\\)])*)\)|<([0-9A-Fa-f\s]+)>/g;
  let token;
  while ((token = tokenRE.exec(arrayBody))) {
    result += token[2] !== undefined ? decodeHex(token[2], fontMap) : decodeLiteral(token[1], fontMap);
  }
  return result;
}

const textStreams = [];
for (const [objectId, content] of streams) {
  if (!/\bBT\b/.test(content)) continue;
  const pieces = [];
  for (const block of content.matchAll(/\bBT\b([\s\S]*?)\bET\b/g)) {
    const body = block[1];
    const fontUses = [...body.matchAll(/\/(\S+)\s+[\d.]+\s+Tf/g)];
    const tag = fontUses.length ? fontUses[fontUses.length - 1][1] : null;
    const fontMap = tag && tagToFont.has(tag) ? fontMaps.get(tagToFont.get(tag)) : null;
    for (const array of body.matchAll(/\[((?:\\.|[^\]])*)\]\s*TJ/g)) pieces.push(decodeArray(array[1], fontMap));
    for (const single of body.matchAll(/\(((?:\\.|[^\\)])*)\)\s*Tj/g)) pieces.push(decodeLiteral(single[1], fontMap));
    for (const single of body.matchAll(/<([0-9A-Fa-f\s]+)>\s*Tj/g)) pieces.push(decodeHex(single[1], fontMap));
  }
  if (pieces.length) textStreams.push({ objectId, text: pieces.join("\n") });
}

const report = textStreams.map((stream, index) => `--- PDF text stream ${index + 1} (object ${stream.objectId}) ---\n${stream.text}`).join("\n\n");
fs.writeFileSync(output, report, "utf8");
const totalChars = [...report].filter(ch => !/\s|�/.test(ch)).length;
console.log(JSON.stringify({ inputBytes: source.length, textStreams: textStreams.length, fontMaps: fontMaps.size, fontTags: tagToFont.size, outputBytes: Buffer.byteLength(report), readableCharacters: totalChars, output }));
