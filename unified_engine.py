import re, io, zipfile
import pandas as pd

MINIMAL_STYLES = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>'

# ── Kolon adlari ─────────────────────────────────────────────────────────────
C_SEKTOR   = 'Hisse Sekt\u00f6r'
C_EFK      = 'Esas Faaliyet Kar\u0131 /Zarar\u0131 Net (Y\u0131ll\u0131k)'
C_PD       = 'Piyasa De\u011feri'
C_PDDD     = 'Piyasa De\u011feri / Defter De\u011feri'
C_MARJ     = 'Esas Faaliyet Kar Marj\u0131 (Y\u0131ll\u0131k)'
C_BODE     = 'Toplam Bor\u00e7 / \u00d6zsermaye'
C_NAKIT    = '\u0130\u015fletme Faaliyetlerinden Nakit Ak\u0131\u015flar\u0131'
C_NK       = 'Net D\u00f6nem Kar\u0131 / Zarar\u0131 (Y\u0131ll\u0131k)'
C_FK_ORAN  = 'Fiyat Kazan\u00e7'
C_PD_EFK   = 'Piyasa De\u011feri / Esas Faaliyet Kar\u0131'
C_NS       = 'Net Sat\u0131\u015flar (Y\u0131ll\u0131k)'
C_ROE      = '\u00d6zsermaye Karl\u0131l\u0131\u011f\u0131 (ROE) Y\u0131ll\u0131k (%)'
C_KAPANIS  = 'Hisse Kapan\u0131\u015f'
C_OZKAYNAK = '\u00d6zkaynaklar'

ELENEN_SEKTORLER = ['holding', 'gayrimenkul yat', 'portf\u00f6y',
                    'yat\u0131r\u0131m ortakl\u0131\u011f\u0131', 'menkul k\u0131ymet',
                    'giri\u015fim sermayesi']


def fix_xlsx_styles(fb):
    try:
        bi, bo = io.BytesIO(fb), io.BytesIO()
        with zipfile.ZipFile(bi,'r') as zi:
            with zipfile.ZipFile(bo,'w',zipfile.ZIP_DEFLATED) as zo:
                for it in zi.infolist():
                    d = zi.read(it.filename)
                    if it.filename == 'xl/styles.xml': d = MINIMAL_STYLES
                    zo.writestr(it, d)
        return bo.getvalue()
    except: return fb


def safe_float(val):
    try: return float(str(val).replace(',','.').replace('%',''))
    except: return None


def fmt_milyon(val):
    if val is None: return '-'
    if abs(val)>=1_000_000_000_000: return f'{val/1_000_000_000_000:.1f}T'
    if abs(val)>=1_000_000_000:     return f'{val/1_000_000_000:.1f}Mr'
    if abs(val)>=1_000_000:         return f'{val/1_000_000:.0f}M'
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
        if header and len(rl)>=2 and rl[0]:
            rd = {header[i]: rl[i] if i<len(rl) else '' for i in range(len(header))}
            kod = rd.get('Kod','').strip()
            if kod and kod!='nan': data[kod] = rd
    return data


def donem_from_filename(fn):
    name = (fn.replace('Puanlama_Analizi_Tu_mu__','')
              .replace('Puanlama Analizi T\u00fcm\u00fc','')
              .replace('.xlsx','').replace('__1_','').replace('__2_','')
              .replace('_1_','').replace('_2_','').strip())
    if name.isdigit() and len(name)==6: return name
    m = re.search(r'(\d{6})', fn)
    return m.group(1) if m else None


def hesapla_pd(row):
    pd_d = safe_float(row.get(C_PD,''))
    if pd_d and pd_d>0: return pd_d
    efk = safe_float(row.get(C_EFK,''))
    pdefk = safe_float(row.get(C_PD_EFK,''))
    if efk and pdefk and efk>0 and pdefk>0: return efk*pdefk
    ns = safe_float(row.get(C_NS,''))
    pdns = safe_float(row.get('Piyasa De\u011feri / Net Sat\u0131\u015f',''))
    if ns and pdns and ns>0 and pdns>0: return ns*pdns
    return None


# ── FARK puanlama ─────────────────────────────────────────────────────────────
def fark_karar(puan):
    if puan>=75: return 'GUCLU ADAY'
    if puan>=55: return 'POTANSIYEL'
    if puan>=35: return 'ZAYIF'
    return 'ELENDI'

def geri_karar(puan):
    if puan>=75: return 'GUCLU ADAY'
    if puan>=55: return 'POTANSIYEL'
    if puan>=35: return 'ZAYIF'
    return 'ELENDI'


class UnifiedEngine:
    def __init__(self, quarters_data):
        self.quarters = quarters_data
        self.sorted_donems = sorted(quarters_data.keys())
        self.son_donem = self.sorted_donems[-1] if self.sorted_donems else None
        self.son_data  = quarters_data.get(self.son_donem, {}) if self.son_donem else {}

    # ── Seri yardimcilari ────────────────────────────────────────────────────
    def _seri(self, kod, col):
        return [safe_float(self.quarters[d].get(kod,{}).get(col,''))
                for d in self.sorted_donems]

    def _pd_seri(self, kod):
        return [hesapla_pd(self.quarters[d].get(kod,{})) for d in self.sorted_donems]

    def _buyume(self, seri, yil):
        hedef = yil*4
        ei = max(0, len(seri)-1-hedef)
        sv = next((x for x in reversed(seri) if x and x>0), None)
        ev = next((seri[i] for i in range(ei, min(ei+3,len(seri))) if seri[i] and seri[i]>0), None)
        if sv and ev: return (sv-ev)/abs(ev)*100
        return None

    # ── FARK analizi ─────────────────────────────────────────────────────────
    def fark_analiz(self, kod):
        son = self.son_data.get(kod, {})
        if not son: return None

        fk_son = safe_float(son.get(C_EFK,''))
        nk_son = safe_float(son.get(C_NK,''))
        marj   = safe_float(son.get(C_MARJ,''))
        pddd   = safe_float(son.get(C_PDDD,''))
        bode   = safe_float(son.get(C_BODE,''))
        nakit  = safe_float(son.get(C_NAKIT,''))
        pd_val = hesapla_pd(son)
        sektor = son.get(C_SEKTOR,'')
        fkpd   = (fk_son/pd_val*100) if fk_son and pd_val and pd_val>0 and fk_son>0 else None

        fk_seri = self._seri(kod, C_EFK)
        nk_seri = self._seri(kod, C_NK)
        pd_seri = self._pd_seri(kod)

        # F1
        s = sektor.lower()
        finansal = any(e in s for e in ELENEN_SEKTORLER)
        if finansal:
            valid = [x for x in fk_seri if x is not None]
            if not (len(valid)>=6 and sum(1 for x in valid[-8:] if x>0)>=6):
                return None

        # F2
        son8 = [x for x in fk_seri[-8:] if x is not None]
        if len(son8)<4: return None
        pozitif = sum(1 for x in son8 if x>0)
        if pozitif < max(4, int(len(son8)*0.6)): return None

        # F3
        if not fk_son or fk_son<=0: return None
        ei = max(0, len(fk_seri)-9)
        fk_eski = next((fk_seri[i] for i in range(ei, min(ei+3,len(fk_seri)))
                        if fk_seri[i] and fk_seri[i]>0), None)
        if not fk_eski: return None
        buyume = (fk_son-fk_eski)/abs(fk_eski)*100
        esik = 5 if ((pddd and pddd<1) or (fkpd and fkpd>15)) else 20
        if buyume < esik: return None

        # F4
        son4_nk = [x for x in nk_seri[-4:] if x is not None]
        son4_fk = [x for x in fk_seri[-4:] if x is not None]
        if len(son4_nk)>=4 and all(x<0 for x in son4_nk):
            if len(son4_fk)>=2 and all(x<0 for x in son4_fk[-2:]):
                return None

        # Puanlama A
        buyuyen = sum(1 for i in range(1,len(fk_seri))
                      if fk_seri[i-1] and fk_seri[i] and fk_seri[i-1]>0 and fk_seri[i]>fk_seri[i-1])
        br = buyuyen/(len(fk_seri)-1 or 1)
        a = 30 if br>=0.8 else (20 if br>=0.6 else (10 if br>=0.4 else 0))
        if buyume>=200: a+=5
        elif buyume>=100: a+=3
        elif buyume>=50: a+=1
        a = min(a,35)

        # B
        b=0
        if pddd:
            if pddd<1: b+=12
            elif pddd<3: b+=9
            elif pddd<6: b+=5
        pd_eski = next((pd_seri[i] for i in range(ei, min(ei+3,len(pd_seri)))
                        if pd_seri[i] and pd_seri[i]>0), None)
        if pd_eski and pd_val and pd_val>0:
            pd_buy = (pd_val-pd_eski)/pd_eski*100
            if buyume>pd_buy*2: b+=13
            elif buyume>pd_buy: b+=8
        if pd_val and fk_son and fk_son>0:
            r = pd_val/fk_son
            if r<5: b+=10
            elif r<15: b+=3
        b = min(b,48)

        # C
        c=0
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
        elif fk_son and fk_son>0: c+=1
        if nakit and nakit>0: c+=7
        c = min(c,25)

        # D
        d=0
        if any(x in s for x in ['finans','faktoring','tasarruf','sigorta','enerji',
                                  'sa\u011fl\u0131k','ila\u00e7','su','elektrik','savunma','ileti\u015fim']):
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
        d = min(d,20)

        puan = round(a+b+c+d, 1)
        return {
            'kod':kod, 'sektor':sektor, 'puan':puan, 'karar':fark_karar(puan),
            'fk':fk_son, 'pd':pd_val, 'pddd':pddd, 'marj':marj,
            'fkpd':fkpd, 'buyume':buyume, 'A':a,'B':b,'C':c,'D':d,
        }

    # ── GERI analizi ─────────────────────────────────────────────────────────
    def geri_analiz(self, kod, yil=3):
        son = self.son_data.get(kod, {})
        if not son: return None

        fk_oran = safe_float(son.get(C_FK_ORAN,''))
        pddd    = safe_float(son.get(C_PDDD,''))
        efk_son = safe_float(son.get(C_EFK,''))
        pd_efk  = safe_float(son.get(C_PD_EFK,''))
        ns_son  = safe_float(son.get(C_NS,''))
        roe     = safe_float(son.get(C_ROE,''))
        kapanis = safe_float(son.get(C_KAPANIS,''))
        sektor  = son.get(C_SEKTOR,'')
        pd_val  = hesapla_pd(son)

        if fk_oran is not None and (fk_oran<=0 or fk_oran>=30): return None
        if pddd is None or pddd>=5: return None
        if efk_son is not None and efk_son<=0: return None

        fkpd = ((1/pd_efk*100) if pd_efk and pd_efk>0
                else ((efk_son/pd_val*100) if efk_son and pd_val and pd_val>0 else None))

        efk_seri = self._seri(kod, C_EFK)
        pd_seri  = self._pd_seri(kod)
        ns_seri  = self._seri(kod, C_NS)

        efk_buy = self._buyume(efk_seri, yil)
        pd_buy  = self._buyume(pd_seri,  yil)
        ns_buy  = self._buyume(ns_seri,  yil)

        m1=0
        if fkpd:
            if fkpd>=25: m1=25
            elif fkpd>=15: m1=18
            elif fkpd>=8: m1=10
            else: m1=4

        m2=0
        if efk_buy is not None:
            if efk_buy>=400: m2=30
            elif efk_buy>=200: m2=24
            elif efk_buy>=100: m2=16
            elif efk_buy>=50: m2=10
            elif efk_buy>0: m2=5

        m3=0
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

        m4=0
        if ns_buy is not None:
            if ns_buy>=300: m4=15
            elif ns_buy>=150: m4=11
            elif ns_buy>=75: m4=7
            elif ns_buy>0: m4=3

        bonus=0
        if efk_buy and pd_buy:
            if efk_buy>pd_buy*2: bonus=10
            elif efk_buy>pd_buy: bonus=5

        puan = round(min(m1+m2+m3+m4+bonus,100),1)
        return {
            'kod':kod, 'sektor':sektor, 'puan':puan, 'karar':geri_karar(puan),
            'fk_oran':fk_oran, 'pddd':pddd, 'fkpd':fkpd,
            'efk_buy':efk_buy, 'pd_buy':pd_buy, 'ns_buy':ns_buy,
            'pd_val':pd_val, 'roe':roe, 'kapanis':kapanis,
            'fiyat_geride': bool(efk_buy and pd_buy and efk_buy>pd_buy),
            'm1':m1,'m2':m2,'m3':m3,'m4':m4,'bonus':bonus,
        }

    # ── Toplu tarama ─────────────────────────────────────────────────────────
    def fark_tara(self):
        res = []
        elendi = {'F1':[],'F2':[],'F3':[],'F4':[]}
        for kod in sorted(self.son_data):
            r = self.fark_analiz(kod)
            if r: res.append(r)
        res.sort(key=lambda x: x['puan'], reverse=True)
        return res

    def geri_tara(self, yil=3):
        res = []
        for kod in sorted(self.son_data):
            r = self.geri_analiz(kod, yil)
            if r: res.append(r)
        res.sort(key=lambda x: x['puan'], reverse=True)
        return res

    def kesisim_tara(self, yil=3):
        fark_kodlar = {r['kod']:r for r in self.fark_tara()}
        geri_kodlar = {r['kod']:r for r in self.geri_tara(yil)}
        kesisim = []
        for kod in fark_kodlar:
            if kod in geri_kodlar:
                kesisim.append({
                    'kod': kod,
                    'sektor': fark_kodlar[kod]['sektor'],
                    'fark_puan': fark_kodlar[kod]['puan'],
                    'fark_karar': fark_kodlar[kod]['karar'],
                    'geri_puan': geri_kodlar[kod]['puan'],
                    'geri_karar': geri_kodlar[kod]['karar'],
                    'toplam': round(fark_kodlar[kod]['puan'] + geri_kodlar[kod]['puan'], 1),
                    'fkpd': geri_kodlar[kod].get('fkpd'),
                    'efk_buy': geri_kodlar[kod].get('efk_buy'),
                    'pd_buy': geri_kodlar[kod].get('pd_buy'),
                    'fiyat_geride': geri_kodlar[kod].get('fiyat_geride'),
                    'pd_val': geri_kodlar[kod].get('pd_val'),
                    'pddd': fark_kodlar[kod].get('pddd'),
                    'marj': fark_kodlar[kod].get('marj'),
                    'A': fark_kodlar[kod]['A'], 'B': fark_kodlar[kod]['B'],
                    'C': fark_kodlar[kod]['C'], 'D': fark_kodlar[kod]['D'],
                })
        kesisim.sort(key=lambda x: x['toplam'], reverse=True)
        return kesisim

    def istatistik(self, yil=3):
        toplam = len(self.son_data)
        fark_n = len(self.fark_tara())
        geri_n = len(self.geri_tara(yil))
        kesisim_n = len(self.kesisim_tara(yil))
        return {'toplam':toplam,'fark':fark_n,'geri':geri_n,'kesisim':kesisim_n}
