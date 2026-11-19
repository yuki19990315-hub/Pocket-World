/* Make device-ready, big-endian RGB565 images from the illustrated PNG set.
 * Usage: node PocketWorld/tools/build_display_assets.js
 * Needs 'sharp' at build time only. Device runtime uses .dat and no decoder.
 */
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');

const design = path.join(__dirname, '..', 'design', 'assets');
const output = path.join(__dirname, '..', 'firmware', 'assets');
const bundle = path.join(__dirname, '..', '..', 'SannyCompanionAndroid', 'app', 'src', 'main', 'assets', 'world_pack');
const worlds = ['nature', 'city', 'hybrid', 'fantasy', 'forest', 'aquarium', 'river', 'deepsea'];
const phases = world => world === 'hybrid' ? ['young', 'mid', 'mature'] : ['young', 'mature'];

async function rgb565(input, destination) {
  const {data, info} = await sharp(input).removeAlpha().raw().toBuffer({resolveWithObject: true});
  if (info.width !== 240 || info.height !== 240 || info.channels !== 3) {
    throw Error(`${input}: expected a 240x240 RGB image`);
  }
  const pixels = Buffer.alloc(240 * 240 * 2);
  for (let i = 0, j = 0; i < data.length; i += 3, j += 2) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    pixels[j] = (r & 0xf8) | (g >> 5);
    pixels[j + 1] = ((g & 0x1c) << 3) | (b >> 3);
  }
  fs.writeFileSync(destination, pixels);
  return pixels.length;
}

async function main() {
  fs.mkdirSync(output, {recursive: true});
  fs.mkdirSync(bundle, {recursive: true});
  let total = 0;
  for (const world of worlds) for (const stage of phases(world)) {
    const name = `${world}-${stage}`;
    const png = path.join(design, name + '.png');
    const dat = path.join(output, name + '.dat');
    total += await rgb565(png, dat);
    fs.copyFileSync(png, path.join(bundle, name + '.png'));
    fs.copyFileSync(dat, path.join(bundle, name + '.dat'));
  }
  fs.copyFileSync(path.join(__dirname, '..', 'www', 'index.html'), path.join(bundle, 'index.html'));
  // Deploy dashboard last, so a partial transfer leaves the previous UI active.
  const names = [...worlds.flatMap(w => phases(w).flatMap(s => [`${w}-${s}.dat`, `${w}-${s}.png`])), 'index.html'];
  fs.writeFileSync(path.join(bundle, 'manifest.txt'), names.join('\n') + '\n');
  console.log(`Built ${(names.length - 1) / 2} device frames (${total} bytes RGB565); packaged ${names.length} update files`);
}
main().catch(err => {console.error(err); process.exitCode = 1;});
