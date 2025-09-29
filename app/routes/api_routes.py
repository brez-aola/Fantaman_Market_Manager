"""Modern API routes using Repository Pattern with Security Features."""

import logging
from typing import Optional

from flask import Blueprint, current_app, jsonify, request, render_template
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_repositories, get_db_session
from app.services import AuthService
from app.security.decorators import security_headers, log_api_request, jwt_required_with_logging, require_roles, apply_rate_limit
from app.security.config import get_rate_limit

# Alias for easier use
jwt_required = jwt_required_with_logging()
admin_required = require_roles('admin')

# Create two blueprints: one for API endpoints and one for web pages
bp = Blueprint("modern_api", __name__, url_prefix="/api/v1")
web_bp = Blueprint("web", __name__)
logger = logging.getLogger(__name__)


@bp.route("/health")
@apply_rate_limit(get_rate_limit('default'))
@security_headers()
@log_api_request()
def health():
    """Health check endpoint."""
    try:
        # Test database connectivity
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            user_count = len(repos.users.get_all(limit=1))

        return jsonify({
            "status": "ok",
            "database": "connected",
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "database": "disconnected",
            "error": str(e)
        }), 500


@bp.route("/users")
@apply_rate_limit(get_rate_limit('read'))
@security_headers()
@log_api_request()
@jwt_required
@admin_required
def list_users():
    """List all users."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            users = repos.users.get_all()

            return jsonify({
                "users": [{
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                } for user in users],
                "total": len(users)
            })
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/users/<int:user_id>")
@apply_rate_limit(get_rate_limit('read'))
@security_headers()
@log_api_request()
@jwt_required
def get_user(user_id: int):
    """Get user by ID."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            user = repos.users.get_by_id(user_id)

            if not user:
                return jsonify({"error": "User not found"}), 404

            # Get user with roles
            user_with_roles = repos.users.get_with_roles(user_id)
            roles = []
            if user_with_roles and user_with_roles.roles:
                roles = [user_role.role.name for user_role in user_with_roles.roles]

            return jsonify({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "roles": roles,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None
            })
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/teams")
@apply_rate_limit(get_rate_limit('read'))
@security_headers()
@log_api_request()
@jwt_required
def list_teams():
    """List all teams with rate limiting."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            teams = repos.teams.get_all()

            return jsonify({
                "teams": [{
                    "id": team.id,
                    "name": team.name,
                    "cash": float(team.cash) if team.cash else 0.0,
                    "league_id": team.league_id,
                    "league_name": team.league.name if team.league else None
                } for team in teams],
                "total": len(teams)
            })
    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/teams/<int:team_id>")
@apply_rate_limit(get_rate_limit('read'))
@security_headers()
@log_api_request()
@jwt_required
def get_team(team_id: int):
    """Get team by ID with detailed information."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            team = repos.teams.get_by_id(team_id)

            if not team:
                return jsonify({"error": "Team not found"}), 404

            # Get team statistics
            stats = repos.teams.get_team_statistics(team_id)

            return jsonify({
                "id": team.id,
                "name": team.name,
                "cash": float(team.cash) if team.cash else 0.0,
                "league_id": team.league_id,
                "league_name": team.league.name if team.league else None,
                "statistics": stats
            })
    except Exception as e:
        logger.error(f"Error getting team {team_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/teams/<int:team_id>/players")
@apply_rate_limit(get_rate_limit('read'))
@security_headers()
@log_api_request()
@jwt_required
def get_team_players(team_id: int):
    """Get all players for a specific team."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            team = repos.teams.get_by_id(team_id)

            if not team:
                return jsonify({"error": "Team not found"}), 404

            players = repos.players.get_by_team_id(team_id)

            return jsonify({
                "team": {
                    "id": team.id,
                    "name": team.name
                },
                "players": [{
                    "id": player.id,
                    "name": player.name,
                    "role": player.role,
                    "cost": float(player.costo) if player.costo else 0.0,
                    "real_team": player.squadra_reale
                } for player in players],
                "total": len(players)
            })
    except Exception as e:
        logger.error(f"Error getting team {team_id} players: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/players")
@apply_rate_limit(get_rate_limit('read'))
@security_headers()
@log_api_request()
@jwt_required
def list_players():
    """List players with filtering options."""
    try:
        # Parse query parameters
        role = request.args.get('role', '').strip()
        team_id = request.args.get('team_id', type=int)
        free_agents = request.args.get('free_agents', 'false').lower() == 'true'
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            if free_agents:
                players = repos.players.get_free_agents(role=role or None)
            elif team_id:
                players = repos.players.get_by_team_id(team_id)
            elif role:
                players = repos.players.get_by_role(role)
            else:
                # Get all players without pagination for now
                all_players = repos.players.get_all()
                # Apply manual pagination
                players = all_players[offset:offset + limit] if offset or limit != 50 else all_players

            return jsonify({
                "players": [{
                    "id": player.id,
                    "name": player.name,
                    "role": player.role,
                    "cost": float(player.costo) if player.costo else 0.0,
                    "real_team": player.squadra_reale,
                    "team_id": player.team_id,
                    "team_name": player.team.name if player.team else None
                } for player in players],
                "total": len(players),
                "filters": {
                    "role": role,
                    "team_id": team_id,
                    "free_agents": free_agents
                }
            })
    except Exception as e:
        logger.error(f"Error listing players: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/players/<int:player_id>")
@apply_rate_limit(get_rate_limit('read'))
@security_headers()
@log_api_request()
@jwt_required
def get_player(player_id: int):
    """Get player by ID."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            player = repos.players.get_by_id(player_id)

            if not player:
                return jsonify({"error": "Player not found"}), 404

            return jsonify({
                "id": player.id,
                "name": player.name,
                "role": player.role,
                "cost": float(player.costo) if player.costo else 0.0,
                "real_team": player.squadra_reale,
                "team_id": player.team_id,
                "team_name": player.team.name if player.team else None,
                "contract_years": getattr(player, 'anni_contratto', None),
                "option": getattr(player, 'opzione', None)
            })
    except Exception as e:
        logger.error(f"Error getting player {player_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/players", methods=["POST"])
@apply_rate_limit(get_rate_limit('create'))
@security_headers()
@log_api_request()
@jwt_required
@admin_required
def create_player():
    """Create a new player."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        # Validate required fields
        required_fields = ['name', 'role']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Create player using the correct repository method
            player = repos.players.create_player(
                name=data['name'],
                role=data['role'],
                squadra_reale=data.get('real_team', ''),
                costo=data.get('cost', 0.0),
                team_id=data.get('team_id'),
                is_injured=data.get('is_injured', False)
                # Note: anni_contratto and opzione not supported by create_player method
            )
            db.commit()

            return jsonify({
                "id": player.id,
                "name": player.name,
                "role": player.role,
                "cost": float(player.costo) if player.costo else 0.0,
                "real_team": player.squadra_reale,
                "team_id": player.team_id,
                "message": "Player created successfully"
            }), 201

    except Exception as e:
        logger.error(f"Error creating player: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/players/<int:player_id>", methods=["PUT"])
@apply_rate_limit(get_rate_limit('update'))
@security_headers()
@log_api_request()
@jwt_required
@admin_required
def update_player(player_id: int):
    """Update an existing player."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        with next(get_db_session()) as db:
            repos = get_repositories(db)
            player = repos.players.get_by_id(player_id)

            if not player:
                return jsonify({"error": "Player not found"}), 404

            # Update player fields
            update_data = {}
            if 'name' in data:
                update_data['name'] = data['name']
            if 'role' in data:
                update_data['role'] = data['role']
            if 'real_team' in data:
                update_data['squadra'] = data['real_team']
            if 'cost' in data:
                update_data['costo'] = data['cost']
            if 'team_id' in data:
                update_data['team_id'] = data['team_id']
            if 'contract_years' in data:
                update_data['anni_contratto'] = data['contract_years']
            if 'option' in data:
                update_data['opzione'] = data['option']

            updated_player = repos.players.update(player_id, update_data)
            db.commit()

            return jsonify({
                "id": updated_player.id,
                "name": updated_player.name,
                "role": updated_player.role,
                "cost": float(updated_player.costo) if updated_player.costo else 0.0,
                "real_team": updated_player.squadra_reale,
                "team_id": updated_player.team_id,
                "message": "Player updated successfully"
            })

    except Exception as e:
        logger.error(f"Error updating player {player_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/players/<int:player_id>", methods=["DELETE"])
@apply_rate_limit(get_rate_limit('delete'))
@security_headers()
@log_api_request()
@jwt_required
@admin_required
def delete_player(player_id: int):
    """Delete a player."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            player = repos.players.get_by_id(player_id)

            if not player:
                return jsonify({"error": "Player not found"}), 404

            success = repos.players.delete(player_id)
            if success:
                db.commit()
                return jsonify({"message": "Player deleted successfully"}), 200
            else:
                return jsonify({"error": "Failed to delete player"}), 500

    except Exception as e:
        logger.error(f"Error deleting player {player_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/leagues")
@apply_rate_limit(get_rate_limit('read'))
@security_headers()
@log_api_request()
@jwt_required
def list_leagues():
    """List all leagues."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            leagues = repos.leagues.get_all()

            return jsonify({
                "leagues": [{
                    "id": league.id,
                    "name": league.name,
                    "slug": league.slug
                } for league in leagues],
                "total": len(leagues)
            })
    except Exception as e:
        logger.error(f"Error listing leagues: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/leagues/<int:league_id>")
@apply_rate_limit(get_rate_limit('read'))
@security_headers()
@log_api_request()
@jwt_required
def get_league(league_id: int):
    """Get league by ID with statistics."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            league = repos.leagues.get_by_id(league_id)

            if not league:
                return jsonify({"error": "League not found"}), 404

            # Get league statistics
            stats = repos.leagues.get_league_statistics(league_id)

            return jsonify({
                "id": league.id,
                "name": league.name,
                "slug": league.slug,
                "statistics": stats
            })
    except Exception as e:
        logger.error(f"Error getting league {league_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/teams", methods=["POST"])
@apply_rate_limit(get_rate_limit('create'))
@security_headers()
@log_api_request()
@jwt_required
def create_team():
    """Create a new team with rate limiting and validation."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        # Validate required fields
        if not data.get('name'):
            return jsonify({"error": "Missing required field: name"}), 400

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Check if team name already exists
            existing_teams = repos.teams.get_all()
            if any(team.name == data['name'] for team in existing_teams):
                return jsonify({"error": "Team name already exists"}), 409

            # Use the correct method from TeamRepository
            team = repos.teams.create_team(
                name=data['name'],
                league_id=data.get('league_id', 1),  # Default league
                cash=data.get('cash', 300.0)  # Default budget
                # Note: owner not supported by current Team model
            )
            db.commit()

            return jsonify({
                "id": team.id,
                "name": team.name,
                "cash": float(team.cash) if team.cash else 0.0,
                "league_id": team.league_id,
                "message": "Team created successfully"
            }), 201

    except Exception as e:
        logger.error(f"Error creating team: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/teams/<int:team_id>", methods=["PUT"])
@apply_rate_limit(get_rate_limit('update'))
@security_headers()
@log_api_request()
@jwt_required
def update_team(team_id: int):
    """Update an existing team."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        with next(get_db_session()) as db:
            repos = get_repositories(db)
            team = repos.teams.get_by_id(team_id)

            if not team:
                return jsonify({"error": "Team not found"}), 404

            # Update team fields
            update_data = {}
            if 'name' in data:
                update_data['name'] = data['name']
            if 'cash' in data:
                update_data['cash'] = data['cash']
            if 'league_id' in data:
                update_data['league_id'] = data['league_id']

            updated_team = repos.teams.update(team_id, update_data)
            db.commit()

            return jsonify({
                "id": updated_team.id,
                "name": updated_team.name,
                "cash": float(updated_team.cash) if updated_team.cash else 0.0,
                "league_id": updated_team.league_id,
                "message": "Team updated successfully"
            })

    except Exception as e:
        logger.error(f"Error updating team {team_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/teams/<int:team_id>", methods=["DELETE"])
@apply_rate_limit(get_rate_limit('delete'))
@security_headers()
@log_api_request()
@jwt_required
@admin_required
def delete_team(team_id: int):
    """Delete a team."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            team = repos.teams.get_by_id(team_id)

            if not team:
                return jsonify({"error": "Team not found"}), 404

            # Check if team has players assigned
            players = repos.players.get_by_team_id(team_id)
            if players:
                return jsonify({
                    "error": f"Cannot delete team with {len(players)} assigned players. Unassign players first."
                }), 409

            success = repos.teams.delete(team_id)
            if success:
                db.commit()
                return jsonify({"message": "Team deleted successfully"}), 200
            else:
                return jsonify({"error": "Failed to delete team"}), 500

    except Exception as e:
        logger.error(f"Error deleting team {team_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/market/statistics")
@apply_rate_limit(get_rate_limit('market'))
@security_headers()
@log_api_request()
@jwt_required
def market_statistics():
    """Get market statistics."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            stats = repos.players.get_market_statistics()

            return jsonify({
                "market_statistics": stats
            })
    except Exception as e:
        logger.error(f"Error getting market statistics: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/market/assign", methods=["POST"])
@apply_rate_limit(get_rate_limit('market'))
@security_headers()
@log_api_request()
@jwt_required
def assign_player_to_team():
    """Assign a player to a team."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        player_id = data.get('player_id')
        team_id = data.get('team_id')

        if not player_id or not team_id:
            return jsonify({"error": "Missing player_id or team_id"}), 400

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Validate player exists
            player = repos.players.get_by_id(player_id)
            if not player:
                return jsonify({"error": "Player not found"}), 404

            # Validate team exists
            team = repos.teams.get_by_id(team_id)
            if not team:
                return jsonify({"error": "Team not found"}), 404

            # Check if player is already assigned
            if player.team_id:
                return jsonify({
                    "error": f"Player is already assigned to team ID {player.team_id}"
                }), 409

            # Assign player to team
            success = repos.players.assign_to_team(player_id, team_id)
            if success:
                db.commit()
                return jsonify({
                    "message": f"Player {player.name} assigned to team {team.name}",
                    "player_id": player_id,
                    "team_id": team_id
                }), 200
            else:
                return jsonify({"error": "Failed to assign player"}), 500

    except Exception as e:
        logger.error(f"Error assigning player: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/market/unassign", methods=["POST"])
@apply_rate_limit(get_rate_limit('market'))
@security_headers()
@log_api_request()
@jwt_required
def unassign_player_from_team():
    """Remove a player from their team."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        player_id = data.get('player_id')
        if not player_id:
            return jsonify({"error": "Missing player_id"}), 400

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Validate player exists
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
                return jsonify({
                    "message": f"Player {player.name} unassigned from team {old_team_name}",
                    "player_id": player_id
                }), 200
            else:
                return jsonify({"error": "Failed to unassign player"}), 500

    except Exception as e:
        logger.error(f"Error unassigning player: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/market/transfer", methods=["POST"])
@apply_rate_limit(get_rate_limit('market'))
@security_headers()
@log_api_request()
@jwt_required
def transfer_player():
    """Transfer a player from one team to another."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        player_id = data.get('player_id')
        from_team_id = data.get('from_team_id')
        to_team_id = data.get('to_team_id')
        transfer_cost = data.get('cost', 0.0)

        if not all([player_id, from_team_id, to_team_id]):
            return jsonify({"error": "Missing required fields: player_id, from_team_id, to_team_id"}), 400

        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Validate entities exist
            player = repos.players.get_by_id(player_id)
            if not player:
                return jsonify({"error": "Player not found"}), 404

            from_team = repos.teams.get_by_id(from_team_id)
            to_team = repos.teams.get_by_id(to_team_id)
            if not from_team or not to_team:
                return jsonify({"error": "One or both teams not found"}), 404

            # Validate player is currently assigned to from_team
            if player.team_id != from_team_id:
                return jsonify({"error": "Player is not currently assigned to the specified from_team"}), 400

            # Check if to_team has sufficient budget
            if to_team.cash < transfer_cost:
                return jsonify({"error": "Destination team has insufficient budget"}), 400

            # Perform transfer
            success = repos.players.assign_to_team(player_id, to_team_id)
            if success:
                # Update team budgets if there's a cost
                if transfer_cost > 0:
                    repos.teams.update(from_team_id, {'cash': from_team.cash + transfer_cost})
                    repos.teams.update(to_team_id, {'cash': to_team.cash - transfer_cost})

                # Update player cost
                if 'new_cost' in data:
                    repos.players.update(player_id, {'costo': data['new_cost']})

                db.commit()
                return jsonify({
                    "message": f"Player {player.name} transferred from {from_team.name} to {to_team.name}",
                    "player_id": player_id,
                    "from_team": from_team.name,
                    "to_team": to_team.name,
                    "cost": transfer_cost
                }), 200
            else:
                return jsonify({"error": "Failed to transfer player"}), 500

    except Exception as e:
        logger.error(f"Error transferring player: {e}")
        return jsonify({"error": "Internal server error"}), 500


# Web routes for main pages
@web_bp.route("/")
def index():
    """Homepage - Main market manager page."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)

            # Get basic statistics for homepage
            teams = repos.teams.get_all()
            total_players = len(repos.players.get_all())
            free_agents = len(repos.players.get_free_agents())

            # Get team cash summary
            team_casse = []
            team_casse_missing = []

            for team in teams:
                players = repos.players.get_by_team_id(team.id)
                total_spent = sum(float(p.costo or 0) for p in players)
                remaining = float(team.cash or 300) - total_spent

                team_casse.append({
                    'squadra': team.name,
                    'starting': 300.0,
                    'remaining': remaining
                })

                # Count missing players by role
                role_counts = {'P': 0, 'D': 0, 'C': 0, 'A': 0}
                for player in players:
                    if player.role:
                        role_key = player.role[0].upper()
                        if role_key == 'G':  # Legacy goalkeeper
                            role_key = 'P'
                        if role_key in role_counts:
                            role_counts[role_key] += 1

                # Required: 3P, 8D, 8C, 6A = 25 total
                required = {'P': 3, 'D': 8, 'C': 8, 'A': 6}
                missing = sum(max(0, required[role] - role_counts[role]) for role in required)

                team_casse_missing.append({
                    'squadra': team.name,
                    'missing': missing,
                    'missing_portieri': max(0, required['P'] - role_counts['P']),
                    'missing_dif': max(0, required['D'] - role_counts['D']),
                    'missing_cen': max(0, required['C'] - role_counts['C']),
                    'missing_att': max(0, required['A'] - role_counts['A'])
                })

            # Sort by remaining cash
            team_casse.sort(key=lambda x: x['remaining'], reverse=True)

            return render_template(
                "index.html",
                squadre=current_app.config.get("SQUADRE", []),
                team_casse=team_casse,
                team_casse_missing=team_casse_missing,
                query="",
                results=[],
                columns=[],
                suggestions=[],
                total_players=total_players,
                free_agents=free_agents
            )
    except Exception as e:
        logger.error(f"Error loading homepage: {e}")
        return render_template(
            "index.html",
            squadre=current_app.config.get("SQUADRE", []),
            team_casse=[],
            team_casse_missing=[],
            query="",
            results=[],
            columns=[],
            error="Error loading homepage data"
        )


@web_bp.route("/rose")
def rose():
    """Rose squadre - Team rosters page."""
    try:
        with next(get_db_session()) as db:
            repos = get_repositories(db)
            teams = repos.teams.get_all()

            # Build team rosters
            # Build data structure expected by template
            rose_data = {}
            for team in teams:
                players = repos.players.get_by_team_id(team.id)

                # Group by role for this team
                team_roster = {
                    'Portieri': [],
                    'Difensori': [],
                    'Centrocampisti': [],
                    'Attaccanti': []
                }

                for player in players:
                    role_key = 'Attaccanti'  # default
                    if player.role:
                        role_first = player.role[0].upper()
                        if role_first in ['P', 'G']:
                            role_key = 'Portieri'
                        elif role_first == 'D':
                            role_key = 'Difensori'
                        elif role_first == 'C':
                            role_key = 'Centrocampisti'
                        elif role_first == 'A':
                            role_key = 'Attaccanti'

                    # Format player data for template
                    team_roster[role_key].append({
                        'id': player.id,
                        'nome': player.name,
                        'ruolo': player.role,
                        'costo': float(player.costo or 0),
                        'squadra_reale': player.squadra_reale,
                        'anni_contratto': getattr(player, 'anni_contratto', None),
                        'opzione': getattr(player, 'opzione', None)
                    })

                rose_data[team.name] = team_roster

            return render_template(
                "rose.html",
                rose=rose_data,
                rose_structure=current_app.config.get("ROSE_STRUCTURE", {
                    "Portieri": 3,
                    "Difensori": 8,
                    "Centrocampisti": 8,
                    "Attaccanti": 6,
                }),
                squadre=current_app.config.get("SQUADRE", [])
            )
    except Exception as e:
        logger.error(f"Error loading rose: {e}")
        return render_template(
            "rose.html",
            rose={},
            rose_structure=current_app.config.get("ROSE_STRUCTURE", {
                "Portieri": 3,
                "Difensori": 8,
                "Centrocampisti": 8,
                "Attaccanti": 6,
            }),
            squadre=current_app.config.get("SQUADRE", []),
            error="Error loading team rosters"
        )
