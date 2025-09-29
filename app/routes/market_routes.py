"""Modern market routes using Repository Pattern."""

import logging
from typing import Optional, List

from flask import Blueprint, current_app, render_template, request, jsonify, redirect, url_for
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_repositories, get_db_session

bp = Blueprint("modern_market", __name__)
logger = logging.getLogger(__name__)


@bp.route("/", methods=["GET"])
def index():
    """Market index page with player search and filtering."""
    try:
        # Parse query parameters
        query = request.args.get("q", "").strip()
        ruolo = request.args.get("ruolo", "").strip()
        squadra = request.args.get("squadra", "").strip()
        roles_selected = request.args.getlist("roles")
        costo_min = request.args.get("costo_min", "").strip()
        costo_max = request.args.get("costo_max", "").strip()
        opzione = request.args.get("opzione", "").strip()
        anni_contratto = request.args.get("anni_contratto", "").strip()
        page = int(request.args.get("page", 1))
        per_page = 50

        # Default role selection
        role_map = {
            "Portieri": ["P"],
            "Difensori": ["D"],
            "Centrocampisti": ["C"],
            "Attaccanti": ["A"],
        }

        if not roles_selected:
            roles_selected = list(role_map.keys())

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Build filters
            filters = {}
            if query:
                filters['name'] = query
            if squadra:
                filters['real_team'] = squadra

            # Convert role categories to role codes
            role_codes = []
            for role_cat in roles_selected:
                role_codes.extend(role_map.get(role_cat, []))

            if role_codes:
                filters['roles'] = role_codes
            elif ruolo:
                filters['roles'] = [ruolo.upper()]

            # Cost filters
            if costo_min:
                try:
                    filters['min_cost'] = float(costo_min)
                except ValueError:
                    pass

            if costo_max:
                try:
                    filters['max_cost'] = float(costo_max)
                except ValueError:
                    pass

            # Get players with filters
            offset = (page - 1) * per_page
            players = repos.players.search_players(
                name_query=filters.get('name'),
                role=filters.get('roles'),
                real_team=filters.get('real_team'),
                min_cost=filters.get('min_cost'),
                max_cost=filters.get('max_cost'),
                limit=per_page,
                offset=offset
            )

            # Get total count for pagination (simplified)
            total_count = len(repos.players.search_players(
                name_query=filters.get('name'),
                role=filters.get('roles'),
                real_team=filters.get('real_team'),
                min_cost=filters.get('min_cost'),
                max_cost=filters.get('max_cost')
            ))

            # Get available teams for filter dropdown
            teams = repos.teams.get_all()
            team_names = sorted(list(set(p.squadra for p in repos.players.get_all() if p.squadra)))

            # Get market statistics
            market_stats = repos.players.get_market_statistics()

            # Calculate pagination
            total_pages = (total_count + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages

            return render_template(
                "market.html",
                giocatori=players,
                query=query,
                ruolo=ruolo,
                squadra=squadra,
                roles_selected=roles_selected,
                role_map=role_map,
                costo_min=costo_min,
                costo_max=costo_max,
                opzione=opzione,
                anni_contratto=anni_contratto,
                team_names=team_names,
                squadre=current_app.config.get("SQUADRE", []),
                current_page=page,
                total_pages=total_pages,
                has_prev=has_prev,
                has_next=has_next,
                per_page=per_page,
                total_count=total_count,
                market_stats=market_stats
            )

    except Exception as e:
        logger.error(f"Error loading market index: {e}")
        return render_template(
            "market.html",
            giocatori=[],
            query="",
            ruolo="",
            squadra="",
            roles_selected=[],
            role_map={
                "Portieri": ["P"],
                "Difensori": ["D"],
                "Centrocampisti": ["C"],
                "Attaccanti": ["A"],
            },
            costo_min="",
            costo_max="",
            opzione="",
            anni_contratto="",
            team_names=[],
            squadre=[],
            current_page=1,
            total_pages=1,
            has_prev=False,
            has_next=False,
            per_page=50,
            total_count=0,
            market_stats={},
            error="Error loading market data"
        )


@bp.route("/assign", methods=["POST"])
def assign_player():
    """Assign a player to a team."""
    try:
        player_id = request.form.get("player_id", type=int)
        team_name = request.form.get("team")

        if not player_id or not team_name:
            return jsonify({"error": "Missing player_id or team"}), 400

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Find player
            player = repos.players.get_by_id(player_id)
            if not player:
                return jsonify({"error": "Player not found"}), 404

            # Find team by name
            teams = repos.teams.get_all()
            team = next((t for t in teams if t.name == team_name), None)
            if not team:
                return jsonify({"error": "Team not found"}), 404

            # Check if player is already assigned
            if player.team_id and player.team_id != team.id:
                return jsonify({
                    "error": f"Player is already assigned to {player.team.name}"
                }), 400

            # Assign player to team
            success = repos.players.assign_to_team(player_id, team.id)

            if success:
                db.commit()
                logger.info(f"Player {player.name} assigned to team {team.name}")
                return jsonify({
                    "success": True,
                    "message": f"Player {player.name} assigned to {team.name}"
                })
            else:
                return jsonify({"error": "Failed to assign player"}), 500

    except Exception as e:
        logger.error(f"Error assigning player: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/unassign", methods=["POST"])
def unassign_player():
    """Remove a player from their team."""
    try:
        player_id = request.form.get("player_id", type=int)

        if not player_id:
            return jsonify({"error": "Missing player_id"}), 400

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Find player
            player = repos.players.get_by_id(player_id)
            if not player:
                return jsonify({"error": "Player not found"}), 404

            if not player.team_id:
                return jsonify({"error": "Player is not assigned to any team"}), 400

            old_team_name = player.team.name if player.team else "Unknown"

            # Unassign player
            success = repos.players.assign_to_team(player_id, None)

            if success:
                db.commit()
                logger.info(f"Player {player.name} unassigned from team {old_team_name}")
                return jsonify({
                    "success": True,
                    "message": f"Player {player.name} unassigned from {old_team_name}"
                })
            else:
                return jsonify({"error": "Failed to unassign player"}), 500

    except Exception as e:
        logger.error(f"Error unassigning player: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/player/<int:player_id>")
def player_detail(player_id: int):
    """Show detailed information about a player."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)

            player = repos.players.get_by_id(player_id)
            if not player:
                return render_template("error.html",
                                     message="Player not found"), 404

            # Get all teams for assignment options
            teams = repos.teams.get_all()

            return render_template(
                "player_detail.html",
                player=player,
                teams=teams
            )

    except Exception as e:
        logger.error(f"Error loading player detail for ID {player_id}: {e}")
        return render_template("error.html",
                             message="Error loading player details"), 500


@bp.route("/free-agents")
def free_agents():
    """Show all free agents (unassigned players)."""
    try:
        role = request.args.get("role", "").strip()

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Get free agents, optionally filtered by role
            free_agents = repos.players.get_free_agents(role=role if role else None)

            # Group by role for display
            agents_by_role = {
                "P": [],
                "D": [],
                "C": [],
                "A": []
            }

            for player in free_agents:
                player_role = (player.role or "").strip()
                if player_role:
                    role_letter = player_role[0].upper()
                    if role_letter == "G":  # Legacy goalkeeper -> Portiere
                        role_letter = "P"
                    if role_letter in agents_by_role:
                        agents_by_role[role_letter].append(player)

            # Get market statistics
            market_stats = repos.players.get_market_statistics()

            return render_template(
                "free_agents.html",
                agents_by_role=agents_by_role,
                total_free_agents=len(free_agents),
                selected_role=role,
                market_stats=market_stats,
                teams=repos.teams.get_all()
            )

    except Exception as e:
        logger.error(f"Error loading free agents: {e}")
        return render_template(
            "free_agents.html",
            agents_by_role={"P": [], "D": [], "C": [], "A": []},
            total_free_agents=0,
            error="Error loading free agents data"
        )


@bp.route("/statistics")
def market_statistics():
    """Show detailed market statistics."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Get comprehensive market statistics
            market_stats = repos.players.get_market_statistics()

            # Get team statistics
            teams = repos.teams.get_all()
            team_stats = []
            for team in teams:
                try:
                    stats = repos.teams.get_team_statistics(team.id)
                    players = repos.players.get_by_team_id(team.id)
                    team_stats.append({
                        "name": team.name,
                        "players": len(players),
                        "total_value": stats.get("total_player_value", 0.0),
                        "cash": float(team.cash) if team.cash else 0.0,
                        "remaining_budget": float(team.cash) if team.cash else 300.0 - sum(float(p.costo or 0) for p in players)
                    })
                except Exception as e:
                    logger.warning(f"Error getting stats for team {team.name}: {e}")

            # Sort teams by total value
            team_stats.sort(key=lambda x: x["total_value"], reverse=True)

            return render_template(
                "market_statistics.html",
                market_stats=market_stats,
                team_stats=team_stats,
                total_teams=len(team_stats)
            )

    except Exception as e:
        logger.error(f"Error loading market statistics: {e}")
        return render_template(
            "market_statistics.html",
            market_stats={},
            team_stats=[],
            error="Error loading statistics"
        )
