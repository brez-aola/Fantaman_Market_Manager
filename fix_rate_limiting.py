#!/usr/bin/env python3
"""
Script per aggiungere rate limiting e security decorators a tutti gli endpoint API.
"""

import re


def fix_api_routes():
    """Fix API routes with rate limiting and security decorators."""

    file_path = "app/routes/api_routes.py"

    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Define the fixes to apply
    fixes = [
        # Players endpoints
        {
            'old': '@bp.route("/players")\ndef list_players():',
            'new': '@bp.route("/players")\n@limiter.limit("500 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef list_players():'
        },
        {
            'old': '@bp.route("/players/<int:player_id>")\ndef get_player(player_id: int):',
            'new': '@bp.route("/players/<int:player_id>")\n@limiter.limit("500 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef get_player(player_id: int):'
        },
        {
            'old': '@bp.route("/players", methods=["POST"])\ndef create_player():',
            'new': '@bp.route("/players", methods=["POST"])\n@limiter.limit("100 per hour")\n@security_headers\n@log_api_request\n@jwt_required\n@admin_required\ndef create_player():'
        },
        {
            'old': '@bp.route("/players/<int:player_id>", methods=["PUT"])\ndef update_player(player_id: int):',
            'new': '@bp.route("/players/<int:player_id>", methods=["PUT"])\n@limiter.limit("200 per hour")\n@security_headers\n@log_api_request\n@jwt_required\n@admin_required\ndef update_player(player_id: int):'
        },
        {
            'old': '@bp.route("/players/<int:player_id>", methods=["DELETE"])\ndef delete_player(player_id: int):',
            'new': '@bp.route("/players/<int:player_id>", methods=["DELETE"])\n@limiter.limit("50 per hour")\n@security_headers\n@log_api_request\n@jwt_required\n@admin_required\ndef delete_player(player_id: int):'
        },
        # Teams endpoints
        {
            'old': '@bp.route("/teams/<int:team_id>")\ndef get_team(team_id: int):',
            'new': '@bp.route("/teams/<int:team_id>")\n@limiter.limit("500 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef get_team(team_id: int):'
        },
        {
            'old': '@bp.route("/teams", methods=["POST"])\ndef create_team():',
            'new': '@bp.route("/teams", methods=["POST"])\n@limiter.limit("100 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef create_team():'
        },
        {
            'old': '@bp.route("/teams/<int:team_id>", methods=["PUT"])\ndef update_team(team_id: int):',
            'new': '@bp.route("/teams/<int:team_id>", methods=["PUT"])\n@limiter.limit("200 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef update_team(team_id: int):'
        },
        {
            'old': '@bp.route("/teams/<int:team_id>", methods=["DELETE"])\ndef delete_team(team_id: int):',
            'new': '@bp.route("/teams/<int:team_id>", methods=["DELETE"])\n@limiter.limit("50 per hour")\n@security_headers\n@log_api_request\n@jwt_required\n@admin_required\ndef delete_team(team_id: int):'
        },
        # Team players
        {
            'old': '@bp.route("/teams/<int:team_id>/players")\ndef get_team_players(team_id: int):',
            'new': '@bp.route("/teams/<int:team_id>/players")\n@limiter.limit("500 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef get_team_players(team_id: int):'
        },
        # Market endpoints
        {
            'old': '@bp.route("/market/statistics")\ndef market_statistics():',
            'new': '@bp.route("/market/statistics")\n@limiter.limit("100 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef market_statistics():'
        },
        {
            'old': '@bp.route("/market/assign", methods=["POST"])\ndef assign_player():',
            'new': '@bp.route("/market/assign", methods=["POST"])\n@limiter.limit("100 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef assign_player():'
        },
        {
            'old': '@bp.route("/market/unassign", methods=["POST"])\ndef unassign_player():',
            'new': '@bp.route("/market/unassign", methods=["POST"])\n@limiter.limit("100 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef unassign_player():'
        },
        {
            'old': '@bp.route("/market/transfer", methods=["POST"])\ndef transfer_player():',
            'new': '@bp.route("/market/transfer", methods=["POST"])\n@limiter.limit("100 per hour")\n@security_headers\n@log_api_request\n@jwt_required\ndef transfer_player():'
        }
    ]

    # Apply fixes
    for fix in fixes:
        content = content.replace(fix['old'], fix['new'])

    # Write the file back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Rate limiting and security decorators added to all API endpoints!")


if __name__ == "__main__":
    fix_api_routes()
