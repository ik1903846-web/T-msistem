import re, io, zipfile
import pandas as pd

MINIMAL_STYLES = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>'

# ── Kolon sabitleri ───────────────────────────────────────────────────────────
C_SEKTOR    = 'Hisse Sekt\u00f6r'
C_EFK       = 'Esas Faaliyet Kar\u0131 /Zarar\u0131 Net (Y\u0131ll\u0131k)'
C_PD        = 'Piyasa De\u011feri'
C_PDDD      = 'Piyasa De\u011feri / Defter De\u011feri'
C_MARJ      = 'Esas Faaliyet Kar Marj\u0131 (Y\u0131ll\u0131k)'
C_BODE      = 'Toplam Bor\u00e7 / \u00d6zsermaye'
C_NAKIT     = '\u0130\u015fletme Faaliyetlerinden Nakit Ak\u0131\u015flar\u0131'
C_NK        = 'Net D\u00f6nem Kar\u0131 / Zarar\u0131 (Y\u0131ll\u0131k)'
C_FK_ORAN   = 'Fiyat Kazan\u00e7'
C_PD_EFK    = 'Piyasa De\u011feri / Esas Faaliyet Kar\u0131'
C_NS        = 'Net Sat\u0131\u015flar (Y\u0131ll\u0131k)'
C_ROE       = '\u00d6zsermaye Karl\u0131l\u0131\u011f\u0131 (ROE) Y\u0131ll\u0131k (%)'
C_KAPANIS   = 'Hisse Kapan\u0131\u015f'
C_OZKAYNAK  = '\u00d6zkaynaklar'
C_FAVOK     = 'FAV\u00d6K (Y\u0131ll\u0131k)'
C_MARJ_B    = 'Esas Faaliyet Kar Marj\u0131 (Y\u0131ll\u0131k)'
C_DONEN     = 'D\u00f6nen Varl\u0131klar'
C_DURAN     = 'Duran Varl\u0131klar'
C_FIN_GID   = 'Finansman Giderleri'
C_KVB       = 'K\u0131sa Vadeli Bor\u00e7lar'
C_UVB       = 'Uzun Vadeli Bor\u00e7lar'
# Yeni kolonlar
C_FIILI     = 'Fiili Dola\u015f\u0131mdaki Pay'
C_HALKA     = 'Halka A\u00e7\u0131kl\u0131k Oran\u0131'
C_CARI_ORAN = 'Cari Oran'
C_AKTIF_BUY = 'Aktif B\u00fcyüme (%)'
C_FAVOK_BUY = 'FAV\u00d6K B\u00fcy\u00fcme (%) (Y\u0131ll\u0131k)'
C_OZK_BUY   = '\u00d6zsermaye B\u00fcy\u00fcmesi (%)'
C_FAVOK_FIN = 'FAV\u00d6K / Net Finansman Gider'
C_NETBORC_F = 'Net Bor\u00e7 / FAV\u00d6K (Y\u0131ll\u0131k) (%)'
C_PIOTROSKI = 'Piotroski F Skor'
C_NAKIT_BEN = 'Nakit ve Nakit Benzerleri'
C_NET_BORC  = 'Net Bor\u00e7'
C_MDV       = 'Maddi Duran Varl\u0131klar'

ELENEN_SEKTORLER = ['holding', 'gayrimenkul yat', 'portf\u00f6y',
                    'yat\u0131r\u0131m ortakl\u0131\u011f\u0131', 'menkul k\u0131ymet',
                    'giri\u015fim sermayesi']


def fix_xlsx_styles(fb):
    try:
        bi, bo = io.BytesIO(fb), io.BytesIO()
        with zipfile.ZipFile(bi, 'r') as zi:
            with zipfile.ZipFile(bo, 'w', zipfile.ZIP_DEFLATED) as zo:
                for it in zi.infolist():
                    d = zi.read(it.filename)
                    if it.filename == 'xl/styles.xml': d = MINIMAL_STYLES
                    zo.writestr(it, d)
        return bo.getvalue()
    except: return fb


def safe_float(val):
    try: return float(str(val).replace(',', '.').replace('%', ''))
    except: return None


def fmt_milyon(val):
    if val is None: return '-'
    if abs(val) >= 1_000_000_000_000: return f'{val/1_000_000_000_000:.1f}T'
    if abs(val) >= 1_000_000_000:     return f'{val/1_000_000_000:.1f}Mr'
    if abs(val) >= 1_000_000:         return f'{val/1_000_000:.0f}M'
    return f'{val:.0f}'


def read_excel_bytes(fb):
    fb = fix_xlsx_styles(fb)
    try: df = pd.read_excel(io.BytesIO(fb), header=None, engine='openpyxl')
    except:
        try: df = pd.read_excel(io.BytesIO(fb), header=None)
        except: return {}
    data, header = {}, None
    for _, row in df.iterrows():
        rl = [str(v).strip() if pd.notna(v) else '' for v in row]
        if rl and rl[0] == 'Kod': header = rl; continue
        if header and len(rl) >= 2 and rl[0]:
            rd = {header[i]: rl[i] if i < len(rl) else '' for i in range(len(header))}
            kod = rd.get('Kod', '').strip()
            if kod and kod != 'nan': data[kod] = rd
    return data


def donem_from_filename(fn):
    name = (fn.replace('Puanlama_Analizi_Tu_mu__', '')
              .replace('Puanlama Analizi T\u00fcm\u00fc', '')
              .replace('.xlsx', '').replace('__1_', '').replace('__2_', '')
              .replace('_1_', '').replace('_2_', '').strip())
    if name.isdigit() and len(name) == 6: return name
    m = re.search(r'(\d{6})', fn)
    return m.group(1) if m else None


def hesapla_pd(row):
    pd_d = safe_float(row.get(C_PD, ''))
    if pd_d and pd_d > 0: return pd_d
    efk = safe_float(row.get(C_EFK, ''))
    pdefk = safe_float(row.get(C_PD_EFK, ''))
    if efk and pdefk and efk > 0 and pdefk > 0: return efk * pdefk
    return None


def fark_karar(p):
    if p >= 75: return 'GUCLU ADAY'
    if p >= 55: return 'POTANSIYEL'
    if p >= 35: return 'ZAYIF'
    return 'ELENDI'

def geri_karar(p): return fark_karar(p)


def roe_istikrar_hesapla(quarters, donems, kod):
    """
    Son kac donem ust uste ROE >= %30,
    tum gecmiste hic dusmedi mi,
    ve son ROE degeri.
    """
    roe_seri = [safe_float(quarters[d].get(kod, {}).get(
        '\u00d6zsermaye Karl\u0131l\u0131\u011f\u0131 (ROE) Y\u0131ll\u0131k (%)', ''))
        for d in donems]

    # Son kac donem ust uste %30+
    son_kac = 0
    for r in reversed(roe_seri):
        if r is not None and r >= 30:
            son_kac += 1
        elif r is not None:
            break

    # Tum gecmiste hic %30 altina dusmedi mi (min 4 donem sartt)
    gecerli = [r for r in roe_seri if r is not None]
    hic_dusmedi = len(gecerli) >= 4 and all(r >= 30 for r in gecerli)

    # Son ROE
    son_roe = next((r for r in reversed(roe_seri) if r is not None), None)

    return son_kac, hic_dusmedi, son_roe


def roe_donus_hesapla(quarters, donems, kod):
    """
    ROE negatiften pozitife donus sinyali.
    Returns: (donus_var, son_roe, kac_donem_pozitif)
    """
    roe_seri = []
    for d in donems:
        r = safe_float(quarters[d].get(kod, {}).get(C_ROE, ''))
        roe_seri.append(r)

    gecerli = [(i, r) for i, r in enumerate(roe_seri) if r is not None]
    if len(gecerli) < 5:
        return False, None, 0

    son_roe = gecerli[-1][1]
    if son_roe <= 0:
        return False, son_roe, 0

    # Son 2 donem icinde neg->poz gecis var mi?
    gecis = False
    gecis_idx = 0
    for j in range(len(gecerli)-1, max(0, len(gecerli)-3), -1):
        if gecerli[j][1] > 0 and j > 0 and gecerli[j-1][1] < 0:
            gecis = True
            gecis_idx = j
            break

    if not gecis:
        return False, son_roe, 0

    # Onceki en az 2 donem negatif miydi?
    onceki_neg = sum(1 for _, r in gecerli[max(0, gecis_idx-4):gecis_idx] if r < 0)
    if onceki_neg < 2:
        return False, son_roe, 0

    # Donusten bu yana kac donem pozitif?
    kac_poz = len(gecerli) - gecis_idx
    return True, son_roe, kac_poz


def bebek_karar(p):
    if p >= 80: return 'KARINCA GUCLU'
    if p >= 60: return 'BEBEK ADAY'
    if p >= 50: return 'IZLE'
    return 'ZAYIF'


class UnifiedEngine:
    def __init__(self, quarters_data):
        self.quarters = quarters_data
        self.sorted_donems = sorted(quarters_data.keys())
        self.son_donem = self.sorted_donems[-1] if self.sorted_donems else None
        self.son_data  = quarters_data.get(self.son_donem, {}) if self.son_donem else {}

    def _seri(self, kod, col):
        return [safe_float(self.quarters[d].get(kod, {}).get(col, ''))
                for d in self.sorted_donems]

    def _pd_seri(self, kod):
        return [hesapla_pd(self.quarters[d].get(kod, {}))
                for d in self.sorted_donems]

    def _buyume(self, seri, yil):
        hedef = yil * 4
        ei = max(0, len(seri) - 1 - hedef)
        sv = next((x for x in reversed(seri) if x and x > 0), None)
        ev = next((seri[i] for i in range(ei, min(ei+3, len(seri)))
                   if seri[i] and seri[i] > 0), None)
        if sv and ev: return (sv - ev) / abs(ev) * 100
        return None

    # ── FARK ─────────────────────────────────────────────────────────────────
    def fark_analiz(self, kod):
        son = self.son_data.get(kod, {})
        if not son: return None
        fk_son  = safe_float(son.get(C_EFK, ''))
        nk_son  = safe_float(son.get(C_NK, ''))
        marj    = safe_float(son.get(C_MARJ, ''))
        pddd    = safe_float(son.get(C_PDDD, ''))
        bode    = safe_float(son.get(C_BODE, ''))
        nakit   = safe_float(son.get(C_NAKIT, ''))
        pd_val  = hesapla_pd(son)
        sektor  = son.get(C_SEKTOR, '')
        favok   = safe_float(son.get(C_FAVOK, ''))
        fkpd    = (fk_son/pd_val*100) if fk_son and pd_val and pd_val>0 and fk_son>0 else None

        fk_seri = self._seri(kod, C_EFK)
        nk_seri = self._seri(kod, C_NK)
        pd_seri = self._pd_seri(kod)
        s = sektor.lower()

        # F1
        finansal = any(e in s for e in ELENEN_SEKTORLER)
        if finansal:
            valid = [x for x in fk_seri if x is not None]
            if not (len(valid) >= 6 and sum(1 for x in valid[-8:] if x > 0) >= 6):
                return None

        # F2
        son8 = [x for x in fk_seri[-8:] if x is not None]
        if len(son8) < 4: return None
        if sum(1 for x in son8 if x > 0) < max(4, int(len(son8)*0.6)): return None

        # F3
        if not fk_son or fk_son <= 0: return None
        ei = max(0, len(fk_seri)-9)
        fk_eski = next((fk_seri[i] for i in range(ei, min(ei+3, len(fk_seri)))
                        if fk_seri[i] and fk_seri[i] > 0), None)
        if not fk_eski: return None
        buyume = (fk_son - fk_eski) / abs(fk_eski) * 100
        esik = 5 if ((pddd and pddd < 1) or (fkpd and fkpd > 15)) else 20
        if buyume < esik: return None

        # F4
        son4_nk = [x for x in nk_seri[-4:] if x is not None]
        son4_fk = [x for x in fk_seri[-4:] if x is not None]
        if len(son4_nk) >= 4 and all(x < 0 for x in son4_nk):
            if len(son4_fk) >= 2 and all(x < 0 for x in son4_fk[-2:]): return None

        # Puan A
        buyuyen = sum(1 for i in range(1, len(fk_seri))
                      if fk_seri[i-1] and fk_seri[i] and fk_seri[i-1]>0 and fk_seri[i]>fk_seri[i-1])
        br = buyuyen / (len(fk_seri)-1 or 1)
        a = 30 if br>=0.8 else (20 if br>=0.6 else (10 if br>=0.4 else 0))
        if buyume>=200: a+=5
        elif buyume>=100: a+=3
        elif buyume>=50: a+=1
        a = min(a, 35)

        # B
        b = 0
        if pddd:
            if pddd<1: b+=12
            elif pddd<3: b+=9
            elif pddd<6: b+=5
        pd_eski = next((pd_seri[i] for i in range(ei, min(ei+3, len(pd_seri)))
                        if pd_seri[i] and pd_seri[i] > 0), None)
        if pd_eski and pd_val and pd_val > 0:
            pd_buy = (pd_val - pd_eski) / pd_eski * 100
            if buyume > pd_buy*2: b+=13
            elif buyume > pd_buy: b+=8
        if pd_val and fk_son and fk_son > 0:
            r = pd_val / fk_son
            if r < 5: b+=10
            elif r < 15: b+=3
        b = min(b, 48)

        # C
        c = 0
        if marj:
            if marj>20: c+=10
            elif marj>10: c+=7
            elif marj>5: c+=4
            else: c+=1
        if fk_son and fk_son>0 and nk_son is not None:
            rn = nk_son/fk_son*100
            if rn>60: c+=8
            elif rn>30: c+=5
            elif rn>0: c+=2
            else: c+=1
        elif fk_son and fk_son > 0: c+=1
        if nakit and nakit > 0: c+=7
        c = min(c, 25)

        # D
        d = 0
        if any(x in s for x in ['finans','faktoring','sigorta','enerji','sa\u011fl\u0131k',
                                  'ila\u00e7','su','elektrik','savunma','ileti\u015fim']):
            d+=8
        elif any(x in s for x in ['sanayi','tekstil','g\u0131da','i\u00e7ecek','perakende',
                                    'ula\u015ft\u0131rma','kimya','mobilya','orman','\u00e7imento']):
            d+=5
        else: d+=2
        if pd_val:
            if pd_val<2_000_000_000: d+=7
            elif pd_val<20_000_000_000: d+=4
            else: d+=1
        if bode:
            if bode<100: d+=5
            elif bode<300: d+=3
        if favok and fk_son and favok > fk_son*1.2: d+=2
        d = min(d, 20)

        puan = round(a+b+c+d, 1)
        return {
            'kod':kod,'sektor':sektor,'puan':puan,'karar':fark_karar(puan),
            'fk':fk_son,'pd':pd_val,'pddd':pddd,'marj':marj,
            'fkpd':fkpd,'buyume':buyume,'A':a,'B':b,'C':c,'D':d,
            'favok':favok,'nk':nk_son,'nakit':nakit,
        }

    # ── GERI ─────────────────────────────────────────────────────────────────
    def geri_analiz(self, kod, yil=3):
        son = self.son_data.get(kod, {})
        if not son: return None
        fk_oran = safe_float(son.get(C_FK_ORAN, ''))
        pddd    = safe_float(son.get(C_PDDD, ''))
        efk_son = safe_float(son.get(C_EFK, ''))
        pd_efk  = safe_float(son.get(C_PD_EFK, ''))
        ns_son  = safe_float(son.get(C_NS, ''))
        roe     = safe_float(son.get(C_ROE, ''))
        sektor  = son.get(C_SEKTOR, '')
        pd_val  = hesapla_pd(son)
        favok   = safe_float(son.get(C_FAVOK, ''))

        if fk_oran is not None and (fk_oran<=0 or fk_oran>=30): return None
        if pddd is None or pddd>=5: return None
        if efk_son is not None and efk_son<=0: return None

        fkpd = ((1/pd_efk*100) if pd_efk and pd_efk>0
                else ((efk_son/pd_val*100) if efk_son and pd_val and pd_val>0 else None))

        efk_seri = self._seri(kod, C_EFK)
        pd_seri  = self._pd_seri(kod)
        ns_seri  = self._seri(kod, C_NS)
        efk_buy  = self._buyume(efk_seri, yil)
        pd_buy   = self._buyume(pd_seri, yil)
        ns_buy   = self._buyume(ns_seri, yil)

        m1 = 0
        if fkpd:
            if fkpd>=25: m1=25
            elif fkpd>=15: m1=18
            elif fkpd>=8: m1=10
            else: m1=4

        m2 = 0
        if efk_buy is not None:
            if efk_buy>=400: m2=30
            elif efk_buy>=200: m2=24
            elif efk_buy>=100: m2=16
            elif efk_buy>=50: m2=10
            elif efk_buy>0: m2=5

        m3 = 0
        if pd_buy is not None and efk_buy is not None:
            if pd_buy<efk_buy/2: m3=20
            elif pd_buy<efk_buy: m3=14
            elif pd_buy<50: m3=8
            elif pd_buy<100: m3=4
            else: m3=1
        elif pd_buy is not None:
            if pd_buy<50: m3=8
            elif pd_buy<100: m3=4
            else: m3=1

        m4 = 0
        if ns_buy is not None:
            if ns_buy>=300: m4=15
            elif ns_buy>=150: m4=11
            elif ns_buy>=75: m4=7
            elif ns_buy>0: m4=3

        bonus = 0
        if efk_buy and pd_buy:
            if efk_buy>pd_buy*2: bonus=10
            elif efk_buy>pd_buy: bonus=5
        if favok and efk_son and efk_son>0 and favok>efk_son*1.3:
            bonus = min(bonus+2, 12)

        puan = round(min(m1+m2+m3+m4+bonus, 100), 1)
        return {
            'kod':kod,'sektor':sektor,'puan':puan,'karar':geri_karar(puan),
            'fk_oran':fk_oran,'pddd':pddd,'fkpd':fkpd,
            'efk_buy':efk_buy,'pd_buy':pd_buy,'ns_buy':ns_buy,
            'pd_val':pd_val,'roe':roe,'favok':favok,
            'fiyat_geride':bool(efk_buy and pd_buy and efk_buy>pd_buy),
            'm1':m1,'m2':m2,'m3':m3,'m4':m4,'bonus':bonus,
        }

    # ── BEBEK HİSSE ───────────────────────────────────────────────────────────
    def bebek_analiz(self, kod):
        son = self.son_data.get(kod, {})
        if not son: return None

        sektor    = son.get(C_SEKTOR, '')
        pd_val    = hesapla_pd(son)
        ozkaynak  = safe_float(son.get(C_OZKAYNAK, ''))
        efk       = safe_float(son.get(C_EFK, ''))
        marj      = safe_float(son.get(C_MARJ, ''))
        roe       = safe_float(son.get(C_ROE, ''))
        pddd      = safe_float(son.get(C_PDDD, ''))
        favok     = safe_float(son.get(C_FAVOK, ''))
        mdv       = safe_float(son.get(C_MDV, ''))
        duran     = safe_float(son.get(C_DURAN, ''))
        net_borc  = safe_float(son.get(C_NET_BORC, ''))
        nakit_ben = safe_float(son.get(C_NAKIT_BEN, ''))
        piotroski = safe_float(son.get(C_PIOTROSKI, ''))
        cari_oran = safe_float(son.get(C_CARI_ORAN, ''))
        ozk_buy   = safe_float(son.get(C_OZK_BUY, ''))
        favok_fin = safe_float(son.get(C_FAVOK_FIN, ''))
        aktif_buy = safe_float(son.get(C_AKTIF_BUY, ''))
        halka     = safe_float(son.get(C_HALKA, ''))
        fiili     = safe_float(son.get(C_FIILI, ''))
        fkpd      = (efk/pd_val*100) if efk and pd_val and pd_val>0 and efk>0 else None
        pd_efk_v  = safe_float(son.get(C_PD_EFK, ''))
        if pd_efk_v and pd_efk_v > 0: fkpd = 1/pd_efk_v*100

        # Temel filtreler
        if not pd_val or pd_val <= 0: return None
        if not ozkaynak or ozkaynak <= 0: return None
        if not efk or efk <= 0: return None  # EFK pozitif olmali

        # ── Puanlama ──────────────────────────────────────────────────────────

        # A — Küçük Cüsse (max 25p)
        # Özkaynak küçük olmalı — bu "bebek" kriteri
        a = 0
        if ozkaynak < 500_000_000: a = 25
        elif ozkaynak < 2_000_000_000: a = 18
        elif ozkaynak < 10_000_000_000: a = 10
        else: a = 3

        # B — Kaldıraç Büyüklüğü (max 30p)
        # Marj yüksek + ROE yüksek + FK/PD% yüksek = kaldıraç büyük
        b = 0
        if marj:
            if marj >= 40: b += 12
            elif marj >= 20: b += 8
            elif marj >= 10: b += 4
            else: b += 1
        if roe:
            if roe >= 30: b += 10
            elif roe >= 15: b += 6
            elif roe >= 5: b += 3
        if fkpd:
            if fkpd >= 50: b += 8
            elif fkpd >= 25: b += 5
            elif fkpd >= 15: b += 3
        b = min(b, 30)

        # C — Değerlenmemiş Varlıklar (max 20p)
        # PD/DD < 1 + Maddi Duran Varlık büyük = gizli değer var
        c = 0
        if pddd:
            if pddd < 0.5: c += 12
            elif pddd < 1.0: c += 8
            elif pddd < 2.0: c += 4
        if mdv and pd_val:
            mdv_pd = mdv / pd_val * 100
            if mdv_pd >= 100: c += 8  # MDV piyasa degerinden buyuk!
            elif mdv_pd >= 50: c += 5
            elif mdv_pd >= 25: c += 2
        c = min(c, 20)

        # D — Finansal Saglik (max 15p)
        d = 0
        if piotroski:
            if piotroski >= 7: d += 8
            elif piotroski >= 5: d += 5
            elif piotroski >= 3: d += 2
        if cari_oran:
            if cari_oran >= 2: d += 4
            elif cari_oran >= 1.2: d += 2
        if favok_fin and favok_fin > 3: d += 3
        d = min(d, 15)

        # E — Büyüme Potansiyeli (max 10p)
        e = 0
        if ozk_buy and ozk_buy > 0:
            if ozk_buy >= 50: e += 5
            elif ozk_buy >= 20: e += 3
            else: e += 1
        if aktif_buy and aktif_buy > 0:
            if aktif_buy >= 30: e += 3
            elif aktif_buy >= 10: e += 1
        if nakit_ben and net_borc:
            if nakit_ben > abs(net_borc): e += 2  # net nakit pozisyonunda
        e = min(e, 10)

        puan = round(a+b+c+d+e, 1)

        # 10x Potansiyel Hesabi
        # Teorik adil deger: EFK * sektör F/K carpani (konservativ: 15x)
        # 10x icin: hedef PD = min(EFK*15, Özkaynak*3)
        efk_carpan = 15.0
        hedef_pd_efk = efk * efk_carpan if efk else None
        hedef_pd_ozk = ozkaynak * 3.0 if ozkaynak else None
        hedef_pd = None
        if hedef_pd_efk and hedef_pd_ozk:
            hedef_pd = min(hedef_pd_efk, hedef_pd_ozk)
        elif hedef_pd_efk: hedef_pd = hedef_pd_efk
        elif hedef_pd_ozk: hedef_pd = hedef_pd_ozk

        potansiyel_x = (hedef_pd / pd_val) if hedef_pd and pd_val and pd_val > 0 else None

        return {
            'kod':kod,'sektor':sektor,'puan':puan,'karar':bebek_karar(puan),
            'pd_val':pd_val,'ozkaynak':ozkaynak,'efk':efk,'marj':marj,
            'roe':roe,'pddd':pddd,'fkpd':fkpd,'favok':favok,
            'mdv':mdv,'net_borc':net_borc,'nakit_ben':nakit_ben,
            'piotroski':piotroski,'cari_oran':cari_oran,
            'ozk_buy':ozk_buy,'aktif_buy':aktif_buy,
            'halka':halka,'fiili':fiili,
            'hedef_pd':hedef_pd,'potansiyel_x':potansiyel_x,
            'A':a,'B':b,'C':c,'D':d,'E':e,
        }

    # ── Toplu tarama ─────────────────────────────────────────────────────────
    def fark_tara(self):
        res = [r for kod in sorted(self.son_data)
               if (r := self.fark_analiz(kod)) is not None]
        res.sort(key=lambda x: x['puan'], reverse=True)
        return res

    def geri_tara(self, yil=3):
        res = [r for kod in sorted(self.son_data)
               if (r := self.geri_analiz(kod, yil)) is not None]
        res.sort(key=lambda x: x['puan'], reverse=True)
        return res

    def bebek_tara(self):
        res = [r for kod in sorted(self.son_data)
               if (r := self.bebek_analiz(kod)) is not None]
        res.sort(key=lambda x: x['puan'], reverse=True)
        return res

    def kesisim_tara(self, yil=3):
        fark_map = {r['kod']: r for r in self.fark_tara()}
        geri_map = {r['kod']: r for r in self.geri_tara(yil)}
        res = []
        for kod in fark_map:
            if kod in geri_map:
                res.append({
                    'kod':kod,'sektor':fark_map[kod]['sektor'],
                    'fark_puan':fark_map[kod]['puan'],'fark_karar':fark_map[kod]['karar'],
                    'geri_puan':geri_map[kod]['puan'],'geri_karar':geri_map[kod]['karar'],
                    'toplam':round(fark_map[kod]['puan']+geri_map[kod]['puan'],1),
                    'fkpd':geri_map[kod].get('fkpd'),
                    'efk_buy':geri_map[kod].get('efk_buy'),
                    'pd_buy':geri_map[kod].get('pd_buy'),
                    'fiyat_geride':geri_map[kod].get('fiyat_geride'),
                    'pd_val':geri_map[kod].get('pd_val'),
                    'pddd':fark_map[kod].get('pddd'),
                    'marj':fark_map[kod].get('marj'),
                    'favok':fark_map[kod].get('favok'),
                    'A':fark_map[kod]['A'],'B':fark_map[kod]['B'],
                    'C':fark_map[kod]['C'],'D':fark_map[kod]['D'],
                })
        res.sort(key=lambda x: x['toplam'], reverse=True)
        return res

    def istatistik(self, yil=3):
        return {
            'toplam':len(self.son_data),
            'fark':len(self.fark_tara()),
            'geri':len(self.geri_tara(yil)),
            'kesisim':len(self.kesisim_tara(yil)),
            'bebek':len(self.bebek_tara()),
        }


# ── Derinlemesine Analiz ─────────────────────────────────────────────────────
class DerinAnaliz:
    def __init__(self, engine, kod):
        self.engine = engine
        self.kod = kod
        self.son = engine.son_data.get(kod, {})
        self.sektor = self.son.get(C_SEKTOR, '')
        self.donems = engine.sorted_donems

    def _sektor_hisseleri(self):
        return [k for k,v in self.engine.son_data.items()
                if v.get(C_SEKTOR,'') == self.sektor and k != self.kod]

    def sektor_medyan(self, col):
        vals = [safe_float(self.engine.son_data[k].get(col,''))
                for k in self._sektor_hisseleri()]
        vals = [v for v in vals if v is not None and v > 0]
        if not vals: return None
        vals.sort()
        n = len(vals)
        return vals[n//2] if n%2 else (vals[n//2-1]+vals[n//2])/2

    def hisse_seri(self, col):
        return [{'donem': f"{d[:4]}/{d[4:]}",
                 'deger': safe_float(self.engine.quarters[d].get(self.kod,{}).get(col,''))}
                for d in self.donems]

    def pd_seri(self):
        return [{'donem': f"{d[:4]}/{d[4:]}",
                 'deger': hesapla_pd(self.engine.quarters[d].get(self.kod,{}))}
                for d in self.donems]

    def toplam_varlik_seri(self):
        seri = []
        for d in self.donems:
            row = self.engine.quarters[d].get(self.kod, {})
            donen = safe_float(row.get(C_DONEN,''))
            duran = safe_float(row.get(C_DURAN,''))
            val = (donen+duran) if donen and duran else (donen or duran)
            seri.append({'donem': f"{d[:4]}/{d[4:]}", 'deger': val})
        return seri

    def sektor_seri(self, col):
        seri = []
        for d in self.donems:
            vals = [safe_float(self.engine.quarters[d].get(k,{}).get(col,''))
                    for k in self._sektor_hisseleri()]
            vals = [v for v in vals if v is not None and v > 0]
            if vals:
                vals.sort()
                n = len(vals)
                med = vals[n//2] if n%2 else (vals[n//2-1]+vals[n//2])/2
            else: med = None
            seri.append({'donem': f"{d[:4]}/{d[4:]}", 'deger': med})
        return seri

    def kat_buyume_tablosu(self):
        kolonlar = [
            ('Donem Kari',    self.hisse_seri(C_NK)),
            ('EFK',           self.hisse_seri(C_EFK)),
            ('FAVOK',         self.hisse_seri(C_FAVOK)),
            ('Net Satislar',  self.hisse_seri(C_NS)),
            ('Ozkaynaklar',   self.hisse_seri(C_OZKAYNAK)),
            ('Toplam Varlik', self.toplam_varlik_seri()),
            ('Donen Varlik',  self.hisse_seri(C_DONEN)),
            ('Duran Varlik',  self.hisse_seri(C_DURAN)),
            ('KV Borc',       self.hisse_seri(C_KVB)),
            ('UV Borc',       self.hisse_seri(C_UVB)),
            ('Piyasa Degeri', self.pd_seri()),
        ]
        tablo = []
        for isim, seri in kolonlar:
            vals = [s['deger'] for s in seri]
            ilk = next((v for v in vals if v and v > 0), None)
            son = next((v for v in reversed(vals) if v and v > 0), None)
            kat = round(son/ilk, 1) if ilk and son and ilk > 0 else None
            yuzde = round((son-ilk)/ilk*100, 0) if ilk and son else None
            tablo.append({'kalem':isim,'ilk':ilk,'son':son,'kat':kat,'yuzde':yuzde,'seri':seri})
        return tablo

    def deger_kart(self):
        metriks = [
            ('FK/PD%',   None,      True),
            ('PD/DD',    C_PDDD,    False),
            ('F/K',      C_FK_ORAN, False),
            ('ROE%',     C_ROE,     True),
            ('Marj%',    C_MARJ,    True),
            ('Piotroski',C_PIOTROSKI,True),
        ]
        sonuc = []
        for isim, col, yuksek_iyi in metriks:
            if isim == 'FK/PD%':
                pd_efk = safe_float(self.son.get(C_PD_EFK,''))
                efk = safe_float(self.son.get(C_EFK,''))
                pd = hesapla_pd(self.son)
                hisse_val = ((1/pd_efk*100) if pd_efk and pd_efk>0
                             else ((efk/pd*100) if efk and pd and pd>0 else None))
                sek_pdefk = self.sektor_medyan(C_PD_EFK)
                sektor_val = (1/sek_pdefk*100) if sek_pdefk and sek_pdefk>0 else None
            else:
                hisse_val = safe_float(self.son.get(col,''))
                sektor_val = self.sektor_medyan(col)

            if hisse_val is None or sektor_val is None: durum='veri_yok'
            elif yuksek_iyi: durum='iyi' if hisse_val>sektor_val else 'kotu'
            else: durum='iyi' if hisse_val<sektor_val else 'kotu'

            fark_pct = ((hisse_val-sektor_val)/sektor_val*100
                        if hisse_val and sektor_val else None)
            sonuc.append({'isim':isim,'hisse':hisse_val,'sektor':sektor_val,
                          'durum':durum,'fark_pct':fark_pct,'yuksek_iyi':yuksek_iyi})
        return sonuc
