/* Export deterministic stills of the separate canvas concept as vector paths.
 * Usage: node PocketWorld/design/export_frames.js <output-directory>
 * No external JS packages. Files are development visual references, not firmware.
 */
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const destination = process.argv[2];
if (!destination) throw new Error("Output directory is required");
fs.mkdirSync(destination, { recursive: true });

class Element {
  constructor() {
    this.listeners = {};
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.value = "0";
    this.textContent = "";
    this.classList = { toggle() {} };
  }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  setAttribute(name, value) { this.attributes[name] = value; }
  appendChild(node) { this.children.push(node); }
  replaceChildren() { this.children = []; }
  click() { this.listeners.click(); }
}

const esc = (value) => String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
class SvgCanvas {
  constructor() {
    this.ops = [];
    this.fillStyle = "#ffffff";
    this.strokeStyle = "#ffffff";
    this.lineWidth = 1;
    this.path = [];
    this.clipDepth = 0;
  }
  get frame() { return '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="0 0 120 120" shape-rendering="crispEdges"><defs><clipPath id="screen"><circle cx="60" cy="60" r="59"/></clipPath></defs>' + this.ops.join("") + "</svg>"; }
  clearRect() { this.ops = []; this.clipDepth = 0; }
  fillRect(x, y, w, h) {
    this.ops.push('<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" fill="' + esc(this.fillStyle) + '"/>');
  }
  beginPath() { this.path = []; }
  arc(x, y, r) { this.path.push({ kind: "circle", x, y, r }); }
  ellipse(x, y, rx, ry) { this.path.push({ kind: "ellipse", x, y, rx, ry }); }
  moveTo(x, y) { this.path.push({ kind: "move", x, y }); }
  lineTo(x, y) { this.path.push({ kind: "line", x, y }); }
  closePath() { this.path.push({ kind: "close" }); }
  pathSvg(fill, stroke) {
    return this.path.map((shape) => {
      const props = ' fill="' + esc(fill) + '" stroke="' + esc(stroke) + '"';
      if (shape.kind === "circle") return '<circle cx="' + shape.x + '" cy="' + shape.y + '" r="' + shape.r + '"' + props + '/>';
      if (shape.kind === "ellipse") return '<ellipse cx="' + shape.x + '" cy="' + shape.y + '" rx="' + shape.rx + '" ry="' + shape.ry + '"' + props + '/>';
      return null;
    }).filter(Boolean).join("") || '<path d="' + this.path.map((shape) => shape.kind === "close" ? "Z" : (shape.kind === "move" ? "M" : "L") + shape.x + " " + shape.y).join(" ") + '"' + ' fill="' + esc(fill) + '" stroke="' + esc(stroke) + '"/>';
  }
  fill() { this.ops.push(this.pathSvg(this.fillStyle, "none")); }
  stroke() { this.ops.push(this.pathSvg("none", this.strokeStyle)); }
  save() {}
  clip() { this.ops.push('<g clip-path="url(#screen)">'); this.clipDepth++; }
  restore() { if (this.clipDepth) { this.ops.push("</g>"); this.clipDepth--; } }
}

const context = new SvgCanvas();
const ids = ["world", "world-name", "world-description", "day-label", "day", "play", "plus-day", "plus-week", "stat-label-a", "stat-label-b", "stat-a", "stat-b", "events"];
const nodes = Object.fromEntries(ids.map((id) => [id, new Element()]));
nodes.world.getContext = () => context;
const modes = ["city", "forest", "aquarium", "nature", "hybrid", "fantasy"].map((name) => {
  const el = new Element(); el.dataset.world = name; return el;
});
const document = {
  getElementById: (id) => nodes[id],
  querySelectorAll: () => modes,
  createElement: () => new Element()
};
const script = fs.readFileSync(path.join(__dirname, "preview.js"), "utf8");
vm.runInNewContext(script, { document, Math, requestAnimationFrame() {} });
for (const mode of modes) {
  mode.click();
  for (const day of [0, 14, 30]) {
    nodes.day.listeners.input({ target: { value: String(day) } });
    const filename = path.join(destination, mode.dataset.world + "-day" + day + ".svg");
    fs.writeFileSync(filename, context.frame);
  }
}
console.log("Exported 18 SVG world design frames to " + destination);
