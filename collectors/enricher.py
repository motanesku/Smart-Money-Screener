"""
Enricher v11 — Include Scoring bazat pe Persistență și Sector Heat.
"""
# ... păstrează importurile tale ...

def calculate_smart_money_score(data, persistence_count=0, sector_hotness=0):
    """
    Scoring hibrid: Insider + Whale Persistence + Sector Narrative
    """
    score = 0
    
    # 1. Insider Score (0-40p) - Bazat pe Form 4
    score += data.get('score_insider', 0)
    
    # 2. Whale Persistence (0-30p)
    # Dacă balena a fost văzută în scanner de mai multe ori în 14 zile
    if persistence_count >= 3: score += 30
    elif persistence_count >= 2: score += 15
    
    # 3. Sector & Relative Strength (0-30p)
    if sector_hotness > 0.20: score += 15 # Sectorul e "hot"
    if data.get('relative_strength', 0) > 0.02: score += 15 # Bate sectorul cu 2%
    
    # 4. Vol Ratio Bonus
    if data.get('vol_ratio', 0) > 5: score += 10

    return min(score, 100)

# Notă: În funcția ta enrich_single, trebuie să extragi p_count din v_persistence_signals
