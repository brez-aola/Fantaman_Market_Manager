"""Modern team routes using Repository Pattern."""

import logging
from typing import Optional

from flask import Blueprint, current_app, render_template, request, jsonify
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_repositories, get_db_session
from app.utils.team_utils import resolve_team_by_alias

bp = Blueprint("modern_teams", __name__, url_prefix="/teams")
logger = logging.getLogger(__name__)


@bp.route("/<team_name>")
def team_page(team_name: str):
    """Display team page with roster information."""
    try:
        ROSE_STRUCTURE = current_app.config.get("ROSE_STRUCTURE", {
            "Portieri": 3,
            "Difensori": 8,
            "Centrocampisti": 8,
            "Attaccanti": 6,
        })

        ROLE_MAP = {
            "P": "Portieri",
            "D": "Difensori",
            "C": "Centrocampisti",
            "A": "Attaccanti",
        }

        # Initialize roster structure
        team_roster = {role: [] for role in ROSE_STRUCTURE.keys()}

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Find team by name or alias
            team = resolve_team_by_alias(db, team_name)
            if not team:
                # Try to find team by exact name match
                teams = repos.teams.get_all()
                team = next((t for t in teams if t.name.lower() == team_name.lower()), None)

            if not team:
                logger.warning(f"Team not found: {team_name}")
                return render_template(
                    "team.html",
                    tname=team_name,
                    roster=team_roster,
                    rose_structure=ROSE_STRUCTURE,
                    starting_pot=300.0,
                    total_spent=0.0,
                    cassa=300.0,
                    squadre=current_app.config.get("SQUADRE", []),
                    error="Team not found"
                )

            # Get team players
            players = repos.players.get_by_team_id(team.id)

            # Organize players by role
            for player in players:
                role_code = (player.role or "").strip()
                if role_code:
                    # Normalize legacy 'G' (goalkeeper) to canonical 'P'
                    role_letter = role_code[0].upper()
                    if role_letter == "G":
                        role_letter = "P"

                    role_category = ROLE_MAP.get(role_letter)
                    if role_category:
                        team_roster[role_category].append({
                            "id": player.id,
                            "nome": player.name,
                            "ruolo": role_letter,
                            "squadra_reale": player.squadra,
                            "costo": float(player.costo) if player.costo else 0.0,
                            "anni_contratto": getattr(player, "anni_contratto", None),
                            "opzione": getattr(player, "opzione", None),
                        })

            # Calculate financial information
            starting_pot = float(team.cash) if team.cash is not None else 300.0
            total_spent = sum(float(player.costo or 0) for player in players)
            cassa = starting_pot - total_spent

            # Get team statistics
            team_stats = repos.teams.get_team_statistics(team.id)

            return render_template(
                "team.html",
                tname=team.name,
                roster=team_roster,
                rose_structure=ROSE_STRUCTURE,
                starting_pot=starting_pot,
                total_spent=total_spent,
                cassa=cassa,
                squadre=current_app.config.get("SQUADRE", []),
                team_stats=team_stats
            )

    except Exception as e:
        logger.error(f"Error loading team page for {team_name}: {e}")

        # Fallback to empty roster
        return render_template(
            "team.html",
            tname=team_name,
            roster={role: [] for role in current_app.config.get("ROSE_STRUCTURE", {}).keys()},
            rose_structure=current_app.config.get("ROSE_STRUCTURE", {}),
            starting_pot=300.0,
            total_spent=0.0,
            cassa=300.0,
            squadre=current_app.config.get("SQUADRE", []),
            error="Error loading team data"
        )


@bp.route("/<team_name>/api")
def team_api(team_name: str):
    """API endpoint for team data."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Find team by name or alias
            team = resolve_team_by_alias(db, team_name)
            if not team:
                teams = repos.teams.get_all()
                team = next((t for t in teams if t.name.lower() == team_name.lower()), None)

            if not team:
                return jsonify({"error": "Team not found"}), 404

            # Get team players
            players = repos.players.get_by_team_id(team.id)

            # Get team statistics
            team_stats = repos.teams.get_team_statistics(team.id)

            return jsonify({
                "team": {
                    "id": team.id,
                    "name": team.name,
                    "cash": float(team.cash) if team.cash else 0.0,
                    "league_id": team.league_id,
                    "league_name": team.league.name if team.league else None
                },
                "players": [{
                    "id": player.id,
                    "name": player.name,
                    "role": player.role,
                    "cost": float(player.costo) if player.costo else 0.0,
                    "real_team": player.squadra,
                    "contract_years": getattr(player, "anni_contratto", None),
                    "option": getattr(player, "opzione", None)
                } for player in players],
                "statistics": team_stats,
                "financial": {
                    "starting_budget": float(team.cash) if team.cash else 300.0,
                    "total_spent": sum(float(player.costo or 0) for player in players),
                    "remaining_cash": float(team.cash) if team.cash else 300.0 - sum(float(player.costo or 0) for player in players)
                }
            })

    except Exception as e:
        logger.error(f"Error getting team API data for {team_name}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/")
def teams_index():
    """List all teams."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            teams = repos.teams.get_all()

            # Get statistics for each team
            teams_data = []
            for team in teams:
                try:
                    stats = repos.teams.get_team_statistics(team.id)
                    players = repos.players.get_by_team_id(team.id)

                    teams_data.append({
                        "id": team.id,
                        "name": team.name,
                        "cash": float(team.cash) if team.cash else 0.0,
                        "league_name": team.league.name if team.league else "Unknown",
                        "player_count": len(players),
                        "total_value": stats.get("total_player_value", 0.0),
                        "remaining_budget": float(team.cash) if team.cash else 300.0 - sum(float(p.costo or 0) for p in players)
                    })
                except Exception as e:
                    logger.warning(f"Error getting stats for team {team.name}: {e}")
                    teams_data.append({
                        "id": team.id,
                        "name": team.name,
                        "cash": float(team.cash) if team.cash else 0.0,
                        "league_name": team.league.name if team.league else "Unknown",
                        "player_count": 0,
                        "total_value": 0.0,
                        "remaining_budget": float(team.cash) if team.cash else 300.0
                    })

            return render_template(
                "teams_list.html",
                teams=teams_data,
                total_teams=len(teams_data)
            )

    except Exception as e:
        logger.error(f"Error loading teams index: {e}")
        return render_template(
            "teams_list.html",
            teams=[],
            total_teams=0,
            error="Error loading teams data"
        )
