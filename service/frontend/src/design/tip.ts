// Императивный тултип для графиков: работает с единственным #tip в App,
// чтобы hover по SVG не вызывал ре-рендеров React.

function tipEl(): HTMLElement | null {
  return document.getElementById("tip");
}

export function showTip(html: string, x: number, y: number): void {
  const tip = tipEl();
  if (!tip) return;
  tip.innerHTML = html;
  tip.classList.add("on");
  const r = tip.getBoundingClientRect();
  let nx = x + 14;
  let ny = y - r.height - 10;
  if (nx + r.width > window.innerWidth - 8) nx = x - r.width - 14;
  if (ny < 8) ny = y + 16;
  tip.style.left = nx + "px";
  tip.style.top = ny + "px";
}

export function hideTip(): void {
  tipEl()?.classList.remove("on");
}

export function tipRow(color: string, name: string, val: string): string {
  return `<div class="tr"><span class="sw" style="background:${color}"></span><span class="nm">${name}</span><span class="vv">${val}</span></div>`;
}
