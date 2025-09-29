"""Use Cases Layer - Application layer containing business use cases.

This layer orchestrates domain entities and services to fulfill business requirements.
Use cases represent specific business scenarios and coordinate domain operations.
"""

# Export all use cases
from .player_use_cases import *
from .team_use_cases import *
from .user_use_cases import *
from .league_use_cases import *
from .market_use_cases import *

__all__ = [
    # Player Use Cases
    "AssignPlayerUseCase", "SearchPlayersUseCase", "TransferPlayerUseCase",
    "PlayerDTO", "AssignPlayerRequest", "SearchPlayersRequest", "TransferPlayerRequest",
    "SearchPlayersResult", "PlayerRepositoryInterface", "TeamRepositoryInterface",

    # Team Use Cases
    "CreateTeamUseCase", "GetTeamUseCase", "ListTeamsUseCase", "UpdateTeamBudgetUseCase",
    "CheckTeamBudgetUseCase", "TeamDTO", "TeamBudgetDTO", "CreateTeamRequest",
    "UpdateTeamBudgetRequest", "GetTeamRequest", "ListTeamsRequest", "ListTeamsResult",

    # User Use Cases
    "CreateUserUseCase", "GetUserUseCase", "GetUserByUsernameUseCase", "ListUsersUseCase",
    "UpdateUserUseCase", "LoginUserUseCase", "DeactivateUserUseCase", "ActivateUserUseCase",
    "UserDTO", "CreateUserRequest", "UpdateUserRequest", "LoginRequest", "LoginResult",
    "ListUsersRequest", "ListUsersResult", "UserRepositoryInterface",

    # League Use Cases
    "CreateLeagueUseCase", "GetLeagueUseCase", "ListLeaguesUseCase", "UpdateLeagueUseCase",
    "AddTeamToLeagueUseCase", "RemoveTeamFromLeagueUseCase", "GetLeagueStatsUseCase",
    "GetAvailableLeaguesUseCase", "LeagueDTO", "LeagueStatsDTO", "CreateLeagueRequest",
    "UpdateLeagueRequest", "AddTeamToLeagueRequest", "ListLeaguesRequest", "ListLeaguesResult",
    "LeagueRepositoryInterface",

    # Market Use Cases
    "GetMarketStatsUseCase", "SearchMarketUseCase", "AnalyzeTransferUseCase",
    "GetTopTransferTargetsUseCase", "GetMarketTrendsUseCase", "MarketStatsDTO",
    "PlayerMarketValueDTO", "TransferOpportunityDTO", "GetMarketStatsRequest",
    "SearchMarketRequest", "SearchMarketResult", "TransferAnalysisRequest",
    "MarketRepositoryInterface",
]

from .player_use_cases import *
from .team_use_cases import *
from .user_use_cases import *
from .league_use_cases import *
from .market_use_cases import *

__all__ = [
    # Player Use Cases
    'AssignPlayerUseCase', 'ReleasePlayerUseCase', 'TransferPlayerUseCase',
    'SearchPlayersUseCase', 'GetPlayerDetailsUseCase',

    # Team Use Cases
    'CreateTeamUseCase', 'GetTeamRosterUseCase', 'UpdateTeamBudgetUseCase',
    'GetTeamStatisticsUseCase', 'ValidateTeamRosterUseCase',

    # User Use Cases
    'LoginUserUseCase', 'CreateUserUseCase', 'UpdateUserRoleUseCase',
    'ResetPasswordUseCase', 'GetUserPermissionsUseCase',

    # League Use Cases
    'CreateLeagueUseCase', 'AddTeamToLeagueUseCase', 'GetLeagueStandingsUseCase',
    'ValidateLeagueIntegrityUseCase', 'GetLeagueStatisticsUseCase',

    # Market Use Cases
    'GetMarketStatisticsUseCase', 'SearchMarketUseCase', 'GetFreeAgentsUseCase',
    'SuggestPlayerRecommendationsUseCase'
]
