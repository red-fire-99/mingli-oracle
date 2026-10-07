// 临时脚本：用 iztro（紫微斗数权威库）批量排盘，输出 JSON 供 Python 对照
const iz = require('iztro');
const fs = require('fs');

const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = [];
for (const c of cases) {
  try {
    const a = iz.astro.bySolar(c.date, c.timeIndex, c.gender, true);
    const palaces = a.palaces.map(p => ({
      name: p.name,
      zhi: p.earthlyBranch,
      gan: p.heavenlyStem,
      isBody: !!p.isBodyPalace,
      isSoul: !!p.isPrimaryPalace,
      stars: [...p.majorStars, ...p.minorStars].map(s => ({
        n: s.name,
        m: s.mutagen || null,
      })),
    }));
    out.push({
      ok: true,
      five: a.fiveElementsClass,
      soulZhi: a.earthlyBranchOfSoulPalace,
      bodyZhi: a.earthlyBranchOfBodyPalace,
      palaces,
    });
  } catch (e) {
    out.push({ ok: false, err: String(e) });
  }
}
console.log(JSON.stringify(out));
