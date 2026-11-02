const fs = require("node:fs");
const input = process.argv[2];
const raw = fs.readFileSync(input).toString("latin1");
const objects = new Map();
const objectRE = /(\d+)\s+\d+\s+obj\b([\s\S]*?)endobj/g;
let m;
while ((m = objectRE.exec(raw))) objects.set(Number(m[1]), m[2]);
const streamIds = new Set();
const streamRE = /(\d+)\s+\d+\s+obj\b[\s\S]*?stream\r?\n[\s\S]*?\r?\nendstream/g;
while ((m = streamRE.exec(raw))) streamIds.add(Number(m[1]));
const fonts = [];
const cmapRefs = [];
const objectStreams = [];
for (const [id, body] of objects) {
  if (/\/Type\s*\/Font\b/.test(body)) {
    const refs = [...body.matchAll(/\/ToUnicode\s+(\d+)\s+\d+\s+R/g)].map(x => Number(x[1]));
    fonts.push({fontObject:id, toUnicodeRefs:refs, refsHaveStream:refs.map(x=>streamIds.has(x))});
  }
  for (const ref of body.matchAll(/\/ToUnicode\s+(\d+)\s+\d+\s+R/g)) cmapRefs.push({owner:id,cmap:Number(ref[1]),hasStream:streamIds.has(Number(ref[1]))});
  if (/\/Type\s*\/ObjStm\b/.test(body)) objectStreams.push(id);
}
console.log(JSON.stringify({objectCount:objects.size,streamCount:streamIds.size,fontObjects:fonts,cmapRefs,objectStreams,rawCounts:{toUnicode:(raw.match(/\/ToUnicode/g)||[]).length,fonts:(raw.match(/\/Type\s*\/Font\b/g)||[]).length}},null,2));
