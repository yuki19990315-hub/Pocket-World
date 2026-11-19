/* Align existing illustrated scenes to a 120x120 logical LCD pixel grid.
 * Pixel locations and composition are preserved (nearest-neighbour only).
 * Run: node PocketWorld/tools/pixelate_scene_assets.js city forest aquarium river deepsea
 * Then: node PocketWorld/tools/build_display_assets.js
 * Original illustrations remain recoverable from Git history.
 */
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');

const allowed = new Set(['city', 'fantasy', 'forest', 'aquarium', 'river', 'deepsea']);
const scenes = process.argv.slice(2);
const design = path.join(__dirname, '..', 'design', 'assets');

async function main() {
  if (!scenes.length || scenes.some(scene => !allowed.has(scene))) {
    throw Error('Specify one or more of: city fantasy forest aquarium river deepsea');
  }
  for (const scene of new Set(scenes)) {
    for (const stage of ['young', 'mature']) {
      const file = path.join(design, `${scene}-${stage}.png`);
      const source = fs.readFileSync(file);
      const metadata = await sharp(source).metadata();
      if (metadata.width !== 240 || metadata.height !== 240) {
        throw Error(`${file}: expected a 240x240 illustrated source`);
      }
      // Sharp fuses consecutive resize() calls into the final one, so the
      // intermediate 120px image must be materialized before upscaling.
      const small = await sharp(source)
        .resize(120, 120, {kernel: 'nearest'})
        .png()
        .toBuffer();
      const pixelArt = await sharp(small)
        .resize(240, 240, {kernel: 'nearest'})
        .png({palette: true, colours: 256, dither: 0})
        .toBuffer();
      fs.writeFileSync(file, pixelArt);
    }
  }
  console.log(`Pixel-art aligned: ${[...new Set(scenes)].join(', ')} (120px grid)`);
}

main().catch(error => {console.error(error); process.exitCode = 1;});
