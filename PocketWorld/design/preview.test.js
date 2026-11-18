/* Run with: node PocketWorld/design/preview.test.js
 * Headless DOM + canvas smoke test for the separate World Design preview.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

class MockElement {
  constructor() {
    this.children = [];
    this.listeners = {};
    this.dataset = {};
    this.attributes = {};
    this.value = "0";
    this.textContent = "";
    this.classList = {
      toggle: (name, enabled) => {
        this.selected = name === "selected" && enabled;
      }
    };
  }
  addEventListener(type, callback) { this.listeners[type] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
  replaceChildren() { this.children = []; }
  appendChild(child) { this.children.push(child); }
  click() { assert.ok(this.listeners.click, "button must have click handler"); this.listeners.click(); }
}

const nodes = {};
const ids = [
  "world", "world-name", "world-description", "day-label", "day",
  "play", "plus-day", "plus-week", "stat-label-a", "stat-label-b",
  "stat-a", "stat-b", "events"
];
for (const id of ids) nodes[id] = new MockElement();
const modes = ["city", "forest", "aquarium", "nature", "hybrid", "fantasy"]
  .map((name) => { const node = new MockElement(); node.dataset.world = name; return node; });

let drawCount = 0;
const canvasContext = {
  fillRect(x, y, width, height) {
    assert.ok([x, y, width, height].every(Number.isFinite), "invalid pixel coordinate");
    drawCount++;
  },
  beginPath() {}, arc(x, y, radius) {
    assert.ok([x, y, radius].every(Number.isFinite), "invalid circle");
  },
  ellipse(x, y, rx, ry) {
    assert.ok([x, y, rx, ry].every(Number.isFinite), "invalid ellipse");
  },
  moveTo() {}, lineTo() {}, closePath() {}, clip() {}, fill() {}, stroke() {},
  save() {}, restore() {}, clearRect() {}
};
nodes.world.getContext = () => canvasContext;

const callbacks = [];
const document = {
  getElementById(id) { assert.ok(nodes[id], "unknown element " + id); return nodes[id]; },
  querySelectorAll(selector) {
    assert.equal(selector, "[data-world]");
    return modes;
  },
  createElement(tag) {
    assert.ok(tag === "li" || tag === "small");
    return new MockElement();
  }
};
const js = fs.readFileSync(path.join(__dirname, "preview.js"), "utf8");
const source = fs.readFileSync(path.join(__dirname, "preview.html"), "utf8");
assert.match(source, /<canvas id="world" width="120" height="120"/);
assert.match(source, /<script src="preview.js"><\/script>/);

vm.runInNewContext(js, { document, Math, console, requestAnimationFrame: (fn) => callbacks.push(fn) });
assert.equal(nodes["world-name"].textContent, "街の世界");
assert.equal(nodes["stat-a"].textContent, "1");
assert.ok(drawCount > 0);

nodes.day.listeners.input({ target: { value: "7" } });
assert.equal(nodes["day-label"].textContent, "DAY 7");
assert.ok(Number(nodes["stat-a"].textContent) > 1);
assert.ok(nodes.events.children.some((x) => x.children[0].textContent === "DAY 7"));

for (const mode of modes) {
  const before = drawCount;
  mode.click();
  assert.equal(mode.attributes["aria-pressed"], "true");
  assert.ok(drawCount > before, "scene " + mode.dataset.world + " did not paint");
  assert.ok(nodes["world-name"].textContent.length > 0);
}
nodes["plus-week"].click();
assert.equal(nodes["day-label"].textContent, "DAY 14");
nodes["plus-day"].click();
assert.equal(nodes["day-label"].textContent, "DAY 15");
nodes.play.click();
assert.match(nodes.play.textContent, /停止/);
assert.ok(callbacks.length > 0);
callbacks.shift()(1000);
callbacks.shift()(1100);
assert.ok(nodes.day.value >= 15);
nodes.play.click();
assert.match(nodes.play.textContent, /自動成長/);
console.log("Pocket World design preview: 6 scenes, timeline, events, controls OK");
