"""OpenAPI/Swagger documentation setup for the Fantacalcio API.

This module configures Flask-RESTX for automatic API documentation generation.
Provides interactive Swagger UI at /docs/
"""

from flask import Blueprint
from flask_restx import Api, Resource, fields
from flask_restx.namespace import Namespace
from flask import jsonify

# Create blueprint for API documentation
doc_bp = Blueprint('docs', __name__, url_prefix='/docs')

# Configure Flask-RESTX API with security
api = Api(
    doc_bp,
    version='2.0.0',
    title='Fantacalcio Market Manager API',
    description='''
    ## Comprehensive REST API for Fantacalcio Market Manager

    This API provides complete functionality for managing fantasy football leagues, teams, players, and market operations.

    ### Features:
    - **Authentication & Security**: JWT-based authentication with role-based access control
    - **Player Management**: CRUD operations for players with input validation
    - **Team Management**: CRUD operations for teams with authorization
    - **Market Operations**: Player assignments, transfers, statistics
    - **User Management**: Registration, login, profile management
    - **League Management**: League creation and statistics
    - **Rate Limiting**: API protection against abuse
    - **Input Validation**: Comprehensive request validation

    ### Authentication:
    This API uses JWT (JSON Web Tokens) for authentication. To access protected endpoints:

    1. **Register** a new account at `/api/v1/auth/register`
    2. **Login** with credentials at `/api/v1/auth/login` to get JWT tokens
    3. **Include** the access token in the `Authorization` header: `Bearer <token>`

    ### Rate Limits:
    - Authentication: 10 requests per minute
    - Create operations: 100 requests per hour
    - Read operations: 500 requests per hour
    - Update/Delete: 200/50 requests per hour respectively

    ### Security:
    - **Input Validation**: All requests validated using Marshmallow schemas
    - **HTTPS Required**: All production traffic must use HTTPS
    - **CORS Protection**: Configured for allowed origins only
    - **Security Headers**: Comprehensive security headers on all responses
    Most endpoints require authentication. Include JWT token in Authorization header:
    ```
    Authorization: Bearer <your-jwt-token>
    ```

    ### Error Responses:
    All endpoints return consistent error responses:
    ```json
    {
        "error": "Error description",
        "code": "ERROR_CODE",
        "details": {}
    }
    ```

    ### Base URL:
    All API endpoints are prefixed with `/api/v1/`
    ''',
    doc='/swagger/',
    contact='Fantacalcio Team',
    contact_email='admin@fantacalcio.local',
    authorizations={
        'Bearer': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'JWT Authorization header. Example: "Bearer {token}"'
        }
    },
    security='Bearer'
)


# Expose the OpenAPI JSON explicitly at /docs/swagger.json for external tools/tests
@doc_bp.route('/swagger.json')
def openapi_json():
    try:
        # api.__schema__ is provided by flask-restx and contains the OpenAPI spec
        return jsonify(api.__schema__)
    except Exception:
        # Fallback: return minimal metadata
        return jsonify({
            'info': {
                'title': api.title,
                'version': api.version
            }
        })

# Define namespaces for organization
auth_ns = Namespace('auth', description='Authentication and authorization operations')
players_ns = Namespace('players', description='Player management operations')
teams_ns = Namespace('teams', description='Team management operations')
market_ns = Namespace('market', description='Market operations and statistics')
users_ns = Namespace('users', description='User management and authentication')
leagues_ns = Namespace('leagues', description='League management')

# Add namespaces to API
api.add_namespace(auth_ns, path='/api/v1/auth')
api.add_namespace(players_ns, path='/api/v1/players')
api.add_namespace(teams_ns, path='/api/v1/teams')
api.add_namespace(market_ns, path='/api/v1/market')
api.add_namespace(users_ns, path='/api/v1/users')
api.add_namespace(leagues_ns, path='/api/v1/leagues')

# =======================
# API Models (Schemas)
# =======================

# Authentication Models
login_model = api.model('Login', {
    'username': fields.String(required=True, description='Username (3-50 characters)', min_length=3, max_length=50),
    'password': fields.String(required=True, description='Password (6+ characters)', min_length=6)
})

register_model = api.model('Register', {
    'username': fields.String(required=True, description='Username (3-50 characters, letters/numbers/underscore only)', min_length=3, max_length=50),
    'email': fields.String(required=True, description='Valid email address'),
    'password': fields.String(required=True, description='Password (6+ characters)', min_length=6),
    'confirm_password': fields.String(required=True, description='Password confirmation')
})

token_response_model = api.model('TokenResponse', {
    'access_token': fields.String(description='JWT access token'),
    'refresh_token': fields.String(description='JWT refresh token'),
    'token_type': fields.String(description='Token type', default='Bearer'),
    'expires_in': fields.Integer(description='Access token expiration time in seconds'),
    'user': fields.Nested('User', description='User information')
})

user_model = api.model('User', {
    'username': fields.String(description='Username'),
    'email': fields.String(description='Email address'),
    'roles': fields.List(fields.String, description='User roles'),
    'is_active': fields.Boolean(description='User account status'),
    'created_at': fields.String(description='Account creation date'),
    'last_login': fields.String(description='Last login date')
})

error_model = api.model('Error', {
    'error': fields.String(description='Error message'),
    'code': fields.String(description='Error code'),
    'details': fields.Raw(description='Additional error details')
})

validation_error_model = api.model('ValidationError', {
    'error': fields.String(description='Error message', default='Validation failed'),
    'code': fields.String(description='Error code', default='VALIDATION_ERROR'),
    'details': fields.Raw(description='Field-specific validation errors')
})

# Player Models
player_model = api.model('Player', {
    'id': fields.Integer(readonly=True, description='Player unique identifier'),
    'name': fields.String(required=True, description='Player full name'),
    'role': fields.String(required=True, description='Player position', enum=['P', 'D', 'C', 'A']),
    'cost': fields.Float(description='Player market value'),
    'real_team': fields.String(description='Real football team'),
    'team_id': fields.Integer(description='Assigned fantasy team ID'),
    'team_name': fields.String(readonly=True, description='Assigned fantasy team name'),
    'contract_years': fields.Integer(description='Contract duration in years'),
    'option': fields.Boolean(description='Contract option available')
})

player_create_model = api.model('PlayerCreate', {
    'name': fields.String(required=True, description='Player full name'),
    'role': fields.String(required=True, description='Player position', enum=['P', 'D', 'C', 'A']),
    'cost': fields.Float(description='Player market value', default=0.0),
    'real_team': fields.String(description='Real football team'),
    'team_id': fields.Integer(description='Assign to fantasy team'),
    'contract_years': fields.Integer(description='Contract duration', default=1),
    'option': fields.Boolean(description='Contract option', default=False)
})

player_update_model = api.model('PlayerUpdate', {
    'name': fields.String(description='Player full name'),
    'role': fields.String(description='Player position', enum=['P', 'D', 'C', 'A']),
    'cost': fields.Float(description='Player market value'),
    'real_team': fields.String(description='Real football team'),
    'team_id': fields.Integer(description='Fantasy team assignment'),
    'contract_years': fields.Integer(description='Contract duration'),
    'option': fields.Boolean(description='Contract option')
})

# Team Models
team_model = api.model('Team', {
    'id': fields.Integer(readonly=True, description='Team unique identifier'),
    'name': fields.String(required=True, description='Team name'),
    'cash': fields.Float(description='Available budget'),
    'league_id': fields.Integer(description='League membership'),
    'league_name': fields.String(readonly=True, description='League name')
})

team_create_model = api.model('TeamCreate', {
    'name': fields.String(required=True, description='Team name'),
    'cash': fields.Float(description='Starting budget', default=300.0),
    'league_id': fields.Integer(description='League to join', default=1)
})

team_update_model = api.model('TeamUpdate', {
    'name': fields.String(description='Team name'),
    'cash': fields.Float(description='Available budget'),
    'league_id': fields.Integer(description='League membership')
})

# Market Models
market_assignment_model = api.model('MarketAssignment', {
    'player_id': fields.Integer(required=True, description='Player to assign'),
    'team_id': fields.Integer(required=True, description='Destination team')
})

market_transfer_model = api.model('MarketTransfer', {
    'player_id': fields.Integer(required=True, description='Player to transfer'),
    'from_team_id': fields.Integer(required=True, description='Source team'),
    'to_team_id': fields.Integer(required=True, description='Destination team'),
    'cost': fields.Float(description='Transfer fee', default=0.0),
    'new_cost': fields.Float(description='New player market value')
})

market_stats_model = api.model('MarketStatistics', {
    'total_players': fields.Integer(description='Total players in database'),
    'assigned_players': fields.Integer(description='Players assigned to teams'),
    'free_agents': fields.Integer(description='Unassigned players'),
    'role_distribution': fields.Raw(description='Players by role')
})

# User Models
user_model = api.model('User', {
    'id': fields.Integer(readonly=True, description='User unique identifier'),
    'username': fields.String(required=True, description='Unique username'),
    'email': fields.String(required=True, description='User email address'),
    'is_admin': fields.Boolean(readonly=True, description='Admin privileges'),
    'created_at': fields.DateTime(readonly=True, description='Account creation date')
})

# League Models
league_model = api.model('League', {
    'id': fields.Integer(readonly=True, description='League unique identifier'),
    'name': fields.String(required=True, description='League name'),
    'slug': fields.String(readonly=True, description='League URL slug'),
    'teams_count': fields.Integer(readonly=True, description='Number of teams'),
    'max_teams': fields.Integer(description='Maximum teams allowed')
})

# Response Models
success_response_model = api.model('SuccessResponse', {
    'message': fields.String(description='Success message'),
    'data': fields.Raw(description='Response data')
})

error_response_model = api.model('ErrorResponse', {
    'error': fields.String(description='Error message'),
    'code': fields.String(description='Error code'),
    'details': fields.Raw(description='Additional error details')
})

# =======================
# API Documentation Resources
# =======================

@api.route('/health')
class HealthCheck(Resource):
    @api.doc('health_check')
    @api.marshal_with(success_response_model)
    def get(self):
        """System health check endpoint

        Returns system status and database connectivity.
        No authentication required.
        """
        pass

# Players Namespace Documentation
@players_ns.route('/')
class PlayersCollection(Resource):
    @api.doc('list_players')
    @api.expect(api.parser().add_argument('role', type=str, help='Filter by role'))
    @api.expect(api.parser().add_argument('team_id', type=int, help='Filter by team'))
    @api.expect(api.parser().add_argument('free_agents', type=bool, help='Show only unassigned'))
    @api.marshal_list_with(player_model)
    def get(self):
        """Get list of players

        Returns paginated list of players with optional filtering.
        """
        pass

    @api.doc('create_player')
    @api.expect(player_create_model)
    @api.marshal_with(player_model, code=201)
    @api.response(400, 'Validation Error', error_response_model)
    def post(self):
        """Create new player

        Creates a new player in the system.
        Requires admin privileges.
        """
        pass

@players_ns.route('/<int:player_id>')
class Player(Resource):
    @api.doc('get_player')
    @api.marshal_with(player_model)
    @api.response(404, 'Player not found', error_response_model)
    def get(self, player_id):
        """Get player by ID

        Returns detailed information about a specific player.
        """
        pass

    @api.doc('update_player')
    @api.expect(player_update_model)
    @api.marshal_with(player_model)
    @api.response(404, 'Player not found', error_response_model)
    def put(self, player_id):
        """Update player

        Updates player information.
        Requires admin privileges or team ownership.
        """
        pass

    @api.doc('delete_player')
    @api.marshal_with(success_response_model)
    @api.response(404, 'Player not found', error_response_model)
    def delete(self, player_id):
        """Delete player

        Removes player from system.
        Requires admin privileges.
        """
        pass

# Teams Namespace Documentation
@teams_ns.route('/')
class TeamsCollection(Resource):
    @api.doc('list_teams')
    @api.marshal_list_with(team_model)
    def get(self):
        """Get list of teams

        Returns all teams in the system.
        """
        pass

    @api.doc('create_team')
    @api.expect(team_create_model)
    @api.marshal_with(team_model, code=201)
    def post(self):
        """Create new team

        Creates a new fantasy team.
        Requires authentication.
        """
        pass

@teams_ns.route('/<int:team_id>')
class Team(Resource):
    @api.doc('get_team')
    @api.marshal_with(team_model)
    @api.response(404, 'Team not found', error_response_model)
    def get(self, team_id):
        """Get team by ID

        Returns detailed team information.
        """
        pass

    @api.doc('update_team')
    @api.expect(team_update_model)
    @api.marshal_with(team_model)
    def put(self, team_id):
        """Update team

        Updates team information.
        Requires team ownership or admin privileges.
        """
        pass

    @api.doc('delete_team')
    @api.marshal_with(success_response_model)
    @api.response(409, 'Team has assigned players', error_response_model)
    def delete(self, team_id):
        """Delete team

        Removes team from system.
        Cannot delete teams with assigned players.
        """
        pass

@teams_ns.route('/<int:team_id>/players')
class TeamPlayers(Resource):
    @api.doc('get_team_players')
    @api.marshal_list_with(player_model)
    def get(self, team_id):
        """Get team's players

        Returns all players assigned to the team.
        """
        pass

# Market Namespace Documentation
@market_ns.route('/statistics')
class MarketStatistics(Resource):
    @api.doc('get_market_stats')
    @api.marshal_with(market_stats_model)
    def get(self):
        """Get market statistics

        Returns comprehensive market analytics.
        """
        pass

@market_ns.route('/assign')
class MarketAssign(Resource):
    @api.doc('assign_player')
    @api.expect(market_assignment_model)
    @api.marshal_with(success_response_model)
    @api.response(404, 'Player or team not found', error_response_model)
    @api.response(409, 'Player already assigned', error_response_model)
    def post(self):
        """Assign player to team

        Assigns an unassigned player to a team.
        """
        pass

@market_ns.route('/unassign')
class MarketUnassign(Resource):
    @api.doc('unassign_player')
    @api.expect(api.model('PlayerUnassign', {
        'player_id': fields.Integer(required=True, description='Player to unassign')
    }))
    @api.marshal_with(success_response_model)
    def post(self):
        """Unassign player from team

        Removes player from their current team.
        """
        pass

@market_ns.route('/transfer')
class MarketTransfer(Resource):
    @api.doc('transfer_player')
    @api.expect(market_transfer_model)
    @api.marshal_with(success_response_model)
    @api.response(400, 'Insufficient budget', error_response_model)
    def post(self):
        """Transfer player between teams

        Transfers player from one team to another with optional fee.
        """
        pass


def init_api_docs(app):
    """Initialize API documentation in Flask app."""
    # Register the docs blueprint if not already registered (idempotent)
    if doc_bp.name not in app.blueprints:
        app.register_blueprint(doc_bp)

    return api
