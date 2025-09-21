from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from app.models import Team, TeamAlias, League
from difflib import get_close_matches
from typing import List

try:
    from rapidfuzz import process as rf_process
except Exception:
    rf_process = None


def _normalize_alias(s: str) -> str:
    # collapse whitespace, strip, and normalize case for storage
    return " ".join(s.split()).strip()


def resolve_team_by_alias(session: Session, name: str, league_slug: Optional[str] = None) -> Optional[Team]:
    """Resolve a Team by an alias or canonical name.

    Priority:
      1. Exact match on Team.name within league (if league provided)
      2. Exact match on TeamAlias.alias within league
      3. Exact match on Team.name globally
      4. Exact match on TeamAlias.alias globally
    """
    if not name:
        return None
    q_name = name.strip()
    league_id = None
    if league_slug:
        league = session.query(League).filter(League.slug == league_slug).first()
        if league:
            league_id = league.id
    # 1
    if league_id:
        t = session.query(Team).filter(Team.name == q_name, Team.league_id == league_id).first()
        if t:
            return t
    # 2
    if league_id:
        ta = (
            session.query(TeamAlias)
            .join(Team)
            .filter(TeamAlias.alias == q_name, Team.league_id == league_id)
            .first()
        )
        if ta:
            return ta.team
    # 3
    t = session.query(Team).filter(Team.name == q_name).first()
    if t:
        return t
    # 4
    ta = session.query(TeamAlias).filter(TeamAlias.alias == q_name).first()
    if ta:
        return ta.team
    return None


def populate_team_aliases(session: Session, source: str = "fantateam", fuzzy_threshold: float = 0.6) -> List[TeamAlias]:
    """Populate `team_aliases` table by deriving aliases from a legacy source.

    Strategy:
      1. Try exact matching by cash (cassa_attuale or cassa_iniziale).
      2. For remaining unmatched names, try fuzzy name matching against existing team names.

    Returns list of created TeamAlias objects.
    """
    created: List[TeamAlias] = []
    # canonical mapping for known variants is stored in DB table canonical_mappings
    canonical_map = {}
    try:
        from app.models import CanonicalMapping

        for cm in session.query(CanonicalMapping).all():
            canonical_map[cm.variant.lower()] = cm.canonical
    except Exception:
        # if table missing or other error, fall back to empty map
        canonical_map = {}
    # fetch source rows
    import sqlalchemy as sa
    if source == "fantateam":
        rows = session.execute(sa.text("SELECT squadra, cassa_attuale, cassa_iniziale FROM fantateam")).fetchall()
    else:
        # Example: other sources could be added later
        rows = session.execute(sa.text("SELECT squadra, cassa_attuale, cassa_iniziale FROM fantateam")).fetchall()

    # Build map cash -> team id (could be many to one)
    teams = session.query(Team).all()
    cash_map = {}
    name_list = [t.name for t in teams]
    for t in teams:
        cash_map.setdefault(t.cash, []).append(t)

    for r in rows:
        raw_alias = (r[0] or "")
        alias_name = _normalize_alias(raw_alias)
        if not alias_name:
            continue
        cash_val = None
        try:
            cash_val = int(float(r[1] if r[1] is not None else (r[2] if r[2] is not None else 0)))
        except Exception:
            cash_val = None

        matched_team = None
        # 1) cash-based match
        if cash_val is not None and cash_val in cash_map:
            # if multiple teams with same cash choose the best fuzzy name match among them
            candidates = cash_map[cash_val]
            if len(candidates) == 1:
                matched_team = candidates[0]
            else:
                # pick by fuzzy among candidate names
                cand_names = [c.name for c in candidates]
                if rf_process:
                    # rapidfuzz returns (match, score, index)
                    best = rf_process.extractOne(alias_name, cand_names)
                    if best and best[1] / 100.0 >= fuzzy_threshold:
                        matched_team = next((c for c in candidates if c.name == best[0]), None)
                else:
                    best = get_close_matches(alias_name, cand_names, n=1, cutoff=fuzzy_threshold)
                    if best:
                        matched_team = next((c for c in candidates if c.name == best[0]), None)
        # 2) fuzzy global match fallback
        if matched_team is None:
            if rf_process:
                best_global = rf_process.extractOne(alias_name, name_list)
                if best_global and best_global[1] / 100.0 >= fuzzy_threshold:
                    matched_team = session.query(Team).filter(Team.name == best_global[0]).first()
            else:
                best_global = get_close_matches(alias_name, name_list, n=1, cutoff=fuzzy_threshold)
                if best_global:
                    matched_team = session.query(Team).filter(Team.name == best_global[0]).first()

        if matched_team:
            # apply canonical mapping override
            key = alias_name.lower()
            if key in canonical_map:
                # ensure the canonical team matches target if possible
                canon = canonical_map[key]
                # canonical name may differ in case; prefer resolving canon via team name
                canon_team = session.query(Team).filter(Team.name == canon).first()
                if canon_team:
                    matched_team = canon_team

            # dedupe alias insertion (case-insensitive)
            exists = (
                session.query(TeamAlias)
                .filter(TeamAlias.team_id == matched_team.id)
                .filter(TeamAlias.alias.ilike(alias_name))
                .first()
            )
            if not exists:
                ta = TeamAlias(team_id=matched_team.id, alias=alias_name)
                session.add(ta)
                created.append(ta)

    # perform deduplication across teams: if same alias exists for multiple team_ids, keep first and remove others
    session.commit()
    # global dedupe: group by normalized alias
    all_aliases = session.query(TeamAlias).all()
    seen = {}
    for a in all_aliases:
        norm = a.alias.lower()
        if norm in seen:
            # remove duplicate row
            session.delete(a)
        else:
            seen[norm] = a
    session.commit()
    return created
