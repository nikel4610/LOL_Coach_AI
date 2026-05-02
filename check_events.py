import json

with open('data/raw/timelines/KR_8075621844.json', encoding='utf-8') as f:
    data = json.load(f)

frames = data['info']['frames']
items, towers, objectives = [], [], []

for frame in frames:
    for e in frame.get('events', []):
        t = e.get('type')
        ms = e.get('timestamp', 0)
        m = round(ms / 60000, 1)

        if t == 'ITEM_PURCHASED' and len(items) < 8:
            items.append("  %.1f분  participant=%s  item=%s" % (m, e.get('participantId'), e.get('itemId')))

        if t == 'BUILDING_KILL' and e.get('buildingType') == 'TOWER_BUILDING' and len(towers) < 6:
            towers.append("  %.1f분  lane=%s  team=%s  killer=%s" % (m, e.get('laneType'), e.get('teamId'), e.get('killerId')))

        if t == 'ELITE_MONSTER_KILL' and len(objectives) < 10:
            objectives.append("  %.1f분  type=%s  sub=%s  killerTeam=%s  killer=%s" % (
                m, e.get('monsterType'), e.get('monsterSubType'), e.get('killerTeamId'), e.get('killerId')))

print('=== ITEM_PURCHASED 샘플 ===')
for x in items: print(x)

print('\n=== TOWER 킬 샘플 ===')
for x in towers: print(x)

print('\n=== ELITE_MONSTER_KILL 샘플 ===')
for x in objectives: print(x)
