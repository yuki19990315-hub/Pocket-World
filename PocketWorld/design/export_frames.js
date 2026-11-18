/* Export the six illustrated world stages as circular SVG previews.
 * Usage: node PocketWorld/design/export_frames.js <output-directory>
 * SVGs embed the actual PNG scene art. No browser or external package is needed.
 */
const fs = require("node:fs");
const path = require("node:path");
const destination = process.argv[2];
if (!destination) throw new Error("Output directory is required");
fs.mkdirSync(destination, { recursive: true });

for (const world of ["city", "forest", "aquarium", "nature", "hybrid", "fantasy"]) {
  const png = {};
  for (const stage of ["young", "mature"]) {
    png[stage] = fs.readFileSync(path.join(__dirname, "assets", `${world}-${stage}.png`)).toString("base64");
  }
  for (const day of [0, 14, 30]) {
    const opacity = day / 30;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="0 0 240 240" shape-rendering="crispEdges">
<defs><clipPath id="screen"><circle cx="120" cy="120" r="119"/></clipPath></defs>
<g clip-path="url(#screen)">
<image href="data:image/png;base64,${png.young}" width="240" height="240"/>
<image href="data:image/png;base64,${png.mature}" width="240" height="240" opacity="${opacity}"/>
</g><circle cx="120" cy="120" r="119" stroke="#ffffff38" stroke-width="1.2" fill="none"/></svg>`;
    fs.writeFileSync(path.join(destination, `${world}-day${day}.svg`), svg);
  }
}
console.log("Exported 18 illustrated SVG world frames to " + destination);
