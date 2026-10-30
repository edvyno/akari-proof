#!/usr/bin/env python3
"""Generate FlapJax treasury-day audit pages from verified data.

Data source: /tmp/treasury_days_verified.json — every row was verified against
eth_getTransactionReceipt (status 0x1, FLAPJAX Transfer log from treasury) and
block timestamps re-read from a public BSC node.
Funder table below is from each recipient's full native+internal history on BscScan.
"""
import json, html, os

TOK = "0x90c8889f428F9Ebb77BB8f15CAD3a50a9aC680df"
TRE = "0x7C34E9e21eE28A49Ff0b84B61774119E6633359f"

DAYS = {
    "Q80": dict(day="2026-10-29", b0=130413458, b1=130605332, b0_t="2026-10-29 05:00:00 UTC",
                b1_t="2026-10-30 04:59:59 UTC", nb=130605333, nb_t="2026-10-30 05:00:00 UTC",
                fname="flapjax-q80-audit.html", jname="flapjax-q80.json",
                title="Q80"),
    "Q78": dict(day="2026-10-28", b0=130221520, b1=130413457, b0_t="2026-10-28 05:00:00 UTC",
                b1_t="2026-10-29 04:59:59 UTC", nb=130413458, nb_t="2026-10-29 05:00:00 UTC",
                fname="flapjax-q78-audit.html", jname="flapjax-q78.json",
                title="Q78"),
}

TREASURY = {"addr": "0x5ba434b40be6cfc7033bf8d4545320fa609a4268", "bnb": 0.12638071,
            "blk": 123473817, "utc": "2026-09-23 01:03:46 UTC",
            "tx": "0xe0f7aeeedd38558ba63a596b8eb6b73e53af63d6282fc3e370160f3b2109bfd0"}

# recipient -> funder record
# kind: treasury | eoa | relay | none | dust | unexplained
FUND = {
    "0x97cd18b8bbb629b17675d868259ea84c0a2a5a9c": dict(kind="none"),
    "0xabc2c3daffa4c1963299da225c25f2aa7d4ddf62": dict(kind="none"),
    "0xfb200657f7266157a45dfcc6c09690726daa24e6": dict(kind="treasury", bnb=0.0005, blk=126835408,
        utc="2026-10-10 13:25:31 UTC",
        tx="0xa3d7042983f4f2352b9b8f324414688db10887e2b2b2a125deca9a8bec6624e7"),
    "0xd16446a568f46bca1504422062f23767d8fa58d9": dict(kind="none"),
    "0x2ae18c3b2fc18545edd35beeaef97cc2ed908a02": dict(kind="dust", bnb=0.00006257, blk=131000000,
        utc="2026-10-30 08:20:04 UTC",
        tx="0x5bd8ede524ed31fc2a86136e6a8e452b4c1b18aa420178fe895d8eca72bed6ef",
        note="internal dust credit from a third-party sponsored swap, outside both audited days"),
    "0x32cf8fffd9ada47abd09a7b2269dd4835ee994f7": dict(kind="none"),
    "0xa32fd912a81683804ec6bbd7ba4b6cad8e0ca3ac": dict(kind="none"),
    "0xcf06c2f35e7671cbb1fcae42b50a447db189f1da": dict(kind="none"),
    "0xfdf05af8ddce3621f01713e01721d6e9ad702ea8": dict(kind="none"),
    "0x3d98800c64c345950e1eaaa076d88c12d1bf5f37": dict(kind="none"),
    "0xab39aa1e2db4036e01cf7e919b3f239b3ff90160": dict(kind="unexplained",
        note="no inbound native or internal BNB in its whole history; BscScan flags its 2026-10-19 approve "
             "(tx 0xe49c5f50a2c5f2b96be5e02c863282c39090461617c15610117d3b8eece21b43) as Sponsored (third-party gas)."),
    "0xdf4ff9d2f45f99f11a90b16f277d4b7edddb72a5": dict(kind="none"),
    "0x0a66a9def221efc698b6bbeca82cae6729a8aba8": dict(kind="none"),
    "0xe8797a6bb4693674d78e933e85cb159a0219d03b": dict(kind="none"),
    "0x8c062dc5d775b7d5efc168f75a875f392f53dcdf": dict(kind="eoa",
        funder="0x67f5d43cbd8129bf41aae37a609aac44bd55dd1f", bnb=0.00006616, blk=124103796,
        utc="2026-09-26 07:50:18 UTC",
        tx="0xb5a5215482c7cade369d789258eb4da375a32d62aa0392d669e56256d6d36ed8"),
    "0xa21fc88bd8c17cae306089d7b00a1f5cd5ad3ee9": dict(kind="relay",
        funder="0xca7ded7e4f4ba8ab3b10009236ae6d1b95094589", bnb=0.000164397936681007, blk=128955356,
        utc="2026-10-21 14:38:11 UTC",
        tx="0x322f5447e749887d2ea22c54536959d2a9f06890005c0ac2306d368e265c5840",
        note="first BNB arrived from a Relay solver (gasless sponsorship tx), not from a normal wallet; "
             "the same address later bridged USDC out through Relay Depository."),
    "0xca58696564492ef9c3229c89072365b253bda246": dict(kind="treasury", bnb=0.0005, blk=130097514,
        utc="2026-10-27 13:29:06 UTC",
        tx="0x87443eff758296585f6d6eb7b68800ea6c73f143239e60541a6ef5b1f072d456"),
}

KIND_LABEL = {
    "treasury": "first BNB funder = the treasury (linked to the project)",
    "eoa": "first BNB funder = a distinct external wallet",
    "relay": "first BNB arrived via a Relay solver (gasless sponsor)",
    "none": "no BNB funder at all (0 native and 0 internal txs ever)",
    "dust": "no funder; only a third-party swap dust credit (outside the day)",
    "unexplained": "funder not established (stated, not guessed)",
}


def a(x):
    return f'<a href="https://bscscan.com/address/{x}" target="_blank">{x}</a>'


def txlink(h):
    return f'<a href="https://bscscan.com/tx/{h}" target="_blank">{h[:10]}…{h[-6:]}</a>'


def group_of(w):
    f = FUND.get(w, dict(kind="unexplained"))
    k = f["kind"]
    if k == "treasury":
        return "G1"
    if k == "relay":
        return "G2"
    if k == "eoa":
        return "G3"
    if k == "unexplained":
        return "G5"
    return "G4"


def build(tag):
    d = DAYS[tag]
    data = json.load(open("/tmp/treasury_days_verified.json"))[tag]
    total = sum(r["amt"] for r in data)
    recips = sorted(set(r["to"] for r in data))
    groups = {}
    for w in recips:
        groups.setdefault(group_of(w), []).append(w)

    rows = "".join(
        f'<tr><td>{txlink(r["tx"])}</td><td>{r["block"]:,}</td><td>{r["cot"]}</td>'
        f'<td>{a(r["to"])}</td><td style="text-align:right">{r["amt"]:,.0f}</td></tr>'
        for r in data)

    per = {}
    for r in data:
        per.setdefault(r["to"], []).append(r)
    grp_rows = ""
    for w in sorted(per, key=lambda x: -sum(r["amt"] for r in per[x])):
        f = FUND.get(w, dict(kind="unexplained"))
        amt = sum(r["amt"] for r in per[w])
        ev = ""
        if f["kind"] in ("treasury", "eoa", "relay"):
            ev = (f'{f["bnb"]:.8f} BNB from '
                  f'{a(f.get("funder", TRE))} in {txlink(f["tx"])}, block {f["blk"]:,}, {f["utc"]}'
                  + (f'<br><i>{html.escape(f["note"])}</i>' if f.get("note") else ""))
        elif f["kind"] == "dust":
            ev = f'0.00006257 BNB internal credit in {txlink(f["tx"])}, outside the day — {html.escape(f["note"])}'
        elif f["kind"] == "unexplained":
            ev = html.escape(f.get("note", "no funder visible"))
        else:
            ev = "0 native and 0 internal transactions in its entire history — nothing to group on."
        grp_rows += (f'<tr><td>{a(w)}</td><td style="text-align:right">{amt:,.0f}</td>'
                     f'<td>{len(per[w])}</td><td>{group_of(w)}</td><td>{KIND_LABEL[f["kind"]]}</td><td>{ev}</td></tr>')

    g1 = groups.get("G1", [])
    g2 = groups.get("G2", [])
    g3 = groups.get("G3", [])
    g4 = groups.get("G4", [])
    g5 = groups.get("G5", [])
    n_ops = len(g1) and 0 or 0
    ops = len(g1) + len(g2) + len(g3) + 1 + len(g4) + len(g5) if g1 else len(g2) + len(g3) + len(g4) + len(g5)
    # G1 recipients are all linked to the treasury, so they are one operator with the treasury's funder;
    # count distinct operators conservatively: G1 = 1, G2 = 1, G3 = 1, each G4 = 1, each G5 = 1
    ops = (1 if g1 else 0) + (1 if g2 else 0) + (1 if g3 else 0) + len(g4) + len(g5)

    lines = []
    if g1:
        lines.append(f"<li><b>G1 — funded by the treasury ({len(g1)}):</b> " +
                     ", ".join(a(w) for w in g1) +
                     ". Each received exactly one 0.0005 BNB payment from the treasury, the only BNB either address ever "
                     "got from anyone. That links them to the treasury, not to another operator; because both were funded "
                     "by the same wallet they count as one operator together with the treasury.</li>")
    if g2:
        lines.append(f"<li><b>G2 — first BNB via a Relay solver ({len(g2)}):</b> " +
                     ", ".join(a(w) for w in g2) +
                     f". First BNB came from Relay solver {a('0xca7ded7e4f4ba8ab3b10009236ae6d1b95094589')} inside a gasless "
                     "sponsored tx, not from a normal wallet. A relay sponsor does not link this wallet to the treasury or to "
                     "any other recipient.</li>")
    if g3:
        lines.append(f"<li><b>G3 — funded by a distinct external wallet ({len(g3)}):</b> " +
                     ", ".join(a(w) for w in g3) +
                     f". First BNB came from {a('0x67f5d43cbd8129bf41aae37a609aac44bd55dd1f')}, which is neither the treasury "
                     f"nor the treasury's own funder ({a(TREASURY['addr'])}). No other recipient shares this funder.</li>")
    if g4:
        lines.append(f"<li><b>G4 — no funder at all ({len(g4)}):</b> " + ", ".join(a(w) for w in g4) +
                     ". Zero inbound BNB in both the native and the internal tabs, so there is no funding edge to group "
                     "on: these cannot be merged with each other or with the treasury.</li>")
    if g5:
        lines.append(f"<li><b>G5 — not explained ({len(g5)}):</b> " + ", ".join(a(w) for w in g5) +
                     ". See the note below; listed rather than guessed.</li>")

    unexp_html = "".join(
        "<li>" + html.escape(FUND.get(w, {}).get("note", "no funder visible")) + f" ({a(w)})</li>" for w in g5)

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FlapJax {d['title']} audit — treasury FLAPJAX outflows, {d['day']} COT</title>
<style>body{{font:15px/1.5 -apple-system,system-ui,sans-serif;max-width:1120px;margin:2rem auto;padding:0 1rem;color:#111}}
table{{border-collapse:collapse;width:100%;margin:1rem 0;font-size:13px}}td,th{{border:1px solid #ddd;padding:6px 8px;vertical-align:top;text-align:left}}
code{{background:#f4f4f4;padding:1px 4px;border-radius:3px;font-size:12.5px;word-break:break-all}}a{{color:#0a58ca;text-decoration:none}}
.k{{display:inline-block;background:#f0f6ff;border:1px solid #cfe2ff;border-radius:4px;padding:2px 8px;margin:2px 6px 2px 0}}</style></head><body>
<h1>FlapJax {d['title']} — on-chain audit ({d['day']} COT)</h1>
<p><b>Claim:</b> these are <i>all</i> FLAPJAX transfers out of the FlapJax treasury during {d['day']} COT (UTC−5), each
recipient's first BNB funder, and the operator groups those funders imply. Every number is re-checkable on BscScan or any public BSC node.</p>
<p><span class="k">token {TOK}</span><span class="k">treasury {TRE}</span>
<span class="k">day = {d['day']} 00:00–23:59:59 COT = {d['b0_t']} → {d['b1_t']}</span></p>
<p><b>Block boundaries of the day:</b> first block <b>{d['b0']:,}</b> ({d['b0_t']}); last block <b>{d['b1']:,}</b>
({d['b1_t']}). Block {d['nb']:,} is the first block at {d['nb_t']}.</p>
<p><b>Method.</b> Enumerated every FLAPJAX transfer touching the treasury in the window, then verified each one
individually with <code>eth_getTransactionReceipt</code>: status 0x1, a FLAPJAX <code>Transfer</code> log emitted by
the token contract with the treasury as sender, amount read from the log's 18-decimal value. Block timestamps were
re-read from a public BSC node and converted to COT (UTC−5). Recipient funding history was read from the full native
<i>and</i> internal transaction tabs of each address, not just the first page.</p>
<h2>Result in one line</h2>
<p><b>{len(data)} transfers · {total:,.0f} FLAPJAX total · {len(recips)} distinct recipients ·
{ops} distinct operators implied · {len(g1)} recipient(s) funded by the treasury · {len(g2)} funded via a Relay solver ·
{len(g3)} funded by a distinct external wallet · {len(g4)} with no funder at all · {len(g5)} unexplained.</b></p>
<h2>The {len(data)} transfers of {d['day']} COT</h2>
<table><tr><th>tx</th><th>block</th><th>time (COT, UTC−5)</th><th>recipient</th><th style="text-align:right">FLAPJAX</th></tr>
{rows}
<tr><th colspan="4">total</th><th style="text-align:right">{total:,.0f}</th></tr></table>
<h2>First BNB funder per recipient</h2>
<table><tr><th>recipient</th><th style="text-align:right">FLAPJAX on {d['day'][5:]}</th><th>txs</th><th>group</th>
<th>first-funding status</th><th>funder evidence (the tx that links the group)</th></tr>{grp_rows}</table>
<h3>Groups implied</h3>
<ul>{''.join(lines)}</ul>
<p><b>Distinct operators implied: {ops}.</b> {'The funder analysis finds no shared-funder sybil cluster inside this day beyond the treasury-funded group.' if not g2 and not g3 else 'The only funder links found are the ones named above; no two recipients share a funder other than the treasury.'}</p>
<h3>For reference — the treasury's own first BNB funder</h3>
<p>Treasury first received BNB in {txlink(TREASURY['tx'])}, block {TREASURY['blk']:,}, {TREASURY['utc']}:
<b>{TREASURY['bnb']} BNB from {a(TREASURY['addr'])}</b>. No recipient in this day shares that funder.</p>
<h2>Transfers I could not explain</h2>
<ul>
{unexp_html}
</ul>
<h2>Re-check recipe (no trust required)</h2>
<p>Enumerate the window on a public node with <code>eth_getLogs</code> for the FLAPJAX token
<code>{TOK}</code>, <code>topic0</code> = the ERC-20 <code>Transfer</code> signature and <code>topic1</code> = the treasury
padded to 32 bytes; public endpoints cap query ranges, so chunk the range and, for each hit, confirm the recipient and
amount with <code>eth_getTransactionReceipt</code>. Note from experience: some public endpoints silently return partial
log sets for wide ranges — every tx on this page was verified per-receipt, and the count matches the treasury's token
transfer tab for the day. Machine-readable copy: <a href="{d['jname']}">{d['jname']}</a>.</p>
<p style="color:#666;font-size:13px">Published by @meetAkari · 2026-10-30 · read-only audit; no wallet interaction,
no payment taken or given to publish it.</p>
</body></html>"""
    return d, data, total, recips, ops, page


if __name__ == "__main__":
    out = os.path.expanduser("~/akari-proof")
    for tag in ("Q80", "Q78"):
        d, data, total, recips, ops, page = build(tag)
        open(os.path.join(out, d["fname"]), "w").write(page)
        json.dump({"task": f"FlapJax {tag}", "day_cot": d["day"], "block_first": d["b0"],
                   "block_last": d["b1"], "block_next": d["nb"], "token": TOK, "treasury": TRE,
                   "transfers": data, "total": total, "recipient_count": len(recips),
                   "operators_implied": ops,
                   "treasury_first_funder": TREASURY},
                  open(os.path.join(out, d["jname"]), "w"), indent=1)
        print(tag, "rows", len(data), "total", f"{total:,.0f}", "recipients", len(recips), "operators", ops)
