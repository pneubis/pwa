#!/usr/bin/env python3
"""
GitHub Actions scraper — récupère standings + fixtures de rugbypass.com
et génère data.json pour la PWA 6 Nations.
"""
import requests, json, re, sys
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr,en;q=0.5',
}

FLAGS = {
    'France':         '🇫🇷',
    'England':        '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    'Ireland':        '🇮🇪',
    'Scotland':       '🏴󠁧󠁢󠁳󠁣󠁴󠁿',
    'Wales':          '🏴󠁧󠁢󠁷󠁬󠁳󠁿',
    'Italy':          '🇮🇹',
}
FR_NAMES = {
    'France':   'France',
    'England':  'Angleterre',
    'Ireland':  'Irlande',
    'Scotland': 'Écosse',
    'Wales':    'Pays de Galles',
    'Italy':    'Italie',
}

def get_json_from_page(url, pattern):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    m = re.search(pattern, r.text, re.DOTALL)
    if not m:
        raise ValueError(f"Pattern not found in {url}")
    return json.loads(m.group(1))

def scrape_standings():
    r = requests.get('https://www.rugbypass.com/six-nations/standings/', headers=HEADERS, timeout=15)
    r.raise_for_status()
    # Extract JSON embedded in page
    m = re.search(r'(\{"hasStandings":true.*?"standings":\[.*?\]\})', r.text, re.DOTALL)
    if not m:
        # Try broader pattern
        m = re.search(r'(\{"hasStandings":.+?"seasonForm":"[^"]*"\})', r.text, re.DOTALL)
    # Find all standings entries
    entries = re.findall(
        r'\{"id":(\d+),"name":"([^"]+)","played":(\d+).*?"won":(\d+),"lost":(\d+).*?"tries_bonus":(\d+),"losing_bonus":(\d+).*?"rank":(\d+),"points":(\d+)',
        r.text
    )
    standings = []
    seen = set()
    for e in entries:
        name = e[1]
        if name in FLAGS and name not in seen:
            seen.add(name)
            standings.append({
                'rank': int(e[7]),
                'name': name,
                'name_fr': FR_NAMES.get(name, name),
                'flag': FLAGS.get(name, '🏳️'),
                'played': int(e[2]),
                'won': int(e[3]),
                'lost': int(e[4]),
                'drawn': 0,
                'tries_bonus': int(e[5]),
                'losing_bonus': int(e[6]),
                'points': int(e[8]),
            })
    # Also get points diff
    diffs = re.findall(
        r'"name":"(' + '|'.join(FLAGS.keys()) + r')"[^}]*?"points_diff":(-?\d+)[^}]*?"points_scored":(\d+)[^}]*?"points_against":(\d+)',
        r.text
    )
    diff_map = {d[0]: {'diff': int(d[1]), 'for': int(d[2]), 'against': int(d[3])} for d in diffs}
    for s in standings:
        d = diff_map.get(s['name'], {})
        s['points_diff'] = d.get('diff', 0)
        s['points_for'] = d.get('for', 0)
        s['points_against'] = d.get('against', 0)
    standings.sort(key=lambda x: x['rank'])
    return standings

def scrape_fixtures():
    r = requests.get('https://www.rugbypass.com/six-nations/fixtures-results/', headers=HEADERS, timeout=15)
    r.raise_for_status()
    
    # Extract all match entries
    matches = []
    # Pattern for played matches
    played = re.findall(
        r'"id":(\d+).*?"dateFull":"([^"]+)".*?"time":"([^"]+)".*?"homeTeam":\{"id":\d+[^}]*"name":"([^"]+)"[^}]*\}.*?"awayTeam":\{"id":\d+[^}]*"name":"([^"]+)"[^}]*\}.*?"homeScore":(\d+),"awayScore":(\d+).*?"round":"([^"]+)".*?"status":"Result".*?"venue":"([^"]+)"',
        r.text
    )
    for m in played:
        home = m[3]; away = m[4]
        if home not in FLAGS and away not in FLAGS:
            continue
        matches.append({
            'id': m[0],
            'date': m[1],
            'time': m[2],
            'home': {'name': home, 'name_fr': FR_NAMES.get(home, home), 'flag': FLAGS.get(home, '🏳️')},
            'away': {'name': away, 'name_fr': FR_NAMES.get(away, away), 'flag': FLAGS.get(away, '🏳️')},
            'home_score': int(m[5]),
            'away_score': int(m[6]),
            'round': m[7],
            'venue': m[8],
            'status': 'played'
        })
    
    # Pattern for upcoming
    upcoming = re.findall(
        r'"id":(\d+).*?"dateFull":"([^"]+)".*?"time":"([^"]+)".*?"homeTeam":\{"id":\d+[^}]*"name":"([^"]+)"[^}]*\}.*?"awayTeam":\{"id":\d+[^}]*"name":"([^"]+)"[^}]*\}.*?"homeScore":0,"awayScore":0.*?"round":"([^"]+)".*?"upcoming":true.*?"venue":"([^"]*)"',
        r.text
    )
    for m in upcoming:
        home = m[3]; away = m[4]
        if home not in FLAGS and away not in FLAGS:
            continue
        matches.append({
            'id': m[0],
            'date': m[1],
            'time': m[2],
            'home': {'name': home, 'name_fr': FR_NAMES.get(home, home), 'flag': FLAGS.get(home, '🏳️')},
            'away': {'name': away, 'name_fr': FR_NAMES.get(away, away), 'flag': FLAGS.get(away, '🏳️')},
            'home_score': None,
            'away_score': None,
            'round': m[5],
            'venue': m[6],
            'status': 'upcoming'
        })
    
    return matches

def main():
    print("Scraping standings...", file=sys.stderr)
    standings = scrape_standings()
    print(f"  {len(standings)} teams", file=sys.stderr)
    
    print("Scraping fixtures...", file=sys.stderr)
    matches = scrape_fixtures()
    print(f"  {len(matches)} matches", file=sys.stderr)
    
    leader = standings[0] if standings else {}
    next_match = next((m for m in matches if m['status'] == 'upcoming'), None)
    
    data = {
        'updated_at': datetime.utcnow().isoformat() + 'Z',
        'standings': standings,
        'matches': matches,
        'meta': {
            'leader': leader,
            'next_match': next_match,
            'total_matches': len(matches),
            'played': sum(1 for m in matches if m['status'] == 'played'),
        }
    }
    
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"data.json written — {len(standings)} équipes, {len(matches)} matchs", file=sys.stderr)
    print(json.dumps({'status': 'ok', 'teams': len(standings), 'matches': len(matches)}))

if __name__ == '__main__':
    main()
