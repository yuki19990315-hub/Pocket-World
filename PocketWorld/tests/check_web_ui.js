// Headless logic smoke test: no real browser or network is required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../www/index.html'), 'utf8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(match, 'UI script exists');
const script = match[1];

function fakeNode(dataset = {}) {
  const classes = new Set();
  const listeners = {};
  return {
    dataset, textContent: '', innerHTML: '', hidden: false, disabled: false,
    classList: {
      add(x) { classes.add(x); },
      remove(x) { classes.delete(x); },
      toggle(x, on) { if (on) classes.add(x); else classes.delete(x); },
    },
    addEventListener(type, callback) { listeners[type] = callback; },
    click() { if (listeners.click) listeners.click(); },
    setAttribute() {}, replaceChildren() {},
    querySelectorAll() { return []; },
    getBoundingClientRect() { return {left: 0, top: 0, width: 360, height: 360}; },
  };
}

async function runPreview(world, area, liveState = false, illustrated = false) {
  const nodes = new Map();
  const worldButtons = ['nature', 'city', 'hybrid', 'fantasy', 'forest', 'aquarium']
    .map(id => fakeNode({world: id}));
  const areaButtons = ['river', 'ocean', 'deepsea'].map(id => fakeNode({area: id}));
  const phaseButtons = ['auto','dawn','day','dusk','night','lights_out']
    .map(id => fakeNode({phase: id}));
  const waterTabs = fakeNode();
  waterTabs.querySelectorAll = () => areaButtons;
  nodes.set('water-tabs', waterTabs);
  let drawn = 0;
  let translated = 0;
  let artworkDrawn = 0;
  const smallPixels = [];
  const paintColors = [];
  const context = {
    clearRect() {}, save() {}, restore() {}, beginPath() {}, arc() {}, clip() {},
    translate() { translated += 1; }, scale() {}, moveTo() {}, lineTo() {}, stroke() {},
    fillRect(x, y, width, height) {
      drawn += 1;
      paintColors.push(context.fillStyle);
      if (width === 1 && height === 1) smallPixels.push([x, y]);
    },
    drawImage() { artworkDrawn += 1; },
  };
  const canvas = fakeNode();
  canvas.getContext = () => context;
  nodes.set('world-canvas', canvas);
  const document = {
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, fakeNode()); return nodes.get(id); },
    querySelectorAll(selector) {
      if (selector === '.tab') return worldButtons;
      if (selector === '.water-tab') return areaButtons;
      if (selector === '.phase-btn') return phaseButtons;
      return [];
    },
    createElement() { return fakeNode(); },
  };
  let frame;
  const sandbox = {
    document, location: {search: '?world=' + world + '&area=' + area},
    URLSearchParams, Date, Math, AbortSignal,
    setTimeout() { return 1; }, clearTimeout() {}, setInterval() {},
    requestAnimationFrame(callback) { frame = callback; },
    ...(illustrated ? {Image: class { constructor() { this.complete = true; this.naturalWidth = 240; } }} : {}),
    fetch() {
      if (!liveState) return Promise.reject(new Error('deliberately offline'));
      const worlds = ['nature', 'city', 'hybrid', 'fantasy', 'forest', 'aquarium']
        .map(id => ({id, name: id, seed: 100, minutes: 0, weather: 'sunny',
          plants: 4, wildlife: 2, residents: 0, houses: 0, magic: 0,
          water_areas: id === 'aquarium' ? {
            river: {unlocked: true, plants: 6, fish: 2, shrimp: 1},
            ocean: {unlocked: false, plants: 2, fish: 2},
            deepsea: {unlocked: false, fish: 1, glow: 2},
          } : undefined}));
      return Promise.resolve({ok: true, json: async () => ({worlds,
        motion: {connected: true, tilt_x: 0.6, tilt_y: -0.3, shake_id: 0}})});
    },
  };
  vm.runInNewContext(script, sandbox);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(typeof frame, 'function');
  frame(1200);
  assert.ok(illustrated ? artworkDrawn > 0 : drawn > 50,
    'canvas draws the illustration or substantial procedural scene');
  if (illustrated && world === 'city') {
    assert.equal(smallPixels.length, 6, 'two 1x3 pedestrians use six native pixels');
    assert.match(nodes.get('stats').innerHTML, /<strong>2<\/strong><em>人<\/em>/);
    assert.match(nodes.get('stats').innerHTML, /<strong>1<\/strong><em>軒<\/em>/);
    paintColors.length = 0;
    phaseButtons.find(btn => btn.dataset.phase === 'night').click();
    frame(2600);
    assert.equal(nodes.get('day-phase').textContent, '🌙 夜・街灯点灯');
    assert.ok(paintColors.includes('#fff2b7'), 'cottage windows light up at night');
    paintColors.length = 0;
    phaseButtons.find(btn => btn.dataset.phase === 'lights_out').click();
    frame(3000);
    assert.equal(nodes.get('day-phase').textContent, '🌑 消灯・おやすみ');
    assert.ok(!paintColors.includes('#fff2b7'), 'lights switch off before bedtime');
  }
  assert.ok(nodes.get('world-title').textContent.length > 0);
  if (liveState) {
    assert.ok(translated > 0, 'onboard tilt moves the scene');
    assert.equal(nodes.get('motion-status').textContent, '傾きに反応中');
  }
  if (world === 'aquarium') {
    assert.equal(waterTabs.hidden, false);
    if (liveState) {
      assert.equal(areaButtons[0].disabled, false);
      assert.equal(areaButtons[1].disabled, true);
      assert.equal(areaButtons[2].disabled, true);
      assert.equal(nodes.get('world-title').textContent, '川の水槽');
    } else {
      assert.ok(areaButtons.every(node => !node.disabled), 'demo previews all 3 habitats');
      assert.equal(nodes.get('world-title').textContent, {
        river: '川の水槽', ocean: '海の水槽', deepsea: '深海の水槽',
      }[area]);
    }
  } else {
    assert.equal(waterTabs.hidden, true);
  }
}

(async () => {
  for (const [world, area] of [
    ['nature', 'river'], ['forest', 'river'], ['aquarium', 'river'],
    ['aquarium', 'ocean'], ['aquarium', 'deepsea'],
  ]) await runPreview(world, area);
  await runPreview('city', 'river', false, true);
  await runPreview('aquarium', 'deepsea', true);
  process.stdout.write('Pocket World UI: scene/lock/tiny resident smoke tests passed\n');
})().catch(error => { console.error(error); process.exitCode = 1; });
