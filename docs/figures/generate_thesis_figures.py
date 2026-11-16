"""Create documentation-only SVG diagrams and plots from frozen M12a data."""

from __future__ import annotations

from html import escape
from pathlib import Path
import math

OUT = Path(__file__).resolve().parent
NAVY, BLUE, TEAL, ORANGE, RED, GRAY = "#15324b", "#3478a8", "#2f8f83", "#dc8b32", "#bf4b4b", "#61717f"


def t(x: float, y: float, s: str, size: int = 16, color: str = NAVY, anchor: str = "middle") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="Segoe UI,Arial,sans-serif" font-size="{size}" fill="{color}">{escape(s)}</text>'


def box(x: int, y: int, w: int, h: int, s: str, color: str = "#eef3f6", size: int = 15) -> str:
    lines = s.split("\n")
    start = y + h / 2 - (len(lines) - 1) * (size + 3) / 2 + size / 3
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{color}" stroke="{NAVY}" stroke-width="2"/>' + "".join(t(x+w/2, start+i*(size+3), line, size) for i, line in enumerate(lines))


def ar(x1: int, y1: int, x2: int, y2: int, color: str = BLUE) -> str:
    return f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="3" marker-end="url(#a)"/>'


def doc(title: str, w: int, h: int, body: str, note: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
            '<defs><marker id="a" markerWidth="10" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0L10 4L0 8z" fill="#3478a8"/></marker></defs>'
            f'<rect width="100%" height="100%" fill="white"/>{t(w/2,32,title,22)}{body}{t(w/2,h-14,note,12,GRAY)}</svg>')


def put(name: str, content: str) -> None:
    (OUT / name).write_text(content, encoding="utf-8")


def simple_diagram(name: str, title: str, boxes: list[tuple[str, str]], note: str, width: int = 1280) -> None:
    gap, bw, y, bh = 25, (width - 70 - 4 * 25) // 5, 125, 92
    body = ""
    for i, (label, color) in enumerate(boxes):
        x = 35 + i * (bw + gap)
        body += box(x, y, bw, bh, label, color)
        if i < len(boxes) - 1:
            body += ar(x + bw, y + bh/2, x + bw + gap, y + bh/2)
    put(name, doc(title, width, 280, body, note))


def diagrams() -> None:
    simple_diagram("fig01_hf_tcm_sim_architecture.svg", "Рисунок 1 — Архітектура HF-TCM-SIM",
                   [("Інформаційні біти\n2 біти/такт", "#e9f0f7"), ("TCM encoder\nR=2/3", "#e9f0f7"), ("8PSK + ADR-002\nреконструкція", "#f5f1e9"), ("Модельний канал\n8 samples/symbol", "#f9eeee"), ("Метрики → posterior\nрекурсія → Viterbi", "#eaf5f1")],
                   "Локальна офлайнова реконструкція; не фізичний HF-приймач.")
    simple_diagram("fig02_tcm_encoder.svg", "Рисунок 2 — Реконструйована структура кодера R=2/3",
                   [("Входи\n(u₀,u₁)", "#e9f0f7"), ("Пам'ять\nD¹, D²", "#f5f1e9"), ("XOR\nu₁[k]⊕u₁[k−2]", "#eaf5f1"), ("Виходи\n(c₂,c₁,c₀)", "#e9f0f7"), ("Стан далі\n(u₁[k],u₁[k−1])", "#f5f1e9")],
                   "Порядок виходу й state convention — проєктна інтерпретація матриці G(x).")

    states = [(0, 0), (0, 1), (1, 0), (1, 1)]
    yy = {s: 95 + i*125 for i, s in enumerate(states)}
    body = ""
    for side, x in [(0, 145), (1, 710)]:
        for s in states:
            y=yy[s]; body += f'<circle cx="{x}" cy="{y}" r="23" fill="#e9f0f7" stroke="{NAVY}" stroke-width="2"/>'+t(x,y+6,f"{s[0]}{s[1]}",14)
    eid=0
    for a,b in states:
        for u0 in (0,1):
            for u1 in (0,1):
                out=(u0,u1^b,a); dest=(u1,a); sy,dy=yy[(a,b)],yy[dest]
                color=[BLUE,TEAL,ORANGE,RED][eid%4]
                body+=f'<path d="M168,{sy} C340,{(sy+dy)//2} 500,{(sy+dy)//2} 687,{dy}" fill="none" stroke="{color}" stroke-width="1.7" opacity=".72"/>'
                phase=4*out[0]+2*out[1]+out[2]
                body+=t(425,(sy+dy)/2+(eid%2*12-5),f"{eid}: {a}{b}→{u0}{u1}/{out[0]}{out[1]}{out[2]}→{dest[0]}{dest[1]} · b={phase}",10)
                eid+=1
    body+=t(145,54,"Стан f",14)+t(710,54,"Стан f+1",14)
    put("fig03_reconstructed_trellis.svg",doc("Рисунок 3 — Чотиристанова решітка та 16 проєктних переходів",850,620,body,
        "Edge ID і b відтворені за ADR-002; авторську таблицю відповідності не встановлено."))

    cx,cy,r=390,290,190
    body=f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#cbd7df" stroke-width="2"/><line x1="100" y1="{cy}" x2="680" y2="{cy}" stroke="{GRAY}"/><line x1="{cx}" y1="45" x2="{cx}" y2="540" stroke="{GRAY}"/>'
    for b in range(8):
        a=b*math.pi/4; x=cx+r*math.cos(a); y=cy-r*math.sin(a)
        body+=f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e3e9ed"/><circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{BLUE}"/>'+t(x+20*math.cos(a),y-20*math.sin(a),f"b={b}",14)
    body+=t(694,cy+5,"I",15)+t(cx,38,"Q",15)
    put("fig04_8psk_constellation.svg",doc("Рисунок 4 — Сузір'я 8PSK із фазовим кроком π/4",780,580,body,
        "Абсолютне фазове походження й coded-bit labeling є реконструкціями."))

    simple_diagram("fig05_model_channel.svg", "Рисунок 5 — Тракт передачі через модельний канал",
                   [("Символ 8PSK\ns[f]", "#e9f0f7"), ("Rectangular ZOH\n8 samples/symbol", "#f5f1e9"), ("Gain profile\na[f]", "#f9eeee"), ("Additive noise\nw[n]", "#f9eeee"), ("Received samples\ny[n]", "#eaf5f1")],
                   "M5–M9: a=0.75; M10: контрольовані P0/P1/P2. Не повна фізична HF-модель.")
    simple_diagram("fig06_joint_receiver_reconstruction.svg", "Рисунок 6 — Реконструйований тракт joint receiver",
                   [("ADR-012\n8 I/Q samples", "#e9f0f7"), ("16 predictions\n[A](5) kernel", "#f5f1e9"), ("Squared residual\nmetric per edge", "#f9eeee"), ("ADR-005\nposterior", "#f5f1e9"), ("Estimator update\n→ conditional Viterbi", "#eaf5f1")],
                   "Проєктні likelihood/timebase; не повна авторська HMM специфікація.")
    simple_diagram("fig07_recursive_estimator.svg", "Рисунок 7 — Рекурсивне оновлення оцінки",
                   [("Попередній стан\nμ̃ᵢ", "#e9f0f7"), ("Σₕ pₕ(Y−Ûₕ)\ninnovation", "#f5f1e9"), ("α′μ̃ᵢ + K̃·εᵢ\nupdate", "#eaf5f1"), ("μ̃ᵢ₊₁ + μ₀\nfull estimate", "#e9f0f7"), ("Наступне f+1\npre-state", "#f5f1e9")],
                   "Алгебра явних операндів перевірена; їхня авторська семантика частково unresolved.")
    simple_diagram("fig08_conditional_viterbi.svg", "Рисунок 8 — Conditional Viterbi над frozen metric rows",
                   [("Матриця F×16\nзаморожені costs", "#f5f1e9"), ("Старт (0,0)\nінші ∞", "#e9f0f7"), ("Min-plus update\nза дозволеними ребрами", "#eaf5f1"), ("Вільний фінальний\nстан", "#e9f0f7"), ("Traceback\nвхідні біти", "#f5f1e9")],
                   "Проєктний контракт; tie handling і termination не повністю визначені [A].")


def bars(name: str, title: str, rows: list[tuple[str,float,str]], xmax: float, note: str, digits: int=5) -> None:
    w=1180; top=78; rowh=34; h=top+len(rows)*rowh+60; left=340; right=1110; bottom=top+len(rows)*rowh
    b=f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="{NAVY}"/><line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{NAVY}"/>'
    for i in range(5):
        v=xmax*i/4; x=left+(right-left)*v/xmax
        b+=f'<line x1="{x}" y1="{top}" x2="{x}" y2="{bottom}" stroke="#e5ebef"/>'+t(x,bottom+18,f"{v:.{digits}f}",11,GRAY)
    for i,(label,val,color) in enumerate(rows):
        y=top+i*rowh+6; b+=t(left-10,y+16,label,12,NAVY,"end")
        bw=(right-left)*val/xmax; b+=f'<rect x="{left}" y="{y}" width="{bw:.2f}" height="22" rx="3" fill="{color}"/>'+t(left+bw+50,y+16,f"{val:.8f}",11,GRAY,"start")
    put(name,doc(title,w,h,b,note))


def ci_plot(name: str, title: str, estimate: float, lo: float, hi: float, note: str) -> None:
    w,h=1120,350; left,right,top,bottom=220,1050,105,255; xmin,xmax=-.004,.004
    x=lambda v:left+(right-left)*(v-xmin)/(xmax-xmin)
    b=f'<line x1="{x(0)}" y1="{top}" x2="{x(0)}" y2="{bottom}" stroke="{RED}" stroke-width="2"/>'
    b+=f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{NAVY}"/>'
    for v in [-.004,-.002,0,.002,.004]: b+=f'<line x1="{x(v)}" y1="{top}" x2="{x(v)}" y2="{bottom}" stroke="#e5ebef"/>'+t(x(v),bottom+22,f"{v:.3f}",12,GRAY)
    b+=f'<line x1="{x(lo)}" y1="175" x2="{x(hi)}" y2="175" stroke="{TEAL}" stroke-width="8"/><circle cx="{x(estimate)}" cy="175" r="8" fill="{NAVY}"/>'
    b+=t(630,65,f"Estimate {estimate:.10f}; 95% CI [{lo:.14f}, {hi:.14f}]",14)
    b+=t(630,318,"ΔBER = BER(anchored) − BER(frozen B)",14)
    put(name,doc(title,w,h,b,note))


def results() -> None:
    bars("fig09_m5j_ber.svg","Рисунок 9 — M5j pooled BER: frozen B і combined C",
         [("frozen B (1 079/51 200)",1079/51200,BLUE),("combined C (19 793/51 200)",19793/51200,RED)],.42,
         "100 парних EVALUATION sequences; вузький reconstructed_offline L=1 профіль.",6)
    m7=[("M7 a100_k000 (B)",478/20480,BLUE),("M7 a095_k000",1903/20480,TEAL),("M7 a100_k050",3050/20480,ORANGE),("M7 a100_k100",4831/20480,ORANGE),("M7 a085_k000",4871/20480,ORANGE),("M7 a095_k100",7357/20480,ORANGE),("M7 a095_k050",7575/20480,ORANGE),("M7 a085_k100 (C)",8093/20480,RED),("M7 a085_k050",8545/20480,ORANGE)]
    m8=[("M8 frozen B",413/20480,BLUE),("M8 anch a085_k025",429/20480,TEAL),("M8 anch a095_k025",490/20480,ORANGE),("M8 anch a085_k050",528/20480,ORANGE),("M8 anch a095_k050",924/20480,ORANGE),("M8 anch a100_k025",1501/20480,ORANGE),("M8 anch a100_k050",3000/20480,ORANGE),("M8 combined C",7804/20480,RED)]
    bars("fig10_m7_m8_train.svg","Рисунок 10 — M7/M8 BER у TRAIN partition",m7+m8,.45,
         "M7: 40 sequences; M8 recovery: ті самі 40 TRAIN IDs. Відбір не є незалежною валідацією.",5)
    ci_plot("fig11_m9_ber_ci.svg","Рисунок 11 — M9b paired ΔBER та 95% CI",-.0011328125,-.00322265625,.00068359375,
            "Інтервал містить 0; це не доказ equivalence або noninferiority.")

    w,h,left,right,top,bottom=1120,380,100,1040,90,280
    xx=lambda f:left+(right-left)*f/256; yy=lambda a:bottom-(bottom-top)*(a-.55)/.30
    b=f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="{NAVY}"/><line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{NAVY}"/>'
    for f in [0,64,128,192,256]: b+=f'<line x1="{xx(f)}" y1="{top}" x2="{xx(f)}" y2="{bottom}" stroke="#e5ebef"/>'+t(xx(f),bottom+20,str(f),12,GRAY)
    for a in [.60,.65,.70,.75,.80]: b+=t(left-10,yy(a)+4,f"{a:.2f}",12,GRAY,"end")
    for vals,color,pid in [([.75,.75],BLUE,"P0"),([math.sqrt(.765),.60],RED,"P1"),([.60,math.sqrt(.765)],TEAL,"P2")]:
        a0,a1=vals; b+=f'<path d="M{xx(0)},{yy(a0)} L{xx(128)},{yy(a0)} L{xx(128)},{yy(a1)} L{xx(256)},{yy(a1)}" fill="none" stroke="{color}" stroke-width="4"/>'+t(900,top+18+["P0","P1","P2"].index(pid)*20,f"{pid}: {a0:.4f}→{a1:.2f}",12,color,"start")
    b+=t(570,h-40,"Символ f",14)+t(34,(top+bottom)/2,"Gain a[f]",13,GRAY)
    put("fig12_m10_gain_profiles.svg",doc("Рисунок 12 — M10: модельні профілі дійсного gain",w,h,b,"P1/P2 перемикаються при f=128; це синтетичні schedules, не фізичне fading."))
    ci_plot("fig13_m10_p1_ber_ci.svg","Рисунок 13 — M10 P1 paired ΔBER та 95% CI",-.0003125,-.00205126953125,.0014453125,
            "Інтервал містить 0; superiority, equivalence та noninferiority не встановлені.")


if __name__ == "__main__":
    diagrams(); results()
    print("Generated 13 SVG figures from frozen specifications and archived results.")
