# 국제고·국제중 학교 정보 받아 오기 (나이스 교육정보 개방 포털 open.neis.go.kr) — 2026-11-19
# 매일 .github/workflows/neis.yml 이 실행 → data/neis/<학교 약칭>.json 을 쓴다. 페이지(special/*.html)가 이 JSON 을 읽어 보여 준다.
# 인증키: 환경변수 NEIS_KEY (GitHub secret). 학교 목록: 아래 SCHOOLS (생성기 데이터/special-schools.js 의 neis 와 같게 유지).
# 출처 표기: 화면에 "자료: 나이스 교육정보 개방 포털" 을 함께 보인다(공공데이터).
import datetime as dt, json, os, re, sys, time, urllib.parse, urllib.request

KEY = os.environ.get('NEIS_KEY', '')
HUB = 'https://open.neis.go.kr/hub/'
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'neis')
SCHOOLS = [  # (약칭, 학교급, 교육청, 학교 코드)
    ('서울국제고', '고', 'B10', '7010817'), ('청심국제고', '고', 'J10', '7530776'), ('고양국제고', '고', 'J10', '7530977'),
    ('동탄국제고', '고', 'J10', '7530976'), ('인천국제고', '고', 'E10', '7310334'), ('부산국제고', '고', 'C10', '7150369'),
    ('세종국제고', '고', 'I10', '9300108'), ('대구국제고', '고', 'D10', '7240450'),
    ('대원국제중', '중', 'B10', '7134130'), ('영훈국제중', '중', 'B10', '7121369'), ('청심국제중', '중', 'J10', '7721038'),
    ('부산국제중', '중', 'C10', '7181085'), ('선인국제중', '중', 'S10', '9051144'),
]
KST = dt.timezone(dt.timedelta(hours=9))
TODAY = dt.datetime.now(KST).date()
F = lambda d: d.strftime('%Y%m%d')


def get(ep, **q):
    """한 엔드포인트의 모든 행(1000개씩 여러 쪽)."""
    rows, page = [], 1
    while True:
        q2 = dict(q, KEY=KEY, Type='json', pIndex=page, pSize=1000)
        url = HUB + ep + '?' + urllib.parse.urlencode(q2)
        for tryno in range(3):
            try:
                r = json.load(urllib.request.urlopen(url, timeout=30)); break
            except Exception as e:
                if tryno == 2: print('  실패', ep, e); return rows
                time.sleep(2)
        if ep not in r: return rows          # INFO-200(자료 없음) 등
        head, body = r[ep][0]['head'], r[ep][1]['row']
        rows += body
        if len(rows) >= head[0]['list_total_count'] or not body: return rows
        page += 1


def clean_dish(s):
    out = []
    for x in re.split(r'<br\s*/?>', s or ''):
        x = re.sub(r'\([0-9.\s]+\)', '', x)       # 알레르기 번호 (1.5.6)
        x = re.sub(r'[*#@]+|\s+', ' ', x).strip()
        if x: out.append(x)
    return out


NOT_SUBJECT = re.compile(r'(방학|휴업|휴일|고사|시험|평가|체험|선거|수능|수학능력|입학|졸업|개학|종업|식$|절$|날$|한마당|축제|추석|설날|성탄|신정|대체|자율|자치|동아리|봉사|창체|창의적|진로활동|토요|행사|대회|수련|여행|공강|자습)')
def clean_subject(s):
    s = (s or '').strip().lstrip('-').strip()
    s = re.sub(r'^(\[[^\]]*\]|\([^)]*\)|기말고사|중간고사|학력평가|수행평가|지필평가)+', '', s).strip()
    if not s or NOT_SUBJECT.search(s): return ''
    return re.sub(r'\s+', ' ', s)


def ranges(sch):
    """날짜별 행사 → [시작, 끝, 이름] (같은 이름이 이어지면 하나로)."""
    out = []
    for day, evs in sch:
        for ev in evs:
            prev = next((x for x in reversed(out) if x[2] == ev), None)
            if prev and (dt.datetime.strptime(day, '%Y%m%d') - dt.datetime.strptime(prev[1], '%Y%m%d')).days <= 3:
                prev[1] = day
            else:
                out.append([day, day, ev])
    return sorted(out)


def school_year(d):
    return d.year if d.month >= 3 else d.year - 1


def main():
    if not KEY: sys.exit('NEIS_KEY 가 없습니다')
    os.makedirs(OUT, exist_ok=True)
    mon = TODAY - dt.timedelta(days=TODAY.weekday())
    for name, lv, ofc, code in SCHOOLS:
        print(name)
        path = os.path.join(OUT, name + '.json')
        old = json.load(open(path, encoding='utf8')) if os.path.exists(path) else {}
        base = dict(ATPT_OFCDC_SC_CODE=ofc, SD_SCHUL_CODE=code)
        d = {'name': name, 'updated': TODAY.isoformat()}

        # 기본 정보
        info = (get('schoolInfo', **base) or [{}])[0]
        d['info'] = {k: (info.get(v) or '').strip() for k, v in [('full', 'SCHUL_NM'), ('eng', 'ENG_SCHUL_NM'), ('fond', 'FOND_SC_NM'), ('coedu', 'COEDU_SC_NM'),
                     ('addr', 'ORG_RDNMA'), ('tel', 'ORG_TELNO'), ('home', 'HMPG_ADRES'), ('founded', 'FOND_YMD'), ('kind', 'HS_SC_NM'), ('track', 'SPCLY_PURPS_HS_ORD_NM')]} or old.get('info', {})

        # 급식: 이번 주 월요일 ~ 다음 주 금요일
        meals = {}
        for r in get('mealServiceDietInfo', **base, MLSV_FROM_YMD=F(mon), MLSV_TO_YMD=F(mon + dt.timedelta(days=11))):
            meals.setdefault(r['MLSV_YMD'], {})[r['MMEAL_SC_NM']] = clean_dish(r['DDISH_NM'])
        d['meals'] = meals

        # 학사일정: 오늘 기준 앞 7일 ~ 뒤 120일 (토요휴업일은 뺌)
        sch = {}
        for r in get('SchoolSchedule', **base, AA_FROM_YMD=F(TODAY - dt.timedelta(days=7)), AA_TO_YMD=F(TODAY + dt.timedelta(days=120))):
            ev = (r.get('EVENT_NM') or '').strip()
            if not ev or ev == '토요휴업일': continue
            sch.setdefault(r['AA_YMD'], [])
            if ev not in sch[r['AA_YMD']]: sch[r['AA_YMD']].append(ev)
        d['schedule'] = ranges(sorted(sch.items()))

        # 시간표: 이번 주(없으면 지난주) 학년·반·요일·교시
        ep = 'hisTimetable' if lv == '고' else 'misTimetable'
        tt, week = {}, None
        for wk in (mon, mon - dt.timedelta(days=7), mon - dt.timedelta(days=14)):
            rows = get(ep, **base, TI_FROM_YMD=F(wk), TI_TO_YMD=F(wk + dt.timedelta(days=4)))
            if rows:
                week = F(wk)
                for r in rows:
                    sub = (r.get('ITRT_CNTNT') or '').strip().lstrip('-').strip()
                    if not sub: continue
                    g, c = r['GRADE'], r.get('CLASS_NM') or r.get('CLRM_NM') or '1'
                    day = dt.datetime.strptime(r['ALL_TI_YMD'], '%Y%m%d').weekday()
                    p = int(r['PERIO'] or 0)
                    if day > 4 or p < 1 or p > 10: continue
                    cell = tt.setdefault(g, {}).setdefault(c, [[''] * 8 for _ in range(5)])
                    if p > len(cell[day]):
                        for x in cell: x.extend([''] * (p - len(x)))
                    cell[day][p - 1] = sub
                break
        if tt:
            d['timetable'] = {'week': week, 'grades': tt}
        elif old.get('timetable'):
            d['timetable'] = old['timetable']    # 방학 등으로 비면 지난 자료 유지

        # 학년별 개설 과목: 이번 학년도 전체 시간표에서 과목 이름 모으기 — 월요일·자료 없을 때만(호출 많음)
        if TODAY.weekday() == 0 or not old.get('subjects'):
            ay = school_year(TODAY)
            cnt = {}
            for r in get(ep, **base, AY=str(ay)):
                s = clean_subject(r.get('ITRT_CNTNT'))
                if s: cnt.setdefault(r['GRADE'], {}).setdefault(s, set()).add(r['ALL_TI_YMD'])
            # 며칠 안 나오는 이름(행사·공휴일)은 뺀다 — 과목은 학기 내내 여러 날 나온다
            subs = {g: sorted(k for k, days in v.items() if len(days) >= 8) for g, v in sorted(cnt.items())}
            d['subjects'] = {g: v for g, v in subs.items() if v} or old.get('subjects', {})
            d['subjects_year'] = ay
        else:
            d['subjects'], d['subjects_year'] = old['subjects'], old.get('subjects_year')

        json.dump(d, open(path, 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
        print('  급식', len(meals), '일 · 일정', len(d['schedule']), '· 시간표 학년', len(tt), '· 과목', {g: len(v) for g, v in d['subjects'].items()})


if __name__ == '__main__':
    main()
