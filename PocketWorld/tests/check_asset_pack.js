/* Verify that the Android offline pack and the ESP32's RGB565 assets
 * correspond exactly to the authored 240×240 illustrated scene set.
 * Run from the repository root: node PocketWorld/tests/check_asset_pack.js
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');

const root = path.join(__dirname, '..');
const pack = path.join(root, '..', 'SannyCompanionAndroid', 'app', 'src', 'main', 'assets', 'world_pack');
const scenes = ['nature','city','hybrid','fantasy','forest','aquarium','river','deepsea'];
const phases = scene => scene === 'hybrid' ? ['young','mid','mature'] : ['young','mature'];
const names = [];

(async () => {
  for (const scene of scenes) for (const phase of phases(scene)) {
    const base = `${scene}-${phase}`;
    const png = path.join(root,'design','assets',base+'.png');
    const dat = path.join(root,'firmware','assets',base+'.dat');
    const info = await sharp(png).metadata();
    assert.equal(info.width,240,base);
    assert.equal(info.height,240,base);
    if (scene === 'nature') {
      // Preserve the deliberately coarse 80x80 pixel grid on the 240px LCD.
      const {data, info: raw} = await sharp(png).removeAlpha().raw().toBuffer({resolveWithObject:true});
      for (let y = 0; y < 240; y += 3) for (let x = 0; x < 240; x += 3) {
        const start = (y * 240 + x) * raw.channels;
        for (let dy = 0; dy < 3; dy++) for (let dx = 0; dx < 3; dx++) {
          const offset = ((y + dy) * 240 + x + dx) * raw.channels;
          for (let c = 0; c < raw.channels; c++) {
            assert.equal(data[offset + c], data[start + c], `${base}: lost 3x3 pixel grid at ${x},${y}`);
          }
        }
      }
    }
    if (scene !== 'nature') {
      // The other seven scenes use a 120x120 logical pixel grid.
      const {data, info: raw} = await sharp(png).removeAlpha().raw().toBuffer({resolveWithObject:true});
      for (let y = 0; y < 240; y += 2) for (let x = 0; x < 240; x += 2) {
        const start = (y * 240 + x) * raw.channels;
        for (let dy = 0; dy < 2; dy++) for (let dx = 0; dx < 2; dx++) {
          const offset = ((y + dy) * 240 + x + dx) * raw.channels;
          for (let c = 0; c < raw.channels; c++) {
            assert.equal(data[offset + c], data[start + c], `${base}: lost 2x2 pixel grid at ${x},${y}`);
          }
        }
      }
    }
    assert.equal(fs.statSync(dat).size,240*240*2,base);
    assert.deepEqual(fs.readFileSync(path.join(pack,base+'.png')),fs.readFileSync(png));
    assert.deepEqual(fs.readFileSync(path.join(pack,base+'.dat')),fs.readFileSync(dat));
    names.push(base+'.dat',base+'.png');
  }
  names.push('index.html');
  assert.deepEqual(fs.readFileSync(path.join(pack,'manifest.txt'),'utf8').trim().split(/\r?\n/),names);
  assert.deepEqual(fs.readFileSync(path.join(pack,'index.html')),fs.readFileSync(path.join(root,'www','index.html')));
  assert.ok(names.every(name=>fs.statSync(path.join(pack,name)).size<=128*1024));
  console.log(`Illustrated asset pack: ${scenes.length} scenes / ${names.length} OTA files verified`);
})().catch(error=>{console.error(error);process.exitCode=1;});
