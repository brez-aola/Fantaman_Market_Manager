"""Domain services implementing complex business logic.

Domain services contain business logic that doesn't naturally fit within
a single entity or value object. They orchestrate operations across
multiple domain objects while maintaining business invariants.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from .entities import UserEntity, TeamEntity, PlayerEntity, LeagueEntity
from .value_objects import Money, PlayerRole, TeamName, Email


class PlayerAssignmentService:
    """Domain service for player assignment operations."""

    @staticmethod
    def assign_player_to_team(
        player: PlayerEntity,
        team: TeamEntity,
        current_team_players: List[PlayerEntity]
    ) -> Tuple[bool, str]:
        """
        Assign a player to a team with business rule validation.

        Returns:
            Tuple of (success: bool, message: str)
        """

        # Check if player is available
        if not player.is_free_agent():
            return False, f"Player {player.name} is already assigned to another team"

        # Check team budget
        if not team.can_afford(player.cost):
            remaining = Money(team.cash.amount)
            return False, f"Insufficient funds. Need {player.cost}, have {remaining}"

        # Check roster limits
        role_counts = {}
        for p in current_team_players:
            role = p.role.value.value
            role_counts[role] = role_counts.get(role, 0) + 1

        player_role = player.role.value.value
        current_count = role_counts.get(player_role, 0)

        # Fantasy football roster limits
        limits = {
            'P': 3,   # Portieri
            'D': 8,   # Difensori
            'C': 8,   # Centrocampisti
            'A': 6    # Attaccanti
        }

        max_allowed = limits.get(player_role, 0)
        if current_count >= max_allowed:
            role_name = player.role.display_name()
            return False, f"Team already has maximum {role_name} players ({max_allowed})"

        # All checks passed - perform assignment
        player.assign_to_team(team.id)
        team.spend_money(player.cost)

        return True, f"Player {player.name} successfully assigned to {team.name.value}"

    @staticmethod
    def release_player_from_team(
        player: PlayerEntity,
        team: TeamEntity
    ) -> Tuple[bool, str]:
        """
        Release a player from their team.

        Returns:
            Tuple of (success: bool, message: str)
        """

        if player.is_free_agent():
            return False, f"Player {player.name} is not assigned to any team"

        if player.team_id != team.id:
            return False, f"Player {player.name} does not belong to team {team.name.value}"

        # Release player and refund money
        player.release_from_team()
        team.receive_money(player.cost)

        return True, f"Player {player.name} released from {team.name.value}"

    @staticmethod
    def transfer_player(
        player: PlayerEntity,
        from_team: TeamEntity,
        to_team: TeamEntity,
        from_team_players: List[PlayerEntity],
        to_team_players: List[PlayerEntity]
    ) -> Tuple[bool, str]:
        """
        Transfer a player between teams.

        Returns:
            Tuple of (success: bool, message: str)
        """

        # Release from current team
        release_success, release_msg = PlayerAssignmentService.release_player_from_team(
            player, from_team
        )

        if not release_success:
            return False, release_msg

        # Assign to new team
        assign_success, assign_msg = PlayerAssignmentService.assign_player_to_team(
            player, to_team, to_team_players
        )

        if not assign_success:
            # Rollback the release
            player.assign_to_team(from_team.id)
            from_team.spend_money(player.cost)
            return False, f"Transfer failed: {assign_msg}"

        return True, f"Player {player.name} transferred from {from_team.name.value} to {to_team.name.value}"


class TeamBudgetService:
    """Domain service for team budget management."""

    @staticmethod
    def calculate_team_finances(team: TeamEntity, players: List[PlayerEntity]) -> Dict[str, Money]:
        """Calculate comprehensive team financial information."""

        total_spent = Money(sum(p.cost.amount for p in players))
        remaining_budget = Money(team.cash.amount - total_spent.amount)

        # Calculate by role
        role_spending = {}
        for player in players:
            role = player.role.display_name()
            if role not in role_spending:
                role_spending[role] = Money(0.0)
            role_spending[role] = role_spending[role].add(player.cost)

        return {
            'starting_budget': team.cash,
            'total_spent': total_spent,
            'remaining_budget': remaining_budget,
            'role_spending': role_spending
        }

    @staticmethod
    def validate_budget_transaction(
        team: TeamEntity,
        transaction_amount: Money,
        transaction_type: str = "expense"
    ) -> Tuple[bool, str]:
        """Validate a budget transaction."""

        if transaction_type == "expense":
            if not team.can_afford(transaction_amount):
                return False, f"Insufficient funds. Available: {team.cash}, Required: {transaction_amount}"

        return True, "Transaction valid"

    @staticmethod
    def calculate_team_value(players: List[PlayerEntity]) -> Money:
        """Calculate total team value based on player costs."""
        total_value = sum(player.cost.amount for player in players)
        return Money(total_value)

    @staticmethod
    def suggest_budget_allocation(remaining_budget: Money) -> Dict[str, Money]:
        """Suggest budget allocation across player roles."""

        total = remaining_budget.amount

        # Suggested allocation percentages
        allocation = {
            'Portiere': 0.15,      # 15% for goalkeepers
            'Difensore': 0.30,     # 30% for defenders
            'Centrocampista': 0.35, # 35% for midfielders
            'Attaccante': 0.20     # 20% for forwards
        }

        return {
            role: Money(total * percentage)
            for role, percentage in allocation.items()
        }


class MarketService:
    """Domain service for market operations and analysis."""

    @staticmethod
    def calculate_market_statistics(players: List[PlayerEntity]) -> Dict[str, any]:
        """Calculate comprehensive market statistics."""

        if not players:
            return {
                'total_players': 0,
                'free_agents': 0,
                'assigned_players': 0,
                'total_market_value': Money(0.0),
                'average_player_cost': Money(0.0),
                'role_distribution': {},
                'cost_ranges': {}
            }

        # Basic counts
        total_players = len(players)
        free_agents = len([p for p in players if p.is_free_agent()])
        assigned_players = total_players - free_agents

        # Market value calculations
        total_value = sum(p.cost.amount for p in players)
        average_cost = total_value / total_players if total_players > 0 else 0

        # Role distribution
        role_distribution = {}
        for player in players:
            role = player.role.display_name()
            if role not in role_distribution:
                role_distribution[role] = {
                    'total': 0,
                    'free_agents': 0,
                    'assigned': 0,
                    'total_value': Money(0.0),
                    'average_cost': Money(0.0)
                }

            stats = role_distribution[role]
            stats['total'] += 1
            stats['total_value'] = stats['total_value'].add(player.cost)

            if player.is_free_agent():
                stats['free_agents'] += 1
            else:
                stats['assigned'] += 1

        # Calculate average costs by role
        for role_stats in role_distribution.values():
            if role_stats['total'] > 0:
                avg = role_stats['total_value'].amount / role_stats['total']
                role_stats['average_cost'] = Money(avg)

        # Cost ranges
        costs = [p.cost.amount for p in players]
        cost_ranges = {
            'minimum': Money(min(costs)) if costs else Money(0.0),
            'maximum': Money(max(costs)) if costs else Money(0.0),
            'median': Money(sorted(costs)[len(costs)//2]) if costs else Money(0.0)
        }

        return {
            'total_players': total_players,
            'free_agents': free_agents,
            'assigned_players': assigned_players,
            'total_market_value': Money(total_value),
            'average_player_cost': Money(average_cost),
            'role_distribution': role_distribution,
            'cost_ranges': cost_ranges
        }

    @staticmethod
    def find_players_in_budget(
        players: List[PlayerEntity],
        budget: Money,
        role: Optional[PlayerRole] = None
    ) -> List[PlayerEntity]:
        """Find players within a given budget, optionally filtered by role."""

        candidates = []
        for player in players:
            # Check budget constraint
            if player.cost.amount > budget.amount:
                continue

            # Check role constraint
            if role and player.role != role:
                continue

            # Only consider free agents
            if not player.is_free_agent():
                continue

            candidates.append(player)

        # Sort by cost (ascending) for best value first
        return sorted(candidates, key=lambda p: p.cost.amount)

    @staticmethod
    def suggest_team_improvements(
        team: TeamEntity,
        current_players: List[PlayerEntity],
        all_players: List[PlayerEntity]
    ) -> Dict[str, List[PlayerEntity]]:
        """Suggest player improvements for a team."""

        finances = TeamBudgetService.calculate_team_finances(team, current_players)
        remaining_budget = finances['remaining_budget']

        suggestions = {}

        # Role limits and current counts
        limits = {'P': 3, 'D': 8, 'C': 8, 'A': 6}
        current_counts = {}

        for player in current_players:
            role_code = player.role.value.value
            current_counts[role_code] = current_counts.get(role_code, 0) + 1

        # Find positions that need filling
        for role_code, max_players in limits.items():
            current_count = current_counts.get(role_code, 0)
            if current_count < max_players:
                # Find suitable players for this role
                role_enum = PlayerRole.from_string(role_code)
                affordable_players = MarketService.find_players_in_budget(
                    all_players, remaining_budget, role_enum
                )

                if affordable_players:
                    role_name = role_enum.display_name()
                    suggestions[f"{role_name} (need {max_players - current_count})"] = affordable_players[:5]

        return suggestions


class LeagueManagementService:
    """Domain service for league management operations."""

    @staticmethod
    def validate_league_integrity(
        league: LeagueEntity,
        teams: List[TeamEntity],
        all_players: List[PlayerEntity]
    ) -> Tuple[bool, List[str]]:
        """Validate league integrity and return any issues found."""

        issues = []

        # Check team count
        if len(teams) > league.max_teams:
            issues.append(f"League has {len(teams)} teams, maximum allowed is {league.max_teams}")

        # Check for duplicate team names
        team_names = [team.name.value for team in teams]
        if len(team_names) != len(set(team_names)):
            issues.append("League contains teams with duplicate names")

        # Check player assignments
        assigned_players = [p for p in all_players if not p.is_free_agent()]
        team_ids = {team.id for team in teams}

        for player in assigned_players:
            if player.team_id not in team_ids:
                issues.append(f"Player {player.name} assigned to non-existent team ID {player.team_id}")

        # Check roster limits for each team
        for team in teams:
            team_players = [p for p in assigned_players if p.team_id == team.id]
            if not team.validate_roster_limits(team_players):
                issues.append(f"Team {team.name.value} exceeds roster limits")

        return len(issues) == 0, issues

    @staticmethod
    def calculate_league_statistics(
        league: LeagueEntity,
        teams: List[TeamEntity],
        players: List[PlayerEntity]
    ) -> Dict[str, any]:
        """Calculate comprehensive league statistics."""

        league_players = [p for p in players if p.team_id in {t.id for t in teams}]
        free_agents = [p for p in players if p.is_free_agent()]

        total_cash = sum(team.cash.amount for team in teams)
        total_invested = sum(p.cost.amount for p in league_players)

        team_stats = []
        for team in teams:
            team_players = [p for p in league_players if p.team_id == team.id]
            team_value = sum(p.cost.amount for p in team_players)

            team_stats.append({
                'team_name': team.name.value,
                'players': len(team_players),
                'team_value': Money(team_value),
                'remaining_budget': Money(team.cash.amount - team_value),
                'roster_complete': len(team_players) >= 22  # Minimum squad size
            })

        return {
            'league_name': league.name,
            'total_teams': len(teams),
            'max_teams': league.max_teams,
            'total_players_assigned': len(league_players),
            'free_agents_available': len(free_agents),
            'total_cash_in_league': Money(total_cash),
            'total_invested': Money(total_invested),
            'average_team_value': Money(total_invested / len(teams)) if teams else Money(0.0),
            'teams': team_stats
        }
