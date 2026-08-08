import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_confluence import (
    router as ai_confluence_router,
)
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.security_audit_logs import router as security_audit_logs_router
from app.api.admin_users import router as admin_users_router
from app.api.automated_market_pipeline import (
    router as automated_market_pipeline_router,
)
from app.api.cache import router as cache_router
from app.api.cache_refresh import (
    router as cache_refresh_router,
)
from app.api.context import router as context_router
from app.api.context_decision import (
    router as context_decision_router,
)
from app.api.dashboard import router as dashboard_router
from app.api.decision import router as decision_router
from app.api.dynamic_confidence import (
    router as dynamic_confidence_router,
)
from app.api.health import router as health_router
from app.api.history import router as history_router
from app.api.institutional_smc import (
    router as institutional_smc_router,
)
from app.api.learning import router as learning_router
from app.api.learning_intelligence import (
    router as learning_intelligence_router,
)
from app.api.learning_persistence import (
    router as learning_persistence_router,
)
from app.api.learning_analytics import (
    router as learning_analytics_router,
)
from app.api.confidence_guardrail import (
    router as confidence_guardrail_router,
)
from app.api.market import router as market_router
from app.api.market_session import (
    router as market_session_router,
)
from app.api.economic_news import (
    router as economic_news_router,
)
from app.api.fundamental_analysis import (
    router as fundamental_analysis_router,
)
from app.api.market_regime import (
    router as market_regime_router,
)
from app.api.master_signal_pipeline import (
    router as master_signal_pipeline_router,
)
from app.api.symbol_winrate import (
    router as symbol_winrate_router,
)
from app.api.multi_timeframe import (
    router as multi_timeframe_router,
)
from app.api.multi_timeframe_pipeline import (
    router as multi_timeframe_pipeline_router,
)
from app.api.trading import router as trading_router
from app.api.roles import router as roles_router
from app.api.admin_dashboard import router as admin_dashboard_router
from app.api.signals import router as signals_router
from app.api.signal_performance import router as signal_performance_router
from app.api.background_jobs import router as background_jobs_router
from app.api.monitoring import router as monitoring_router
from app.api.readiness import router as readiness_router
from app.api.deployment import router as deployment_router
from app.api.signal_quality import router as signal_quality_router

from app.core.config import settings
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.core.security_middleware import (
    RequestBodyLimitMiddleware,
    RequestTimingMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.application_monitoring_middleware import (
    ApplicationMonitoringMiddleware,
)

from app.services.market_cache_refresh_service import (
    start_market_cache_refresh_service,
    stop_market_cache_refresh_service,
)
from app.services.learning_persistence_service import (
    initialise_learning_persistence,
)
from app.services.background_worker import run_background_worker

from app.database.connection import (
    Base,
    SessionLocal,
    engine,
)
from app.services.role_permission_service import (
    seed_default_roles_and_permissions,
)

# Import models before creating database tables.
# These imports register the models with SQLAlchemy metadata.
from app.models.account_action_token import AccountActionToken
from app.models.auth_session import AuthSession
from app.models.refresh_token import RefreshToken
from app.models.role_permission import (
    Permission,
    Role,
    UserRole,
    role_permissions,
)
from app.models.trading_signal import TradingSignal
from app.models.background_job import BackgroundJob
from app.models.application_event_log import ApplicationEventLog
from app.models.trade_history import TradeHistory
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User


APP_VERSION = "49.0.0"


def _validate_runtime_security_configuration() -> None:
    """
    Fail closed on unsafe production-only runtime configuration.

    Deployment/readiness endpoints are useful diagnostics, but an unsafe
    production CORS policy should never be allowed to start serving traffic.
    """

    if (
        settings.is_production
        and "*" in settings.cors_origin_list
    ):
        raise RuntimeError(
            "Wildcard CORS origins are not allowed in production."
        )


def _create_development_tables() -> None:
    """
    Create registered tables only for local development and tests.

    Production deployments must use migrations rather than modifying
    the database schema during application import or startup.
    """

    if settings.is_production:
        return

    Base.metadata.create_all(
        bind=engine
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Start and stop Blue-Trading-AI background services safely.
    """

    _validate_runtime_security_configuration()
    _create_development_tables()

    role_db = SessionLocal()

    cache_service_started = False
    background_stop_event: asyncio.Event | None = None
    background_worker_task: asyncio.Task[Any] | None = None

    try:
        seed_default_roles_and_permissions(
            role_db,
            commit=True,
        )
    except Exception:
        role_db.rollback()
        raise
    finally:
        role_db.close()

    try:
        await start_market_cache_refresh_service()
        cache_service_started = True

        # Version 28 persistent learning restore.
        initialise_learning_persistence()

        # Version 45 persistent background-job worker.
        background_stop_event = asyncio.Event()
        background_worker_task = asyncio.create_task(
            run_background_worker(
                stop_event=background_stop_event,
            ),
            name="blue-trading-ai-background-worker",
        )

        app.state.background_worker_stop_event = (
            background_stop_event
        )
        app.state.background_worker_task = (
            background_worker_task
        )

        yield
    finally:
        if background_stop_event is not None:
            background_stop_event.set()

        if background_worker_task is not None:
            try:
                await asyncio.wait_for(
                    background_worker_task,
                    timeout=10,
                )
            except asyncio.TimeoutError:
                background_worker_task.cancel()

                try:
                    await background_worker_task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass
            except Exception:
                # Shutdown must continue so the remaining services
                # are not left running after a worker failure.
                pass

        if cache_service_started:
            await stop_market_cache_refresh_service()


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered market analysis and "
        "trading signal platform"
    ),
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url=(
        None
        if settings.is_production
        else "/docs"
    ),
    redoc_url=(
        None
        if settings.is_production
        else "/redoc"
    ),
    openapi_url=(
        None
        if settings.is_production
        else "/openapi.json"
    ),
)


# ==========================
# VERSION 36 API PROTECTION
# ==========================

cors_origins = settings.cors_origin_list
cors_allows_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_allows_credentials,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
    ],
    expose_headers=[
        "X-Request-ID",
        "X-Process-Time-Ms",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-RateLimit-Rule",
        "Retry-After",
    ],
)

app.add_middleware(ApplicationMonitoringMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RateLimitMiddleware)


# ==========================
# API ROUTERS
# ==========================

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(security_audit_logs_router)
app.include_router(admin_users_router)
app.include_router(roles_router)
app.include_router(admin_dashboard_router)
app.include_router(signals_router)
app.include_router(signal_performance_router)
app.include_router(background_jobs_router)
app.include_router(monitoring_router)
app.include_router(readiness_router)
app.include_router(deployment_router)
app.include_router(signal_quality_router)
app.include_router(trading_router)
app.include_router(market_router)
app.include_router(history_router)
app.include_router(analytics_router)
app.include_router(dashboard_router)
app.include_router(learning_router)
app.include_router(decision_router)
app.include_router(context_router)
app.include_router(context_decision_router)
app.include_router(institutional_smc_router)
app.include_router(ai_confluence_router)

# Version 17 Multi-Timeframe Intelligence Engine
app.include_router(multi_timeframe_router)

app.include_router(dynamic_confidence_router)
app.include_router(master_signal_pipeline_router)

# Version 20 automated market-data pipelines
app.include_router(automated_market_pipeline_router)
app.include_router(multi_timeframe_pipeline_router)

# Version 21 cache and smart request manager
app.include_router(cache_router)

# Version 21 automatic cache refresh controls
app.include_router(cache_refresh_router)

# Version 22 market session intelligence
app.include_router(market_session_router)

# Version 23 economic news intelligence
app.include_router(economic_news_router)

# Version 24 fundamental analysis intelligence
app.include_router(fundamental_analysis_router)

# Version 25 market regime intelligence
app.include_router(market_regime_router)

# Version 26 symbol win rate intelligence
app.include_router(symbol_winrate_router)

# Version 27 AI self-learning intelligence
app.include_router(learning_intelligence_router)

# Version 28 persistent learning intelligence
app.include_router(learning_persistence_router)

# Version 29 learning analytics and confidence calibration
app.include_router(learning_analytics_router)

# Version 30 confidence guardrail intelligence
app.include_router(confidence_guardrail_router)


# ==========================
# HOME TEST
# ==========================

@app.get("/")
def home() -> dict[str, Any]:
    if settings.is_production:
        return {
            "message": (
                "Welcome to "
                f"{settings.APP_NAME}"
            ),
            "status": "Backend is running",
            "version": APP_VERSION,
            "environment": "production",
            "documentation_enabled": False,
            "analysis_only": True,
            "trade_execution_enabled": False,
        }

    return {
        "message": "Welcome to Blue-Trading-AI",
        "status": "Backend is running",
        "version": APP_VERSION,
        "safety_version": 49,
        "environment": settings.ENVIRONMENT,
        "documentation_enabled": (
            not settings.is_production
        ),
        "cors_credentials_enabled": (
            cors_allows_credentials
        ),

        "modules": [
            "Authentication",
            "Database-Backed Authentication Sessions",
            "Secure Refresh Tokens",
            "Email Verification",
            "Single-Use Verification Tokens",
            "Secure Password Reset",
            "Single-Use Password Reset Tokens",
            "Account Token Expiry Enforcement",
            "Real SMTP Email Delivery",
            "Verification Email Delivery",
            "Password Reset Email Delivery",
            "Roles and Permissions",
            "Role-Based Access Control",
            "Owner-Protected Role Management",
            "Permission-Protected API Routes",
            "Role Assignment Tracking",
            "Role Revocation Tracking",
            "Admin Dashboard API",
            "Admin User Statistics",
            "Admin Session Health",
            "Admin Security Metrics",
            "Admin Role Statistics",
            "Recent Security Event Feed",
            "Persistent Trading Signal Database",
            "Signal Quality Enforcement",
            "High-Quality Signal Publication Control",
            "Signal Status Management",
            "Signal Result Tracking",
            "Signal History API",
            "Signal Performance Tracking",
            "Win Rate Analytics",
            "Symbol Performance Analytics",
            "Timeframe Performance Analytics",
            "Completed Trade Learning Readiness",
            "Persistent Background Job Queue",
            "Async Market Data Worker",
            "Signal Generation Worker",
            "Worker Heartbeats and Retry Recovery",
            "Structured Production Logging",
            "HTTP Request Monitoring",
            "Slow Request Detection",
            "Health Monitoring",
            "Sensitive Data Redaction",
            "Production Readiness Audit",
            "Final Security Verification",
            "Final Performance Verification",
            "Database Index Verification",
            "Deployment Validation",
            "Production Environment Validation",
            "HTTPS and CORS Validation",
            "Production Database Validation",
            "Deployment Safety Enforcement",
            "Refresh Token Rotation",
            "Refresh Token Reuse Detection",
            "Refresh Token Family Revocation",
            "Automatic Secure Token Renewal",
            "Individual Session Revocation",
            "Secure Logout",
            "Revoke All Devices",
            "Session Expiry Validation",
            "Session Activity Tracking",
            "Hashed JWT Identifier Storage",
            "Owner-Controlled User Approval",
            "Secure Password Change",
            "Failed Login Tracking",
            "Security Audit Logging",
            "API Security Headers",
            "Request ID Tracking",
            "Request Body Size Protection",
            "Request Timing Monitoring",
            "Route-Aware API Rate Limiting",
            "Hardened CORS Configuration",
            "Authentication Event History",
            "Owner Action Audit Trail",
            "Security Event Filtering",
            "Security Audit Summary",
            "Temporary Login Lockout",
            "Owner Manual Account Unlock",
            "Last Successful Login Tracking",
            "Password Versioning",
            "Automatic Old-Token Revocation",
            "Forced Re-Login After Password Change",
            "Pending Account Review",
            "Approved User Access Control",
            "Rejected User Blocking",
            "Suspended User Blocking",
            "Owner-Only User Administration",
            "Market Data",
            "Trading AI",
            "Signal History",
            "Version 30 Completed-Trade Registration",
            "Cancelled Trade Learning",
            "Duplicate Learning Prevention",
            "Trade Tracking",
            "Performance Statistics",
            "Daily Win Rate Analytics",
            "Weekly Win Rate Analytics",
            "Monthly Win Rate Analytics",
            "Dashboard Summary API",
            "Controlled Learning Adjustment",
            "Decision Intelligence Engine",
            "Market Context Intelligence",
            "Context-Aware Decision Integration",
            "Institutional Smart Money Intelligence",
            "AI Confluence Engine",
            "Multi-Timeframe Intelligence Engine",
            "Dynamic Confidence & Signal Ranking Engine",
            "Master Signal Pipeline Engine",
            "Automated Market Analysis Pipeline",
            "Automated Multi-Timeframe Market Pipeline",
            "Market Data Cache Engine",
            "Smart Market Request Manager",
            "API Rate-Limit Protection",
            "Stale Market Data Fallback",
            "Cache Monitoring API",
            "Automatic Market Cache Refresh Service",
            "Cache Refresh Subscription API",
            "Market Session Intelligence",
            "Asian Session Intelligence",
            "European Session Intelligence",
            "US Session Intelligence",
            "Market Session Overlap Detection",
            "Session Strength Scoring",
            "Session Liquidity Scoring",
            "Session Volatility Scoring",
            "Symbol Session Preference",
            "Session Confidence Adjustment",
            "Economic News Intelligence",
            "Economic Calendar Intelligence",
            "Currency-Specific News Filtering",
            "High-Impact News Detection",
            "Economic News Risk Scoring",
            "Economic News Blackout Protection",
            "Economic News Confidence Adjustment",
            "Economic News Signal Integration",
            "Fundamental Analysis Intelligence",
            "Currency Fundamental Strength Scoring",
            "Interest Rate Analysis",
            "Central Bank Policy Bias",
            "Inflation Analysis",
            "GDP & PMI Growth Analysis",
            "Employment Analysis",
            "Currency Strength Comparison",
            "Fundamental Confidence Adjustment",
            "Fundamental Signal Integration",
            "Market Regime Intelligence",
            "Bull/Bear Regime Detection",
            "Breakout Regime Detection",
            "Accumulation & Distribution Detection",
            "Market Regime Confidence Adjustment",
            "Market Regime Signal Integration",
            "Symbol Win Rate Intelligence",
            "Symbol Confidence Learning",
            "AI Self-Learning Intelligence",
            "Completed Trade Learning",
            "Symbol Performance Learning",
            "Asian Session Performance Learning",
            "European Session Performance Learning",
            "US Session Performance Learning",
            "Market Condition Performance Learning",
            "BUY and SELL Performance Learning",
            "Confidence Calibration",
            "Risk-Reward Performance Learning",
            "Win and Loss Streak Analysis",
            "Learning Recommendations",
            "Persistent Learning Intelligence",
            "Database Learning Restore",
            "Automatic Restart Learning Recovery",
            "Completed Trade Learning Rebuild",
            "Learning Analytics Intelligence",
            "Confidence Calibration Analytics",
            "Symbol Performance Analytics",
            "Asian Session Performance Analytics",
            "European Session Performance Analytics",
            "US Session Performance Analytics",
            "Market Condition Performance Analytics",
            "BUY and SELL Performance Analytics",
            "Risk-Reward Performance Analytics",
            "Win and Loss Streak Analytics",
            "Learning Health Score",
            "Confidence Guardrail Intelligence",
            "Completed-Trade Confidence Calibration",
            "Symbol Confidence Guardrail",
            "Session Confidence Guardrail",
            "Market Condition Confidence Guardrail",
            "BUY and SELL Confidence Guardrail",
            "Minimum 80 Percent Signal Enforcement",
        ],

        # Version 49 high-quality signal publication control
        "high_quality_signal_publication_enabled": True,
        "quality_over_quantity_enabled": True,
        "preferred_daily_signal_target": 5,
        "maximum_daily_published_signals": 10,
        "duplicate_signal_cooldown_hours": 4,
        "one_active_signal_per_symbol_timeframe": True,
        "high_quality_signal_api_prefix": "/signals/quality",
        "high_quality_signal_endpoints": [
            "GET /signals/quality/",
            "GET /signals/quality/status",
            "POST /signals/quality/create",
        ],

        # Version 48 deployment preparation
        "deployment_preparation_enabled": True,
        "deployment_validation_enabled": True,
        "production_environment_validation_enabled": True,
        "https_validation_enabled": True,
        "cors_validation_enabled": True,
        "production_database_validation_enabled": True,
        "deployment_validation_is_read_only": True,
        "deployment_api_prefix": "/deployment",
        "deployment_endpoints": [
            "GET /deployment/",
            "GET /deployment/status",
            "POST /deployment/validate",
        ],
        "required_production_rules": [
            "APP_ENV=production",
            "DEBUG=false",
            "EXPOSE_DEVELOPMENT_TOKENS=false",
            "BROKER_EXECUTION_ENABLED=false",
            "HTTPS frontend and backend URLs",
            "No wildcard CORS",
            "Production database required",
            "Sensitive request logging disabled",
        ],

        # Version 47 final security and performance testing
        "production_readiness_audit_enabled": True,
        "final_security_verification_enabled": True,
        "final_performance_verification_enabled": True,
        "database_health_audit_enabled": True,
        "database_index_verification_enabled": True,
        "signal_guardrail_audit_enabled": True,
        "readiness_audit_is_read_only": True,
        "readiness_api_prefix": "/readiness",
        "readiness_endpoints": [
            "GET /readiness/",
            "GET /readiness/status",
            "POST /readiness/audit",
        ],
        "expected_alembic_head": (
            "v46_application_event_logs"
        ),

        # Version 46 production logging and monitoring
        "production_logging_enabled": True,
        "structured_application_logs_enabled": True,
        "request_monitoring_enabled": True,
        "request_id_header": "X-Request-ID",
        "response_time_header": "X-Response-Time-Ms",
        "slow_request_detection_enabled": True,
        "monitoring_health_checks_enabled": True,
        "sensitive_data_redaction_enabled": True,
        "client_ip_hashing_enabled": True,
        "request_body_logging_enabled": False,
        "authorization_header_logging_enabled": False,
        "cookie_header_logging_enabled": False,
        "application_event_log_table": "application_event_logs",
        "monitoring_api_prefix": "/monitoring",
        "monitoring_endpoints": [
            "GET /monitoring/",
            "GET /monitoring/summary",
            "GET /monitoring/events",
            "GET /monitoring/events/{event_uid}",
            "GET /monitoring/slow-requests",
            "GET /monitoring/health",
            "POST /monitoring/prune",
        ],

        # Version 45 background processing
        "background_processing_enabled": True,
        "background_worker_enabled": True,
        "persistent_background_queue_enabled": True,
        "background_worker_heartbeat_enabled": True,
        "background_job_retry_enabled": True,
        "stalled_background_job_recovery_enabled": True,
        "background_job_database_table": "background_jobs",
        "background_job_api_prefix": "/background-jobs",
        "supported_background_job_types": [
            "MARKET_REFRESH",
            "SIGNAL_GENERATION",
            "SIGNAL_EXPIRY",
            "LEARNING_REFRESH",
        ],
        "background_job_endpoints": [
            "GET /background-jobs/",
            "GET /background-jobs/list",
            "GET /background-jobs/{job_uid}",
            "POST /background-jobs/create",
            "POST /background-jobs/{job_uid}/cancel",
            "POST /background-jobs/{job_uid}/requeue",
            "POST /background-jobs/process-one",
        ],

        # Version 44 signal performance
        "signal_performance_tracking_enabled": True,
        "signal_win_rate_enabled": True,
        "signal_symbol_performance_enabled": True,
        "signal_timeframe_performance_enabled": True,
        "signal_recent_history_enabled": True,
        "learning_minimum_completed_trades": 20,
        "learning_uses_completed_trades_only": True,
        "signal_performance_api_prefix": "/signals/performance",
        "signal_performance_endpoints": [
            "GET /signals/performance/",
            "GET /signals/performance/overview",
            "GET /signals/performance/overall",
            "GET /signals/performance/by-symbol",
            "GET /signals/performance/by-timeframe",
            "GET /signals/performance/recent",
        ],

        # Version 43 persistent trading signals
        "persistent_trading_signal_storage_enabled": True,
        "trading_signal_api_enabled": True,
        "trading_signal_database_table": "trading_signals",
        "trading_signal_quality_enforcement_enabled": True,
        "minimum_signal_confidence": 80,
        "minimum_signal_confirmations": 3,
        "minimum_signal_risk_reward": 1.5,
        "signal_result_tracking_enabled": True,
        "signal_status_management_enabled": True,
        "broker_execution_enabled": False,
        "signal_api_prefix": "/signals",
        "signal_api_endpoints": [
            "GET /signals/",
            "GET /signals/list",
            "GET /signals/{signal_uid}",
            "POST /signals/create",
            "POST /signals/{signal_uid}/complete",
            "POST /signals/{signal_uid}/cancel",
            "POST /signals/{signal_uid}/expire",
        ],

        # Version 42 admin dashboard
        "admin_dashboard_enabled": True,
        "admin_dashboard_permission_protected": True,
        "admin_dashboard_user_statistics_enabled": True,
        "admin_dashboard_session_statistics_enabled": True,
        "admin_dashboard_security_metrics_enabled": True,
        "admin_dashboard_role_statistics_enabled": True,
        "admin_dashboard_recent_events_enabled": True,
        "admin_dashboard_sensitive_secrets_exposed": False,
        "admin_dashboard_api_prefix": "/admin/dashboard",
        "admin_dashboard_endpoints": [
            "GET /admin/dashboard/",
            "GET /admin/dashboard/overview",
            "GET /admin/dashboard/users",
            "GET /admin/dashboard/sessions",
            "GET /admin/dashboard/security",
            "GET /admin/dashboard/roles",
            "GET /admin/dashboard/account-tokens",
            "GET /admin/dashboard/recent-events",
        ],

        # Version 41 roles and permissions
        "roles_and_permissions_enabled": True,
        "role_based_access_control_enabled": True,
        "owner_role_protected": True,
        "default_roles_seeded": True,
        "default_user_role_on_approval": True,
        "permission_route_guards_enabled": True,
        "role_assignment_tracking_enabled": True,
        "role_revocation_tracking_enabled": True,
        "role_api_prefix": "/roles",

        # Version 40 real email delivery
        "smtp_email_delivery_enabled": True,
        "verification_email_delivery_enabled": True,
        "password_reset_email_delivery_enabled": True,

        # Version 39 account recovery security
        "email_verification_enabled": True,
        "password_reset_enabled": True,
        "single_use_account_tokens_enabled": True,
        "account_token_database_hashing_enabled": True,
        "raw_account_token_storage_enabled": False,
        "email_verification_token_lifetime_hours": 24,
        "password_reset_token_lifetime_minutes": 30,
        "password_reset_revokes_sessions": True,
        "password_reset_revokes_refresh_tokens": True,
        "password_reset_revokes_action_tokens": True,
        "email_delivery_connected": True,

        # Version 38 refresh-token security
        "refresh_tokens_enabled": True,
        "refresh_token_rotation_enabled": True,
        "refresh_token_reuse_detection_enabled": True,
        "refresh_token_family_revocation_enabled": True,
        "refresh_token_database_hashing_enabled": True,
        "raw_refresh_token_storage_enabled": False,
        "refresh_token_default_lifetime_days": 30,
        "logout_revokes_refresh_tokens": True,
        "password_change_revokes_refresh_tokens": True,
        "blocked_account_revokes_refresh_tokens": True,

        # Version 37 secure session management
        "database_backed_sessions_enabled": True,
        "individual_session_revocation_enabled": True,
        "secure_logout_enabled": True,
        "revoke_all_devices_enabled": True,
        "session_expiry_validation_enabled": True,
        "session_activity_tracking_enabled": True,
        "session_ip_tracking_enabled": True,
        "session_user_agent_tracking_enabled": True,
        "hashed_jwt_identifier_storage_enabled": True,
        "raw_jwt_storage_enabled": False,
        "password_change_revokes_sessions": True,
        "blocked_account_revokes_sessions": True,

        # Version 36 API protection
        "security_headers_enabled": True,
        "request_id_tracking_enabled": True,
        "request_body_limit_enabled": True,
        "maximum_request_body_bytes": 2097152,
        "request_timing_enabled": True,
        "api_rate_limiting_enabled": True,
        "login_rate_limit_per_minute": 10,
        "registration_rate_limit_per_5_minutes": 5,
        "password_change_rate_limit_per_5_minutes": 5,
        "admin_rate_limit_per_minute": 60,
        "general_api_rate_limit_per_minute": 120,
        "hardened_cors_enabled": True,

        # Version 35 security audit logs
        "security_audit_logging_enabled": True,
        "authentication_event_audit_enabled": True,
        "owner_action_audit_enabled": True,
        "audit_log_filtering_enabled": True,
        "audit_log_summary_enabled": True,
        "sensitive_value_redaction_enabled": True,

        # Version 34 login protection
        "failed_login_tracking_enabled": True,
        "temporary_login_lockout_enabled": True,
        "maximum_failed_login_attempts": 5,
        "login_lockout_minutes": 15,
        "owner_manual_unlock_enabled": True,
        "last_successful_login_tracking_enabled": True,

        # Version 33 account security
        "password_change_enabled": True,
        "password_versioning_enabled": True,
        "old_token_revocation_enabled": True,
        "forced_relogin_after_password_change": True,

        # Version 32 owner-controlled access
        "owner_approval_required": True,
        "new_accounts_default_to_pending": True,
        "approved_users_only": True,
        "owner_user_management_enabled": True,
        "plans_enabled": False,
        "subscriptions_enabled": False,
        "payments_enabled": False,

        # General platform features
        "timeframe_win_rate_enabled": False,
        "dashboard_summary_enabled": True,
        "controlled_learning_enabled": True,
        "decision_intelligence_enabled": True,
        "market_context_enabled": True,
        "context_aware_decision_enabled": True,
        "institutional_smc_enabled": True,
        "ai_confluence_enabled": True,
        "multi_timeframe_intelligence_enabled": True,
        "dynamic_confidence_enabled": True,
        "signal_ranking_enabled": True,
        "master_signal_pipeline_enabled": True,
        "unified_engine_orchestration_enabled": True,

        # Automated market pipeline
        "automated_market_pipeline_enabled": True,
        "automatic_market_data_retrieval_enabled": True,
        "ohlcv_validation_enabled": True,
        "invalid_candle_filtering_enabled": True,

        # Automated multi-timeframe pipeline
        "automated_multi_timeframe_pipeline_enabled": True,
        "automatic_multi_timeframe_collection_enabled": True,
        "multi_timeframe_validation_enabled": True,
        "require_all_timeframes_enabled": True,

        # Version 21 market cache
        "market_data_cache_enabled": True,
        "market_cache_type": "in_memory",
        "timeframe_based_cache_expiration_enabled": True,
        "expired_cache_cleanup_enabled": True,
        "cache_statistics_enabled": True,
        "cache_entry_monitoring_enabled": True,
        "cache_symbol_clearing_enabled": True,
        "full_cache_clearing_enabled": True,

        # Version 21 smart request manager
        "smart_market_request_manager_enabled": True,
        "cache_first_market_requests_enabled": True,
        "duplicate_provider_request_prevention_enabled": True,
        "provider_request_throttling_enabled": True,
        "automatic_provider_retry_enabled": True,
        "rate_limit_detection_enabled": True,
        "rate_limit_protection_enabled": True,
        "stale_cache_fallback_enabled": True,
        "force_market_refresh_supported": True,

        # Version 21 automatic cache refresh
        "automatic_cache_refresh_enabled": True,
        "cache_refresh_background_service_enabled": True,
        "cache_refresh_subscription_management_enabled": True,
        "cache_refresh_manual_cycle_enabled": True,
        "cache_refresh_duplicate_prevention_enabled": True,
        "cache_refresh_check_interval_seconds": 60,
        "cache_refresh_before_expiry_seconds": 60,

        # Version 22 market session intelligence
        "market_session_intelligence_enabled": True,
        "asian_session_detection_enabled": True,
        "european_session_detection_enabled": True,
        "us_session_detection_enabled": True,
        "market_session_overlap_detection_enabled": True,
        "session_strength_scoring_enabled": True,
        "session_liquidity_scoring_enabled": True,
        "session_volatility_scoring_enabled": True,
        "symbol_session_preference_enabled": True,
        "session_confidence_adjustment_enabled": True,
        "maximum_session_confidence_boost": 6.0,
        "maximum_session_confidence_reduction": -5.0,

        # Version 23 economic news intelligence
        "economic_news_intelligence_enabled": True,
        "economic_calendar_enabled": True,
        "manual_news_event_registration_enabled": True,
        "live_economic_calendar_provider_connected": False,
        "currency_specific_news_filtering_enabled": True,
        "high_impact_news_detection_enabled": True,
        "medium_impact_news_detection_enabled": True,
        "low_impact_news_detection_enabled": True,
        "economic_news_risk_scoring_enabled": True,
        "economic_news_blackout_enabled": True,
        "economic_news_confidence_adjustment_enabled": True,
        "economic_news_signal_integration_enabled": True,
        "economic_news_approval_required": True,
        "high_impact_news_blocks_signal": True,
        "active_news_blackout_blocks_signal": True,
        "minimum_news_adjusted_confidence": 80.0,
        "high_impact_blackout_minutes_before": 30,
        "high_impact_blackout_minutes_after": 30,
        "medium_impact_blackout_minutes_before": 15,
        "medium_impact_blackout_minutes_after": 15,
        "maximum_news_confidence_reduction": -35.0,


        # Version 24 fundamental analysis intelligence
        "fundamental_analysis_intelligence_enabled": True,
        "manual_fundamental_data_registration_enabled": True,
        "external_fundamental_provider_connected": False,
        "currency_fundamental_scoring_enabled": True,
        "interest_rate_analysis_enabled": True,
        "central_bank_policy_bias_enabled": True,
        "inflation_analysis_enabled": True,
        "gdp_growth_analysis_enabled": True,
        "pmi_analysis_enabled": True,
        "employment_analysis_enabled": True,
        "consumer_confidence_analysis_enabled": True,
        "trade_balance_analysis_enabled": True,
        "political_risk_penalty_enabled": True,
        "recession_risk_penalty_enabled": True,
        "currency_strength_comparison_enabled": True,
        "fundamental_confidence_adjustment_enabled": True,
        "fundamental_signal_integration_enabled": True,
        "market_regime_intelligence_enabled": True,
        "market_regime_confidence_adjustment_enabled": True,
        "market_regime_signal_integration_enabled": True,
        "symbol_winrate_intelligence_enabled": True,
        "symbol_confidence_learning_enabled": True,

        # Version 27 AI self-learning intelligence
        "learning_intelligence_enabled": True,
        "completed_trade_learning_enabled": True,
        "symbol_performance_learning_enabled": True,
        "session_performance_learning_enabled": True,
        "asian_session_performance_learning_enabled": True,
        "european_session_performance_learning_enabled": True,
        "us_session_performance_learning_enabled": True,
        "timeframe_performance_learning_enabled": False,
        "market_condition_performance_learning_enabled": True,
        "direction_performance_learning_enabled": True,
        "confidence_calibration_enabled": True,
        "risk_reward_performance_learning_enabled": True,
        "learning_streak_analysis_enabled": True,
        "learning_recommendations_enabled": True,
        "minimum_completed_trades_for_v27_learning": 20,
        "maximum_v27_confidence_adjustment": 4.0,

        # Version 28 persistent learning intelligence
        "learning_persistence_enabled": True,
        "database_learning_restore_enabled": True,
        "automatic_restart_learning_recovery_enabled": True,
        "completed_trade_learning_rebuild_enabled": True,
        "persistent_symbol_performance_enabled": True,
        "persistent_session_performance_enabled": True,
        "persistent_market_condition_performance_enabled": True,
        "persistent_direction_performance_enabled": True,
        "persistent_confidence_calibration_enabled": True,
        "persistent_risk_reward_learning_enabled": True,
        "persistent_streak_restoration_enabled": True,
        "timeframe_performance_learning_enabled_v28": False,

        # Version 29 learning analytics and calibration
        "learning_analytics_enabled": True,
        "confidence_calibration_analytics_enabled": True,
        "symbol_performance_analytics_enabled": True,
        "session_performance_analytics_enabled": True,
        "asian_session_analytics_enabled": True,
        "european_session_analytics_enabled": True,
        "us_session_analytics_enabled": True,
        "market_condition_analytics_enabled": True,
        "direction_performance_analytics_enabled": True,
        "risk_reward_performance_analytics_enabled": True,
        "win_loss_streak_analytics_enabled": True,
        "learning_health_score_enabled": True,
        "timeframe_performance_analytics_enabled": False,
        "strategy_optimization_enabled": False,
        "strategy_ranking_enabled": False,
        "maximum_v29_confidence_adjustment": 4.0,

        # Version 30 confidence guardrail intelligence
        "confidence_guardrail_enabled": True,
        "completed_trade_confidence_calibration_enabled": True,
        "symbol_confidence_guardrail_enabled": True,
        "session_confidence_guardrail_enabled": True,
        "market_condition_confidence_guardrail_enabled": True,
        "direction_confidence_guardrail_enabled": True,
        "minimum_completed_trades_v30": 20,
        "maximum_confidence_adjustment_v30": 4.0,
        "minimum_signal_confidence_v30": 80.0,
        "timeframe_performance_learning_enabled_v30": False,
        "strategy_optimization_enabled_v30": False,
        "strategy_ranking_enabled_v30": False,
        "signal_history_v30_enabled": True,
        "completed_trade_auto_registration_enabled": True,
        "cancelled_trade_learning_enabled": True,
        "duplicate_learning_prevention_enabled": True,
        "persistent_learning_registration_enabled": True,
        "fundamental_analysis_approval_required": True,
        "fundamental_direction_alignment_required": True,
        "minimum_fundamental_confidence": 60.0,
        "minimum_fundamental_adjusted_confidence": 80.0,
        "maximum_fundamental_confidence_boost": 8.0,
        "maximum_fundamental_confidence_reduction": -15.0,
        "fundamental_data_stale_hours": 168,

        # Request-manager settings
        "minimum_provider_request_interval_seconds": 1.0,
        "maximum_provider_retries": 2,
        "provider_retry_delay_seconds": 2.0,

        # Cache duration settings
        "market_cache_duration_seconds": {
            "M5": 300,
            "M15": 900,
            "M30": 1800,
            "H1": 3600,
            "H4": 14400,
            "D1": 86400,
            "W1": 604800,
            "MN": 2592000,
        },

        # Signal safety and ranking
        "confidence_inflation_prevention_enabled": True,
        "approved_signals_rank_first": True,
        "automatic_wait_decision_enabled": True,

        # Learning limits
        "minimum_completed_trades_for_learning": 20,
        "maximum_confidence_increase": 4.0,
        "maximum_confidence_decrease": -4.0,

        # Decision requirements
        "minimum_decision_confidence": 80.0,
        "minimum_decision_confirmations": 3,
        "minimum_final_confidence": 80.0,
        "minimum_total_confirmations": 3,

        # Confluence and institutional requirements
        "minimum_confluence_score": 75.0,
        "minimum_institutional_score": 70.0,
        "minimum_institutional_confirmations": 3,
        "minimum_risk_reward_ratio": 1.5,

        # Multi-timeframe intelligence requirements
        "minimum_multi_timeframe_alignment_score": 75.0,
        "minimum_higher_timeframe_score": 70.0,
        "minimum_aligned_timeframes": 3,

        # Dynamic-confidence requirements
        "minimum_dynamic_confidence": 80.0,
        "minimum_signal_ranking_score": 75.0,
        "maximum_dynamic_confidence": 98.0,
        "maximum_confidence_increase_v18": 8.0,

        # Master-pipeline requirements
        "minimum_master_pipeline_confidence": 80.0,
        "minimum_master_pipeline_ranking_score": 75.0,
        "minimum_master_pipeline_confirmations": 3,
        "minimum_master_pipeline_risk_reward_ratio": 1.5,
        "minimum_master_pipeline_direction_alignment": 75.0,

        # Market-data requirements
        "minimum_market_candles": 50,

        # Context blocking rules
        "high_risk_context_blocks_signal": True,
        "weak_context_quality_blocks_signal": True,
        "unsupported_context_blocks_signal": True,

        # Institutional blocking rules
        "weak_institutional_setup_blocks_signal": True,
        "institutional_direction_mismatch_blocks_signal": True,

        # Required engine approvals
        "context_approval_required": True,
        "institutional_approval_required": True,
        "ai_confluence_approval_required": True,
        "multi_timeframe_approval_required": True,
        "dynamic_confidence_approval_required": True,

        # Direction and risk requirements
        "direction_alignment_required": True,
        "risk_management_required": True,
        "higher_timeframe_alignment_required": True,
        "execution_timeframe_confirmation_required": True,

        # Signal-blocking rules
        "hierarchy_conflict_blocks_signal": True,
        "high_risk_environment_blocks_signal": True,
        "weak_signal_quality_blocks_signal": True,
        "engine_direction_conflict_blocks_signal": True,
        "all_master_pipeline_approvals_required": True,

        # Market-data blocking rules
        "empty_market_data_blocks_analysis": True,
        "unsupported_timeframe_blocks_analysis": True,
        "invalid_market_candles_are_removed": True,

        # Market sessions
        "market_session_names": [
            "ASIAN",
            "EUROPEAN",
            "US",
        ],
        "market_session_timezone": "Asia/Kuala_Lumpur",
        "market_session_windows_myt": {
            "ASIAN": "07:00-16:00",
            "EUROPEAN": "15:00-00:00",
            "US": "20:00-05:00",
        },

        # Version 23 supported economic-news currencies
        "supported_economic_news_currencies": [
            "AUD",
            "CAD",
            "CHF",
            "EUR",
            "GBP",
            "JPY",
            "NZD",
            "USD",
        ],

        "supported_economic_news_impacts": [
            "LOW",
            "MEDIUM",
            "HIGH",
        ],

        "supported_economic_news_categories": [
            "INTEREST_RATE_DECISION",
            "CENTRAL_BANK_STATEMENT",
            "CENTRAL_BANK_SPEECH",
            "NON_FARM_PAYROLLS",
            "INFLATION",
            "PRODUCER_INFLATION",
            "GDP",
            "PMI",
            "RETAIL_SALES",
            "UNEMPLOYMENT",
            "CONSUMER_CONFIDENCE",
            "TRADE_BALANCE",
            "OTHER",
        ],


        # Version 24 supported fundamental-analysis currencies
        "supported_fundamental_currencies": [
            "AUD",
            "CAD",
            "CHF",
            "EUR",
            "GBP",
            "JPY",
            "NZD",
            "USD",
        ],

        "supported_fundamental_biases": [
            "STRONGLY_BEARISH",
            "BEARISH",
            "NEUTRAL",
            "BULLISH",
            "STRONGLY_BULLISH",
        ],

        # Supported automated market timeframes
        "supported_automated_market_timeframes": [
            "M5",
            "M15",
            "M30",
            "H1",
            "H4",
            "D1",
            "W1",
            "MN",
        ],

        # Provider timeframe mapping
        "provider_timeframe_mapping": {
            "M5": "5min",
            "M15": "15min",
            "M30": "30min",
            "H1": "1h",
            "H4": "4h",
            "D1": "1day",
            "W1": "1week",
            "MN": "1month",
        },

        # Default automated multi-timeframe package
        "default_multi_timeframes": [
            "M15",
            "M30",
            "H1",
            "H4",
            "D1",
        ],

        # Version 30 signal history and completed-trade learning endpoints
        "signal_history_endpoints": [
            "GET /history/",
            "GET /history/test",
            "GET /history/learning-status",
            "GET /history/statistics",
            "GET /history/active",
            "GET /history/list",
            "GET /history/all",
            "GET /history/{signal_id}",
            "POST /history/update-price",
            "POST /history/{signal_id}/cancel",
            "POST /history/{signal_id}/register-learning",
        ],

        # Version 21 API endpoints
        "market_cache_endpoints": [
            "GET /cache/",
            "GET /cache/test",
            "GET /cache/status",
            "GET /cache/stats",
            "GET /cache/request-stats",
            "GET /cache/entries",
            "GET /cache/market/{symbol}",
            "DELETE /cache/expired",
            "DELETE /cache/symbol/{symbol}",
            "DELETE /cache/all",
            "POST /cache/reset-request-stats",
        ],

        "cache_refresh_endpoints": [
            "GET /cache-refresh/",
            "GET /cache-refresh/test",
            "GET /cache-refresh/status",
            "GET /cache-refresh/subscriptions",
            "POST /cache-refresh/subscriptions",
            "DELETE /cache-refresh/subscriptions",
            (
                "DELETE /cache-refresh/"
                "subscriptions/{symbol}/{timeframe}"
            ),
            (
                "DELETE /cache-refresh/"
                "subscriptions/symbol/{symbol}"
            ),
            (
                "PATCH /cache-refresh/"
                "subscriptions/{symbol}/{timeframe}/enable"
            ),
            (
                "PATCH /cache-refresh/"
                "subscriptions/{symbol}/{timeframe}/disable"
            ),
            "POST /cache-refresh/cycle",
            (
                "POST /cache-refresh/"
                "refresh/{symbol}/{timeframe}"
            ),
            "POST /cache-refresh/service/start",
            "POST /cache-refresh/service/stop",
        ],

        # Version 22 market session API endpoints
        "market_session_endpoints": [
            "GET /market-session/",
            "GET /market-session/test",
            "GET /market-session/configuration",
            "GET /market-session/active",
            "GET /market-session/analyze/{symbol}",
            "GET /market-session/confidence/{symbol}",
        ],

        # Version 23 economic news API endpoints
        "economic_news_endpoints": [
            "GET /economic-news/",
            "GET /economic-news/test",
            "GET /economic-news/configuration",
            "GET /economic-news/calendar",
            "GET /economic-news/upcoming",
            "GET /economic-news/high-impact",
            "GET /economic-news/analyze/{symbol}",
            "GET /economic-news/confidence/{symbol}",
            "GET /economic-news/server-time",
        ],


        # Version 24 fundamental analysis API endpoints
        "fundamental_analysis_endpoints": [
            "GET /fundamental-analysis/",
            "GET /fundamental-analysis/test",
            "GET /fundamental-analysis/configuration",
            "GET /fundamental-analysis/currencies",
            "GET /fundamental-analysis/currency/{currency}",
            "GET /fundamental-analysis/data/{currency}",
            "GET /fundamental-analysis/compare/{base}/{quote}",
            "GET /fundamental-analysis/symbol/{symbol}",
        ],

        # Version 27 learning intelligence API endpoints
        "learning_intelligence_endpoints": [
            "GET /learning-intelligence/",
            "GET /learning-intelligence/health",
            "POST /learning-intelligence/completed-trades",
            "POST /learning-intelligence/evaluate",
            "GET /learning-intelligence/summary",
            "DELETE /learning-intelligence/reset",
        ],

        # Version 28 learning persistence API endpoints
        "learning_persistence_endpoints": [
            "GET /learning-persistence/",
            "GET /learning-persistence/health",
            "GET /learning-persistence/status",
            "POST /learning-persistence/rebuild",
            "POST /learning-persistence/sync",
        ],

        # Version 29 learning analytics API endpoints
        "learning_analytics_endpoints": [
            "GET /learning-analytics/",
            "GET /learning-analytics/health",
            "GET /learning-analytics/summary",
            "GET /learning-analytics/symbols",
            "GET /learning-analytics/sessions",
            "GET /learning-analytics/market-conditions",
            "GET /learning-analytics/directions",
            "GET /learning-analytics/confidence-calibration",
            "GET /learning-analytics/risk-reward",
            "GET /learning-analytics/streaks",
            "GET /learning-analytics/health-score",
        ],

        # Version 30 confidence guardrail API endpoints
        "confidence_guardrail_endpoints": [
            "GET /confidence-guardrail/",
            "GET /confidence-guardrail/health",
            "GET /confidence-guardrail/rules",
            "GET /confidence-guardrail/integration-status",
            "POST /confidence-guardrail/evaluate",
            "POST /confidence-guardrail/apply-to-signal",
            "POST /confidence-guardrail/apply-complete",
            "POST /confidence-guardrail/apply-to-pipeline",
        ],

        # Version 39 account recovery endpoints
        "account_recovery_endpoints": [
            "POST /auth/request-email-verification",
            "POST /auth/verify-email",
            "POST /auth/forgot-password",
            "POST /auth/reset-password",
        ],

        # Version 38 token-renewal endpoints
        "refresh_token_endpoints": [
            "POST /auth/refresh",
        ],

        # Version 37 session-management endpoints
        "session_management_endpoints": [
            "POST /auth/logout",
            "GET /auth/sessions",
            "POST /auth/sessions/{session_id}/revoke",
            "POST /auth/sessions/revoke-all",
        ],

        # Version 36 API protection behavior
        "api_protection_responses": [
            "HTTP 413 Request Entity Too Large",
            "HTTP 429 Too Many Requests",
            "X-Request-ID response header",
            "X-Process-Time-Ms response header",
            "X-RateLimit-* response headers",
        ],

        # Version 35 security audit endpoints
        "security_audit_endpoints": [
            "GET /admin/audit-logs/",
            "GET /admin/audit-logs",
            "GET /admin/audit-logs/summary",
            "GET /admin/audit-logs/event-types",
            "GET /admin/audit-logs/{log_id}",
        ],

        # Version 34 login-protection endpoints
        "login_protection_endpoints": [
            "POST /admin/users/{user_id}/unlock",
        ],

        # Version 33 authentication-security endpoints
        "account_security_endpoints": [
            "POST /auth/change-password",
        ],

        # Version 32 owner user-management endpoints
        "owner_user_management_endpoints": [
            "GET /admin/users/",
            "GET /admin/users",
            "GET /admin/users/{user_id}",
            "POST /admin/users/{user_id}/approve",
            "POST /admin/users/{user_id}/reject",
            "POST /admin/users/{user_id}/suspend",
            "POST /admin/users/{user_id}/pending",
        ],

        # Safety controls
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
        "automatic_order_placement_enabled": False,

        "important_notice": (
            "Blue-Trading-AI provides market analysis, "
            "confidence scoring and trading signals only. "
            "It does not connect to trading accounts or "
            "execute trades."
        ),
    }

__all__ = [
    "APP_VERSION",
    "app",
    "home",
    "lifespan",
]