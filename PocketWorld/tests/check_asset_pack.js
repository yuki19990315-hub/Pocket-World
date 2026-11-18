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
const names = [];

(async () => {
  for (const scene of scenes) for (const phase of ['young','mature']) {
    const base = `${scene}-${phase}`;
    const png = path.join(root,'design','assets',base+'.png');
    const dat = path.join(root,'firmware','assets',base+'.dat');
    const info = await sharp(png).metadata();
    assert.equal(info.width,240,base);
    assert.equal(info.height,240,base);
    assert.equal(fs.statSync(dat).size,240*240*2,base);
    assert.deepEqual(fs.readFileSync(path.join(pack,base+'.png')),fs.readFileSync(png));
    assert.deepEqual(fs.readFileSync(path.join(pack,base+'.dat')),fs.readFileSync(dat));
    names.push(base+'.dat',base+'.png');
  }
  names.push('index.html');
  assert.deepEqual(fs.readFileSync(path.join(pack,'manifest.txt'),'utf8').trim().split('\n'),names);
  assert.deepEqual(fs.readFileSync(path.join(pack,'index.html')),fs.readFileSync(path.join(root,'www','index.html')));
  assert.ok(names.every(name=>fs.statSync(path.join(pack,name)).size<=128*1024));
  console.log(`Illustrated asset pack: ${scenes.length} scenes / ${names.length} OTA files verified`);
})().catch(error=>{console.error(error);process.exitCode=1;});
