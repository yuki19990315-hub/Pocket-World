# Approved photographic-style moon jelly

The user approved an image generated with the built-in image generator on 2026-11-24 after rejecting both procedural line-art versions. It is synthetic artwork, not an aquarium photograph. The selected 240px master is `assets/jellyfish-tank.png`. The same image supplies the phone PNG and the device RGB565 background. No third-party photos or video frames are bundled.

Prompt: Exactly one authentic Aurelia moon jelly, underwater macro photograph aesthetic, fully visible on dark navy water; translucent rounded bell, fine radial canals and four faint horseshoe-shaped gonads; many short marginal tentacles and four folded frilly oral arms. Pale blue-white aquarium lighting, subtle lavender internal structures. No pixel art, outlines, neon, text, tank rim, other animals or bubbles. Soft optical depth and natural tissue folds.

The runtime deforms the approved image with subtle bell contraction, drift and lower-body sway. This is a stylized animation of a still image, not a physically simulated animal or prerecorded video. Viper and CPython reference paths use the same bounded RGB565 sampling. The LCD transfers a single full frame per animation tick; other worlds retain their existing cache and animation paths.

Anatomical references consulted before choosing the visual:
- https://pop.kaiyukan.com/area/exhibition/104.html
- https://www.aquariumbcn.com/en/especies/jellyfish/moon-jellyfish/
- https://eastidahoaquarium.com/touch-moon-jelly-exhibit/
- https://www.montereybayaquarium.org/cams-videos/live-cams/moon-jelly-cam

Build: `node PocketWorld/tools/build_display_assets.js` converts the master PNG and refreshes the Android pack. It requires Node and sharp. The Python build_jelly_tank.py entry point delegates to that builder.

The smaller floating revision uses inverse scale 1840/1024 (about 56% linear size), wide slow two-frequency drift, source-relative oral-arm sway, and luminance/edge matting onto uniform water. Both initial world selection and animation show the same small animal.

Swimming and contraction share a five-second cycle. A smooth propulsion phase advances the trajectory faster during the bell squeeze, then coasts more slowly. Oral-arm drag follows the propulsion with a half-second delay. Linear scale and the path extent remain unchanged.
