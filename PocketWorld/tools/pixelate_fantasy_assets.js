/* Preserve the two existing fantasy compositions while aligning their actual
 * bitmap grid with the 120x120 -> 240x240 nearest-neighbour LCD art spec.
 * Run before build_display_assets.js; original PNGs remain in Git history.
 */
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');

const design = path.join(__dirname, '..', 'design', 'assets');

async function main() {
  for (const stage of ['young', 'mature']) {
    const file = path.join(design, `fantasy-${stage}.png`);
    const source = fs.readFileSync(file);
    const metadata = await sharp(source).metadata();
    if (metadata.width !== 240 || metadata.height !== 240) {
      throw Error(`${file}: expected a 240x240 illustrated source`);
    }
    // Sharp fuses consecutive resize calls into the last one. Materialize
    // the small grid before scaling it back up to guarantee 2x2 blocks.
    const lowResolution = await sharp(source)
      .resize(120, 120, {kernel: 'nearest'})
      .png()
      .toBuffer();
    const pixelArt = await sharp(lowResolution)
      .resize(240, 240, {kernel: 'nearest'})
      .png({palette: true, colours: 256, dither: 0})
      .toBuffer();
    fs.writeFileSync(file, pixelArt);
  }
  console.log('Fantasy pixel art: 2 illustrated stages aligned to the 120px grid');
}

main().catch(error => {console.error(error); process.exitCode = 1;});
