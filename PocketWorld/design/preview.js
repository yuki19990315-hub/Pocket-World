/* Pocket World illustrated background / ambient animation study.
 * Intentionally separate from MicroPython firmware and its real-time save data.
 * No network, microphone, storage, or external dependency.
 */
(function () {
  "use strict";

  const canvas = document.getElementById("world");
  const ctx = canvas.getContext("2d", { alpha: false });
  ctx.imageSmoothingEnabled = false;
  const assetImages = {};
  for (const world of ["city", "forest", "aquarium", "nature", "hybrid", "fantasy"]) {
    const pair = {};
    for (const stage of ["young", "mature"]) {
      const picture = new Image();
      picture.onload = () => drawScene(animatedSeconds);
      picture.src = `assets/${world}-${stage}.png`;
      pair[stage] = picture;
    }
    assetImages[world] = pair;
  }
  const limit = (value, low, high) => Math.max(low, Math.min(high, value));
  const pixel = (value) => Math.round(value);
  const rect = (x, y, width, height, fill) => {
    ctx.fillStyle = fill;
    ctx.fillRect(pixel(x), pixel(y), Math.max(1, pixel(width)), Math.max(1, pixel(height)));
  };
  const circle = (cx, cy, radius, fill) => {
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.arc(pixel(cx), pixel(cy), radius, 0, Math.PI * 2);
    ctx.fill();
  };
  const polygon = (coords, fill) => {
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.moveTo(coords[0][0], coords[0][1]);
    for (let i = 1; i < coords.length; i++) ctx.lineTo(coords[i][0], coords[i][1]);
    ctx.closePath();
    ctx.fill();
  };
  function random(seed) {
    let state = seed | 0;
    return function () {
      state = (Math.imul(1664525, state) + 1013904223) | 0;
      return (state >>> 0) / 4294967296;
    };
  }

  const scenes = {
    city: {
      name: "街の世界", description: "ひとつの家から、少しずつにぎやかな街へ。",
      labels: ["建物", "住民"], events: [
        [0, "原っぱに、最初の小さな家が建ちました。"],
        [1, "新しい住民が引っ越してきました。"],
        [3, "広場から小道が伸び始めました。"],
        [7, "小さな商店がオープンしました。"],
        [14, "街灯がともり、夜の街もにぎやかです。"],
        [30, "みんなで街の誕生祭を開きました。"]
      ]
    },
    forest: {
      name: "森のテラリウム", description: "芽吹き、木漏れ日、生きものたちの静かな時間。",
      labels: ["木と草", "森の生きもの"], events: [
        [0, "小さな芽が土から顔を出しました。"],
        [1, "木の枝に鳥がとまりました。"],
        [3, "雨上がりの森にきのこが生えました。"],
        [7, "うさぎの親子が引っ越してきました。"],
        [14, "夜の森にホタルが灯り始めました。"],
        [30, "大きな古木が森のシンボルになりました。"]
      ]
    },
    aquarium: {
      name: "水の世界", description: "川の小魚から、海と深海へ広がる水の庭。",
      labels: ["魚", "水草と珊瑚"], events: [
        [0, "小川に2匹の魚が住み始めました。"],
        [1, "水草のあいだから稚魚が生まれました。"],
        [3, "小さなエビを見つけました。"],
        [7, "海へつながる水路が開きました。"],
        [14, "色鮮やかな珊瑚礁ができました。"],
        [30, "深い水底から不思議な光が見えました。"]
      ]
    },
    nature: {
      name: "ポケット惑星", description: "雲の上に浮かぶ、呼吸する小さな緑の星。",
      labels: ["植物", "野生動物"], events: [
        [0, "小さな島に最初の草が芽吹きました。"],
        [1, "雲が島に水を運んできました。"],
        [3, "最初の木に小鳥が巣を作りました。"],
        [7, "島のまわりを蝶が舞い始めました。"],
        [14, "丘のすそに小さな滝ができました。"],
        [30, "島が緑に包まれ、小さな楽園になりました。"]
      ]
    },
    hybrid: {
      name: "共生の世界", description: "森と村が一緒に育つ、やさしい小さな暮らし。",
      labels: ["家", "木と草"], events: [
        [0, "森のそばに一軒の家が建ちました。"],
        [1, "住民が庭に新しい木を植えました。"],
        [3, "小川に木の橋が架かりました。"],
        [7, "森の動物が村を訪れました。"],
        [14, "家々の屋根に緑が広がりました。"],
        [30, "村と森がひとつの景色になりました。"]
      ]
    },
    fantasy: {
      name: "魔法の世界", description: "星屑と水晶の浮島。静かに魔力が満ちていく。",
      labels: ["魔力", "精霊"], events: [
        [0, "夜空にひとつ、魔法の欠片が生まれました。"],
        [1, "島の水晶が淡く光り始めました。"],
        [3, "小さな精霊が星のあいだから現れました。"],
        [7, "空に流れ星が走りました。"],
        [14, "島のまわりに光の輪が生まれました。"],
        [30, "星の塔に不思議な扉が開きました。"]
      ]
    }
  };

  let selected = "city";
  let elapsedDays = 0;
  let playing = false;
  let lastFrame = 0;
  let lastCanvasPaint = 0;
  let animatedSeconds = 0;
  const houseMilestones=[180,720,1440,2880,4320,5760,8640,10080,14400,20160,28800,36000,43200];
  function cityNumbers() {
    const minutes = elapsedDays * 1440;
    return [1 + houseMilestones.filter(mark => minutes >= mark).length,
      2 + (minutes <= 180 ? Math.floor(minutes / 70) : 2 + Math.floor(minutes / 1440))];
  }
  function tinyPeople(count, seconds) {
    // The enclosing illustration layer uses a 120x120 working space.
    // Undo that scale: each human is exactly 1x3 native LCD pixels.
    ctx.save();ctx.scale(.5,.5);
    const tick=Math.floor(seconds*1000/1400);
    const shirts=["#1c3746","#bc3c36","#36435b","#8b3554"];
    for(let i=0;i<Math.min(18,count);i++){
      const phase=(tick+i*7)%24,step=phase<12?phase:24-phase;
      const x=93+(i*19)%45+step;
      const y=157+(i*29)%49+(Math.floor(tick/5)+i)%3;
      rect(x,y,1,1,"#ffdeb3");rect(x,y+1,1,1,shirts[i%shirts.length]);rect(x,y+2,1,1,"#20252b");
    }
    ctx.restore();
  }
  const growth = () => Math.log2(1 + elapsedDays) / Math.log2(31);
  const grown = (start, extra) => start + Math.floor(extra * growth());
  const night = () => (elapsedDays % 1) > 0.70;
  const rareEvents = {
    city: ["迷子の猫が広場に住み着きました。", "旅の行商人が小さな市場を開きました。", "夜空に小さな花火が上がりました。"],
    forest: ["白いキツネの足跡を見つけました。", "虹色のきのこがひと晩で育ちました。", "フクロウが新しい巣を作りました。"],
    aquarium: ["金色に光る小魚が泳いできました。", "ウミガメが水路を通り抜けました。", "珍しい模様の貝が流れ着きました。"],
    nature: ["雲の合間に二重の虹が現れました。", "渡り鳥の一団が島を訪れました。", "小さな流星が島の上を通過しました。"],
    hybrid: ["森のシカが村の花壇を見に来ました。", "住民と動物が一緒に橋を渡りました。", "古い樹木の根元に宝物が見つかりました。"],
    fantasy: ["空に双子の流れ星が現れました。", "金色の精霊が島の周りを踊りました。", "古代文字が水晶の中に浮かびました。"]
  };
  function visibleEvents() {
    const entries = scenes[selected].events.filter((entry) => entry[0] <= elapsedDays).slice();
    const index = Object.keys(scenes).indexOf(selected);
    const roll = random(8922 + index * 4241);
    for (let day = 1; day <= Math.floor(elapsedDays); day++) {
      if (roll() < 0.16) {
        const choice = Math.floor(roll() * rareEvents[selected].length);
        entries.push([day, "✧ " + rareEvents[selected][choice]]);
      }
    }
    entries.sort((a, b) => a[0] - b[0]);
    return entries.slice(-3).reverse();
  }

  function starField(seed, amount, color, t) {
    const rand = random(seed);
    for (let n = 0; n < amount; n++) {
      const x = Math.floor(rand() * 120), y = Math.floor(rand() * 76);
      const twinkle = Math.sin(t * 1.6 + x * .35 + y) > -.3;
      if (twinkle) rect(x, y, n % 7 === 0 ? 2 : 1, 1, color);
    }
  }
  function sky(colors, t, dark) {
    for (let y = 0; y < 90; y += 5) {
      rect(0, y, 120, 5, colors[Math.min(colors.length - 1, Math.floor(y / 90 * colors.length))]);
    }
    if (dark) starField(412, 30, "#f4e9bc", t);
    else {
      circle(92, 22, 9, "#f4d998");
      circle(92, 22, 6, "#fff0b6");
      cloud(13 + Math.sin(t * .2) * 3, 24, "#e9f0de");
      cloud(68 + Math.sin(t * .15) * 3, 42, "#e4e9d5");
    }
  }
  function cloud(x, y, fill) {
    rect(x + 4, y + 3, 25, 4, fill); rect(x + 8, y, 14, 4, fill);
    rect(x + 2, y + 5, 31, 3, fill); rect(x + 14, y - 3, 8, 4, fill);
  }
  function hill(x, y, rx, ry, fill) {
    ctx.fillStyle = fill;
    ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); ctx.fill();
  }
  function blades(count, yMin, yMax, fill, seed) {
    const rand = random(seed);
    for (let n = 0; n < count; n++) {
      const x = Math.floor(rand() * 120);
      const y = Math.floor(yMin + rand() * (yMax - yMin));
      rect(x, y, 1, 2 + Math.floor(rand() * 3), fill);
      if (n % 8 === 0) rect(x + 1, y - 1, 1, 1, "#f2d49c");
    }
  }
  function tree(x, y, size, leaves, dark) {
    const s = size || 1;
    rect(x - s, y - 2 * s, 2 * s, 15 * s, "#544334");
    rect(x, y - 8 * s, s, 13 * s, "#9b6a42");
    rect(x - 8 * s, y - 10 * s, 16 * s, 5 * s, dark || "#254c43");
    rect(x - 6 * s, y - 16 * s, 12 * s, 7 * s, leaves || "#4c9b6a");
    rect(x - 3 * s, y - 19 * s, 8 * s, 5 * s, leaves || "#4c9b6a");
    rect(x - 6 * s, y - 12 * s, 5 * s, 3 * s, "#91bd77");
    rect(x + 1 * s, y - 16 * s, 3 * s, 3 * s, "#b2d18b");
  }
  function house(x, y, kind, afterDark) {
    const wall = ["#f1d3a0", "#e7e0c2", "#d7b99e", "#b8d9cd"][kind % 4];
    const roof = ["#c16b5c", "#b96f49", "#667f85", "#aa6455"][kind % 4];
    rect(x - 7, y - 8, 15, 11, "#594a41");
    rect(x - 6, y - 8, 13, 10, wall);
    for (let row = 0; row < 6; row++) rect(x - 8 + row, y - 15 + row, 17 - row * 2, 2, roof);
    rect(x - 5, y - 4, 3, 4, afterDark ? "#ffe2a1" : "#688c8c");
    rect(x + 3, y - 4, 3, 4, afterDark ? "#ffe2a1" : "#688c8c");
    rect(x - 1, y - 4, 3, 7, "#765341");
    rect(x + 2, y - 13, 2, 2, "#f4c78d");
    if (kind % 4 === 1) rect(x + 4, y - 19, 3, 7, "#79665a");
  }
  function flowers(x, y, fill) {
    rect(x, y, 1, 3, "#497b57"); rect(x - 1, y - 1, 3, 2, fill); rect(x, y, 1, 1, "#f3d49e");
  }
  function rabbit(x, y, t) {
    const hop = Math.sin(t * 2.7 + x) > .65 ? 2 : 0;
    rect(x, y - 5 - hop, 7, 4, "#e7dfc5");
    rect(x + 5, y - 8 - hop, 3, 4, "#f3e9d7");
    rect(x + 5, y - 11 - hop, 1, 4, "#ebcfbc");
    rect(x + 7, y - 11 - hop, 1, 4, "#ebcfbc");
    rect(x + 8, y - 7 - hop, 1, 1, "#3b3d40");
    rect(x - 1, y - 5 - hop, 3, 3, "#f8eee1");
  }
  function fish(x, y, color, t, direction) {
    const dir = direction || 1;
    const bob = Math.sin(t * 2 + x) * 1.6;
    const xx = pixel(x), yy = pixel(y + bob);
    rect(xx - 4, yy - 2, 9, 5, color);
    rect(xx + (dir > 0 ? -7 : 5), yy - 3, 3, 7, color);
    rect(xx - 1, yy - 3, 3, 1, "#e2d6ab");
    rect(xx + (dir > 0 ? 3 : -3), yy - 1, 1, 1, "#243d43");
    rect(xx, yy + 1, 3, 1, "#ffffff70");
  }
  function waterPlant(x, y, height, color, t) {
    for (let k = 0; k < height; k += 3) {
      const sway = Math.floor(Math.sin(t * .8 + x + k * .25) * (k / 18));
      rect(x + sway, y - k, 2, 4, color);
      if (k % 9 === 0) rect(x + sway + 2, y - k + 1, 3, 1, "#7fc5a1");
    }
  }
  function bubble(x, y, size) {
    rect(x, y, size, 1, "#c4f4e6");
    rect(x, y, 1, size, "#8ecdd2");
    rect(x + size - 1, y + 1, 1, size - 1, "#8ecdd2");
    rect(x + 1, y + size - 1, size - 1, 1, "#c4f4e6");
  }
  function crystal(x, y, height, color, glint) {
    polygon([[x - 4, y], [x - 5, y - height + 5], [x, y - height], [x + 5, y - height + 6], [x + 4, y]], color);
    polygon([[x, y - height], [x + 2, y - height + 7], [x, y], [x - 2, y - 3]], glint);
  }

  const buildingSlots = [
    [58, 79], [28, 83], [83, 85], [41, 65], [73, 64],
    [17, 72], [95, 70], [58, 49], [23, 51], [93, 51],
    [45, 88], [72, 94], [44, 41], [75, 39], [21, 94], [95, 95]
  ];
  const forestSlots = [
    [59, 56], [28, 65], [91, 65], [14, 82], [109, 81],
    [44, 79], [76, 80], [21, 48], [101, 49], [59, 94],
    [37, 35], [82, 36], [8, 101], [108, 101], [57, 31], [99, 29], [22, 106]
  ];

  function cityScene(g, t, blended) {
    const afterDark = night();
    sky(afterDark ? ["#14253f", "#273952", "#54617a", "#8b7b78"] : ["#6fabb7", "#92c4be", "#bcdbbc", "#f1d9aa"], t, afterDark);
    hill(21, 81, 62, 21, "#759a84"); hill(102, 82, 67, 18, "#6b9981");
    rect(0, 79, 120, 41, "#79a27a");
    hill(52, 111, 105, 28, "#537d66");
    blades(58, 83, 116, "#9fc18a", 247);
    polygon([[47, 120], [49, 84], [62, 69], [70, 81], [76, 120]], "#ac9b80");
    polygon([[53, 120], [54, 90], [62, 77], [65, 90], [68, 120]], "#ccbb94");
    const buildingCount = blended ? grown(1, 8) : cityNumbers()[0];
    for (let k = 0; k < buildingCount; k++) {
      const slot = buildingSlots[k];
      house(slot[0], slot[1], k, afterDark);
    }
    if (g > .45) {
      rect(6, 99, 9, 3, "#9d8164"); rect(5, 94, 2, 9, "#695544");
      rect(14, 94, 2, 9, "#695544"); rect(15, 93, 2, 2, "#e9d4a0");
      rect(98, 92, 2, 15, "#6d6655"); rect(95, 91, 7, 2, "#f3d6a0");
    }
    if (blended) {
      tree(16, 84, 1, "#76ae68"); tree(103, 82, 1, "#609d63");
      tree(82, 50, 1, "#75b47b");
      if (g > .5) tree(29, 44, 1, "#679e7b");
    } else {
      tree(10, 69, 1, "#6baa70");
      tree(110, 74, 1, "#6daa75");
    }
    if(!blended)tinyPeople(cityNumbers()[1],t);
  }

  function forestScene(g, t) {
    const afterDark = night();
    sky(afterDark ? ["#152d42", "#2c4852", "#536b67", "#718577"] : ["#80b8af", "#a5ccae", "#b6d5a2", "#e1d39e"], t, afterDark);
    hill(32, 78, 69, 29, "#558d76"); hill(102, 79, 72, 32, "#376e63");
    rect(0, 76, 120, 44, "#3b755f");
    hill(60, 117, 117, 30, "#294f48");
    blades(120, 79, 117, "#7eae74", 88);
    const treeCount = Math.min(17, grown(2, 15));
    for (let i = 0; i < treeCount; i++) {
      const pos = forestSlots[i], size = (i > 8 && g > .64) ? 2 : 1;
      tree(pos[0], pos[1], size, i % 3 === 0 ? "#5f9b64" : "#70af6f", "#2b6658");
    }
    if (g > .23) {
      for (let i = 0; i < Math.floor(g * 22); i++) {
        const x = 8 + (i * 23) % 105, y = 88 + (i * 17) % 25;
        flowers(x, y, i % 2 ? "#d29b92" : "#e0be78");
      }
    }
    const wildlife = Math.min(5, Math.floor(g * 7));
    for (let i = 0; i < wildlife; i++) rabbit(16 + i * 19, 104 + (i % 3) * 5, t);
    if (g > .48 || afterDark) {
      const rand = random(29);
      for (let i = 0; i < 17; i++) {
        const x = 10 + rand() * 100, y = 55 + rand() * 55;
        if (Math.sin(t * 3 + i) > .0) rect(x, y, 2, 2, "#ffe8a0");
      }
    }
  }

  function aquariumScene(g, t) {
    const colors = ["#275d7b", "#367d91", "#4597a0", "#58aaa5", "#75b9ad", "#608f8b"];
    for (let y = 0; y < 120; y += 12) rect(0, y, 120, 12, colors[Math.min(colors.length - 1, Math.floor(y / 20))]);
    for (let i = 0; i < 5; i++) {
      polygon([[i * 28, 0], [i * 28 + 8, 0], [i * 28 + 27, 88], [i * 28 + 18, 88]], "#b1e7ca13");
    }
    hill(29, 123, 80, 29, "#ceb893");
    hill(105, 119, 65, 27, "#adac89");
    rect(0, 113, 120, 8, "#ac987b");
    const rand = random(229);
    for (let i = 0; i < 32; i++) {
      rect(rand() * 120, 107 + rand() * 13, 2 + rand() * 3, 2, i % 2 ? "#eee0ad" : "#988e7a");
    }
    const plants = Math.min(18, grown(3, 15));
    for (let i = 0; i < plants; i++) {
      const x = 7 + (i * 19) % 112;
      waterPlant(x, 111, 10 + (i % 4) * 5 + Math.floor(g * 9), i % 2 ? "#398b74" : "#4da88d", t);
    }
    if (g > .35) {
      for (let i = 0; i < Math.floor(g * 9); i++) {
        const x = 12 + (i * 33) % 99, y = 112 - (i % 3) * 2;
        rect(x, y - 8, 3, 10, i % 2 ? "#df998c" : "#f0b78c");
        rect(x - 3, y - 9, 4, 4, "#f3a48e");
        rect(x + 3, y - 12, 3, 6, i % 2 ? "#ebbd91" : "#f29c9c");
      }
    }
    const fishCount = Math.min(17, grown(2, 15));
    for (let i = 0; i < fishCount; i++) {
      const direction = i % 2 ? 1 : -1;
      const x = ((18 + i * 31 + t * (2 + (i % 3)) * direction + 240) % 128) - 4;
      const y = 18 + (i * 23) % 70;
      fish(x, y, ["#f4ce82", "#f09884", "#c9e5bd", "#b1d3d5", "#c4adce"][i % 5], t, direction);
    }
    if (g > .8) {
      for (let i = 0; i < 4; i++) {
        const xx = 13 + 30 * i, yy = 35 + 16 * (i % 2);
        rect(xx, yy, 3, 3, "#a7e5e9"); rect(xx + 1, yy - 2, 1, 2, "#c5f6f5");
      }
    }
    for (let i = 0; i < 18; i++) {
      const x = (13 + i * 41) % 117;
      const y = (100 + i * 13 - t * (3 + i % 4) + 2400) % 116;
      bubble(x, y, 2 + i % 3);
    }
  }

  function natureScene(g, t) {
    const afterDark = night();
    sky(afterDark ? ["#1c3450", "#375368", "#627484", "#95a18e"] : ["#8bbfc7", "#add2d2", "#d5dbb7", "#f5d6ab"], t, afterDark);
    const float = Math.sin(t * .75) * 2;
    hill(60, 81 + float, 47, 12, "#8cbd78");
    polygon([[16, 83 + float], [104, 83 + float], [92, 97 + float], [67, 115 + float], [43, 104 + float]], "#6a6257");
    polygon([[29, 91 + float], [92, 91 + float], [67, 109 + float]], "#8c7763");
    rect(52, 77 + float, 6, 9, "#b7df9d");
    const plants = Math.min(12, grown(2, 10));
    for (let i = 0; i < plants; i++) {
      const x = 28 + ((i * 19) % 65);
      const y = 73 + float + ((i * 7) % 10);
      if (i % 3 === 0) tree(x, y, 1, "#7cbd73");
      else flowers(x, y, i % 2 ? "#e8b28b" : "#f5dcaf");
    }
    if (g > .45) {
      rect(88, 85 + float, 5, 12, "#a2dce7");
      rect(89, 96 + float, 3, 8, "#caedf1");
    }
    if (g > .25) {
      for (let i = 0; i < 4; i++) {
        const xx = 17 + i * 26 + Math.sin(t + i) * 4;
        const yy = 36 + i * 9 + Math.sin(t * 2 + i) * 3;
        rect(xx, yy, 2, 1, "#f2d19c");
        rect(xx + 2, yy - 1, 2, 1, "#d8e8cc");
      }
    }
  }

  function fantasyScene(g, t) {
    const colors = ["#252548", "#36315f", "#544979", "#7a638b", "#b18a9f"];
    for (let y = 0; y < 120; y += 12) rect(0, y, 120, 12, colors[Math.min(4, Math.floor(y / 24))]);
    starField(504, 45, "#f1d8c1", t);
    const float = Math.sin(t * 1.1) * 2;
    hill(61, 88 + float, 40, 11, "#775f91");
    polygon([[22, 88 + float], [100, 88 + float], [78, 110 + float], [53, 117 + float]], "#373654");
    polygon([[35, 96 + float], [90, 96 + float], [61, 114 + float]], "#51527b");
    const count = Math.min(12, grown(1, 11));
    for (let i = 0; i < count; i++) {
      const x = 31 + (i * 17) % 61;
      const y = 89 + float + (i % 3) * 2;
      crystal(x, y, 13 + (i * 7) % 20, i % 3 ? "#a28fd0" : "#87aada", "#d9c5ef");
    }
    if (g > .45) {
      rect(55, 53 + float, 14, 31, "#554a79");
      rect(58, 46 + float, 8, 37, "#796592");
      crystal(62, 47 + float, 17, "#e3b8e4", "#f7e0f0");
      rect(61, 73 + float, 4, 9, "#b8a0da");
    }
    if (g > .27) {
      const x = (t * 13) % 120;
      rect(x, 12 + Math.sin(t) * 6, 5, 1, "#f7e5c3");
      rect(x - 3, 13 + Math.sin(t) * 6, 3, 1, "#c5b4e8");
    }
    for (let i = 0; i < Math.floor(g * 13); i++) {
      const x = 25 + (i * 23) % 74, y = 43 + (i * 11) % 53;
      if (Math.sin(t * 3 + i) > 0) rect(x, y + Math.sin(t + i) * 3, 2, 2, "#ffe8b5");
    }
  }

  function drawScene(t) {
    ctx.save();
    ctx.clearRect(0, 0, 240, 240);
    ctx.beginPath(); ctx.arc(120, 120, 119, 0, Math.PI * 2); ctx.clip();
    const g = growth();
    const pair = assetImages[selected];
    if (pair.young.complete && pair.young.naturalWidth && pair.mature.complete && pair.mature.naturalWidth) {
      // A stable scene at both ends of the timeline; gradual painterly dissolve in between.
      ctx.drawImage(pair.young, 0, 0, 240, 240);
      ctx.globalAlpha = selected === "city"
        ? (cityNumbers()[0]-1)/houseMilestones.length
        : limit(elapsedDays / 30, 0, 1);
      ctx.drawImage(pair.mature, 0, 0, 240, 240);
      ctx.globalAlpha = 1;
      if (night() && selected !== "fantasy" && selected !== "aquarium") {
        rect(0, 0, 240, 240, "#0b1e5360");
      }
      ctx.save();
      ctx.scale(2, 2);
      livingDetails(selected, g, t);
      ctx.restore();
    } else {
      // Gracefully retain the original compact procedural sketch if an asset is missing.
      ctx.save();
      ctx.scale(2, 2);
      if (selected === "city") cityScene(g, t, false);
      if (selected === "forest") forestScene(g, t);
      if (selected === "aquarium") aquariumScene(g, t);
      if (selected === "nature") natureScene(g, t);
      if (selected === "hybrid") cityScene(g, t, true);
      if (selected === "fantasy") fantasyScene(g, t);
      ctx.restore();
    }
    ctx.restore();
    ctx.beginPath(); ctx.arc(120, 120, 119, 0, Math.PI * 2);
    ctx.lineWidth = 1.2; ctx.strokeStyle = "#ffffff38"; ctx.stroke();
  }

  function livingDetails(world, g, t) {
    // Details deliberately stay tiny; the painted backgrounds are the stars.
    if (world === "city" || world === "hybrid") {
      tinyPeople(world === "city" ? cityNumbers()[1] : Math.floor(g*7),t);
      if (world === "hybrid" && g > .3) rabbit(83, 95, t);
    }
    if (world === "forest") {
      if (g > .1) rabbit(70 + Math.sin(t * .45) * 5, 90, t);
      if (g > .3 || night()) {
        const rand = random(944);
        for (let i = 0; i < 12; i++) {
          const x = 16 + rand() * 87, y = 20 + rand() * 73;
          if (Math.sin(t * 2.4 + i * 2) > .42) rect(x, y + Math.sin(t + i) * 2, 1, 2, "#fff3a8");
        }
      }
    }
    if (world === "aquarium") {
      const count = 1 + Math.floor(g * 4);
      for (let i = 0; i < count; i++) {
        const direction = i % 2 ? -1 : 1;
        const x = 20 + ((i * 37 + direction * t * (3 + i) + 3000) % 80);
        const y = 26 + (i * 19) % 62;
        fish(x, y, ["#ffd77f", "#ffa990", "#a9e5d9", "#f4c7f2"][i % 4], t, direction);
      }
      for (let i = 0; i < 14; i++) {
        const x = 11 + (i * 31) % 99;
        const y = (105 + i * 27 - t * (2 + i % 4) + 2400) % 117;
        bubble(x, y, 1 + i % 2);
      }
    }
    if (world === "nature") {
      // The young image starts as a quiet meadow; wildlife arrives as it grows.
      if (g > .2) {
        for (let i = 0; i < 1 + Math.floor(g * 3); i++) {
          const x = 18 + ((i * 29 + t * (1.5 + i * .3)) % 85);
          const y = 20 + i * 8 + Math.sin(t * 2 + i) * 3;
          rect(x, y, 2, 1, "#fff8db"); rect(x + 2, y - 1, 2, 1, "#bfd9e9");
        }
      }
      // Tiny moving highlights mark the mature waterfall without repainting it.
      if (g > .6) {
        for (let i = 0; i < 3; i++) {
          const y = 84 + ((t * 6 + i * 7) % 15);
          rect(85 + (i % 2), y, 1, 2, "#d8f5ff");
        }
      }
    }
    if (world === "fantasy") {
      const rand = random(1042);
      for (let i = 0; i < 16; i++) {
        const x = 16 + rand() * 88, y = 22 + rand() * 76;
        if (Math.sin(t * 2.4 + i * 1.7) > .2) {
          rect(x, y + Math.sin(t + i) * 3, 2, 2, i % 2 ? "#fef1b7" : "#d4a9ff");
        }
      }
      if (g > .2) {
        const x = 10 + (t * 8) % 120;
        rect(x, 13 + Math.sin(t * 2) * 3, 6, 1, "#fff2d7");
        rect(x - 5, 14 + Math.sin(t * 2) * 3, 5, 1, "#d7b8f6");
      }
    }
  }

  function sceneStats() {
    const g = growth();
    if (selected === "city") return cityNumbers();
    if (selected === "forest") return [grown(2, 65), grown(1, 19)];
    if (selected === "aquarium") return [grown(2, 15), grown(3, 32)];
    if (selected === "nature") return [grown(2, 75), grown(0, 20)];
    if (selected === "hybrid") return [grown(1, 8), grown(4, 56)];
    return [grown(1, 79), grown(0, 12)];
  }
  function updateText() {
    const scene = scenes[selected];
    document.getElementById("world-name").textContent = scene.name;
    document.getElementById("world-description").textContent = scene.description;
    document.getElementById("day-label").textContent = "DAY " + Math.floor(elapsedDays);
    document.getElementById("day").value = String(elapsedDays);
    const values = sceneStats();
    document.getElementById("stat-label-a").textContent = scene.labels[0];
    document.getElementById("stat-label-b").textContent = scene.labels[1];
    document.getElementById("stat-a").textContent = String(values[0]);
    document.getElementById("stat-b").textContent = String(values[1]);
    const latest = visibleEvents();
    const list = document.getElementById("events");
    list.replaceChildren();
    for (const entry of latest) {
      const li = document.createElement("li");
      li.textContent = entry[1];
      const when = document.createElement("small");
      when.textContent = "DAY " + entry[0];
      li.appendChild(when);
      list.appendChild(li);
    }
    for (const button of document.querySelectorAll("[data-world]")) {
      const active = button.dataset.world === selected;
      button.classList.toggle("selected", active);
      button.setAttribute("aria-pressed", String(active));
    }
    document.getElementById("play").textContent = playing ? "Ⅱ 成長を停止" : "▶ 自動成長";
  }
  function changeDays(value) {
    elapsedDays = limit(Math.round(value * 4) / 4, 0, 30);
    updateText();
    drawScene(animatedSeconds);
  }
  document.getElementById("day").addEventListener("input", (event) => changeDays(Number(event.target.value)));
  document.getElementById("plus-day").addEventListener("click", () => changeDays(elapsedDays + 1));
  document.getElementById("plus-week").addEventListener("click", () => changeDays(elapsedDays + 7));
  document.getElementById("play").addEventListener("click", () => {
    if (!playing && elapsedDays >= 30) changeDays(0);
    playing = !playing;
    updateText();
  });
  for (const button of document.querySelectorAll("[data-world]")) {
    button.addEventListener("click", () => {
      selected = button.dataset.world;
      updateText();
      drawScene(animatedSeconds);
    });
  }
  function frame(now) {
    const delta = lastFrame ? Math.min(0.2, (now - lastFrame) / 1000) : 0;
    lastFrame = now;
    animatedSeconds += delta;
    if (playing && delta) {
      const previousQuarter = Math.floor(elapsedDays * 4);
      elapsedDays = Math.min(30, elapsedDays + delta * .20);
      if (Math.floor(elapsedDays * 4) !== previousQuarter) updateText();
      if (elapsedDays >= 30) { playing = false; updateText(); }
    }
    if (now - lastCanvasPaint > 55) {
      drawScene(animatedSeconds);
      lastCanvasPaint = now;
    }
    requestAnimationFrame(frame);
  }
  updateText();
  drawScene(0);
  requestAnimationFrame(frame);
})();
