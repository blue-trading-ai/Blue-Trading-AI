from app.services.trade_history_service import (
    cancel_trade,
    generate_signal_id,
    get_active_trades,
    get_trade_by_signal_id,
    get_trade_history,
    get_trade_statistics,
    save_approved_signal,
    update_active_trades,
)

from app.services.performance_analytics_service import (
    get_performance_analytics,
)

from app.services.dashboard_service import (
    get_dashboard_summary,
)

from app.services.learning_adjustment_service import (
    get_learning_adjustment,
)

from app.services.decision_intelligence_service import (
    evaluate_trade_decision,
)

from app.services.market_context_service import (
    analyze_market_context,
)

from app.services.context_aware_decision_service import (
    evaluate_context_aware_decision,
)

from app.services.institutional_smc_service import (
    evaluate_institutional_smc,
)

from app.services.ai_confluence_service import (
    evaluate_ai_confluence,
)

from app.services.multi_timeframe_intelligence_service import (
    evaluate_multi_timeframe_intelligence,
)

from app.services.dynamic_confidence_service import (
    evaluate_dynamic_confidence,
    rank_trading_signals,
)

from app.services.master_signal_pipeline_service import (
    evaluate_master_signal_pipeline,
)

from app.services.automated_market_pipeline_service import (
    prepare_automated_market_data,
)

from app.services.multi_timeframe_pipeline_service import (
    DEFAULT_TIMEFRAMES,
    prepare_multi_timeframe_market_data,
)

from app.services.market_cache_service import (
    TIMEFRAME_CACHE_SECONDS,
    MarketCacheEntry,
    MarketDataCache,
    build_cache_key,
    cache_market_data,
    clear_market_cache,
    clear_symbol_cache,
    get_cached_market_data,
    get_market_cache_stats,
    list_market_cache_entries,
    market_data_cache,
    normalize_symbol,
    normalize_timeframe,
    remove_expired_market_cache,
)

from app.services.market_request_manager_service import (
    PROVIDER_TIMEFRAME_MAP,
    MarketRequestManager,
    get_managed_market_data,
    get_market_request_statistics,
    market_request_manager,
    reset_market_request_statistics,
)

from app.services.market_cache_refresh_service import (
    DEFAULT_REFRESH_BEFORE_EXPIRY_SECONDS,
    DEFAULT_REFRESH_CHECK_INTERVAL_SECONDS,
    MarketCacheRefreshService,
    RefreshSubscription,
    get_market_cache_refresh_status,
    list_market_cache_refresh_subscriptions,
    market_cache_refresh_service,
    register_market_cache_refresh,
    run_market_cache_refresh_cycle,
    start_market_cache_refresh_service,
    stop_market_cache_refresh_service,
    unregister_market_cache_refresh,
)

from app.services.market_session_service import (
    DEFAULT_SESSION_PREFERENCES,
    MARKET_TIMEZONE,
    SESSION_WINDOWS,
    SYMBOL_SESSION_PREFERENCES,
    MarketSessionIntelligence,
    MarketSessionState,
    analyze_market_session,
    apply_market_session_confidence,
    get_current_market_sessions,
    get_market_session_configuration,
    market_session_intelligence,
)

from app.services.market_session_integration import (
    integrate_market_session_into_signal,
)

# ===========================
# VERSION 23
# ECONOMIC NEWS INTELLIGENCE
# ===========================

from app.services.economic_news_service import (
    EconomicNewsEvent,
    EconomicNewsIntelligence,
    analyze_economic_news,
    apply_economic_news_confidence,
    clear_economic_news_events,
    economic_news_intelligence,
    get_economic_news_calendar,
    get_economic_news_configuration,
    get_high_impact_economic_news,
    get_upcoming_economic_news,
    register_economic_news_event,
    register_economic_news_events,
    remove_economic_news_event,
)

from app.services.economic_news_integration import (
    integrate_economic_news_into_signal,
)

# ===========================
# VERSION 24
# FUNDAMENTAL ANALYSIS INTELLIGENCE
# ===========================

from app.services.fundamental_analysis_service import (
    FundamentalAnalysisIntelligence,
    FundamentalData,
    analyze_currency_fundamentals,
    analyze_symbol_fundamentals,
    apply_fundamental_confidence,
    clear_fundamental_data,
    compare_currency_fundamentals,
    fundamental_analysis_intelligence,
    get_fundamental_analysis_configuration,
    get_fundamental_data,
    list_fundamental_data,
    register_fundamental_data,
    register_fundamental_data_many,
    remove_fundamental_data,
)

from app.services.fundamental_analysis_integration import (
    integrate_fundamental_analysis_into_signal,
)

# ===========================
# VERSION 25
# MARKET REGIME INTELLIGENCE
# ===========================

from app.services.market_regime_service import (
    MarketRegimeIntelligence,
    MarketRegimeResult,
    analyze_market_regime,
    apply_market_regime_confidence,
    get_market_regime_configuration,
    market_regime_intelligence,
)

from app.services.market_regime_integration import (
    evaluate_market_regime_signal_integration,
    integrate_market_regime_into_signal,
)


# ===========================
# VERSION 27
# AI SELF-LEARNING INTELLIGENCE
# ===========================

from app.services.learning_intelligence_service import (
    LearningIntelligenceService,
    LearningRecommendation,
    LearningStatistics,
    LearningTrade,
)

from app.services.learning_intelligence_integration import (
    evaluate_learning_intelligence,
    get_learning_intelligence_service,
    get_learning_summary,
    integrate_learning_intelligence,
    register_completed_trade,
    reset_learning_intelligence_service,
)


# ===========================
# VERSION 28
# PERSISTENT LEARNING INTELLIGENCE
# ===========================

from app.services.learning_persistence_service import (
    calculate_planned_risk_reward,
    determine_session_from_time,
    get_completed_learning_trades,
    get_learning_persistence_status,
    initialise_learning_persistence,
    rebuild_learning_from_database,
    rebuild_learning_from_trades,
    trade_history_to_learning_trade,
)


# ===========================
# VERSION 29
# LEARNING ANALYTICS
# ===========================

from app.services.learning_analytics_service import (
    CategoryPerformance,
    ConfidenceCalibration,
    LearningHealth,
    build_category_performance,
    get_confidence_calibration,
    get_direction_performance,
    get_learning_analytics_summary,
    get_learning_health,
    get_market_condition_performance,
    get_risk_reward_performance,
    get_session_performance,
    get_streak_analysis,
    get_symbol_performance,
)


# ===========================
# VERSION 30
# CONFIDENCE GUARDRAIL
# ===========================

from app.services.confidence_guardrail_service import (
    ConfidenceGuardrailResult,
    GuardrailFactor,
    MAXIMUM_CONFIDENCE_ADJUSTMENT,
    MINIMUM_COMPLETED_TRADES,
    MINIMUM_SIGNAL_CONFIDENCE,
    apply_guardrail_to_signal,
    build_factor,
    calculate_guarded_confidence,
    calculate_win_rate_adjustment,
    extract_category_record,
    get_confidence_guardrail_rules,
)

from app.services.confidence_guardrail_integration import (
    apply_complete_confidence_guardrail,
    enforce_guardrail_decision,
    get_confidence_guardrail_integration_status,
    get_current_guardrail_analytics,
    integrate_confidence_guardrail,
    integrate_guardrail_into_pipeline_result,
    normalise_signal_for_guardrail,
)


__all__ = [
    # ===========================
    # Trade history
    # ===========================
    "generate_signal_id",
    "save_approved_signal",
    "get_trade_by_signal_id",
    "get_trade_history",
    "get_active_trades",
    "update_active_trades",
    "cancel_trade",
    "get_trade_statistics",

    # ===========================
    # Analytics and dashboard
    # ===========================
    "get_performance_analytics",
    "get_dashboard_summary",
    "get_learning_adjustment",

    # ===========================
    # Decision intelligence
    # ===========================
    "evaluate_trade_decision",
    "analyze_market_context",
    "evaluate_context_aware_decision",
    "evaluate_institutional_smc",
    "evaluate_ai_confluence",
    "evaluate_multi_timeframe_intelligence",
    "evaluate_dynamic_confidence",
    "rank_trading_signals",

    # ===========================
    # Signal pipelines
    # ===========================
    "evaluate_master_signal_pipeline",
    "prepare_automated_market_data",
    "DEFAULT_TIMEFRAMES",
    "prepare_multi_timeframe_market_data",

    # ===========================
    # Version 21 Market Cache
    # ===========================
    "TIMEFRAME_CACHE_SECONDS",
    "MarketCacheEntry",
    "MarketDataCache",
    "build_cache_key",
    "cache_market_data",
    "clear_market_cache",
    "clear_symbol_cache",
    "get_cached_market_data",
    "get_market_cache_stats",
    "list_market_cache_entries",
    "market_data_cache",
    "normalize_symbol",
    "normalize_timeframe",
    "remove_expired_market_cache",

    # ===========================
    # Version 21 Request Manager
    # ===========================
    "PROVIDER_TIMEFRAME_MAP",
    "MarketRequestManager",
    "get_managed_market_data",
    "get_market_request_statistics",
    "market_request_manager",
    "reset_market_request_statistics",

    # ===========================
    # Version 21 Cache Refresh
    # ===========================
    "DEFAULT_REFRESH_BEFORE_EXPIRY_SECONDS",
    "DEFAULT_REFRESH_CHECK_INTERVAL_SECONDS",
    "MarketCacheRefreshService",
    "RefreshSubscription",
    "get_market_cache_refresh_status",
    "list_market_cache_refresh_subscriptions",
    "market_cache_refresh_service",
    "register_market_cache_refresh",
    "run_market_cache_refresh_cycle",
    "start_market_cache_refresh_service",
    "stop_market_cache_refresh_service",
    "unregister_market_cache_refresh",

    # ===========================
    # Version 22 Market Session
    # ===========================
    "DEFAULT_SESSION_PREFERENCES",
    "MARKET_TIMEZONE",
    "SESSION_WINDOWS",
    "SYMBOL_SESSION_PREFERENCES",
    "MarketSessionIntelligence",
    "MarketSessionState",
    "analyze_market_session",
    "apply_market_session_confidence",
    "get_current_market_sessions",
    "get_market_session_configuration",
    "market_session_intelligence",

    # Version 22 signal integration
    "integrate_market_session_into_signal",

    # ===========================
    # Version 23 Economic News
    # ===========================
    "EconomicNewsEvent",
    "EconomicNewsIntelligence",
    "analyze_economic_news",
    "apply_economic_news_confidence",
    "clear_economic_news_events",
    "economic_news_intelligence",
    "get_economic_news_calendar",
    "get_economic_news_configuration",
    "get_high_impact_economic_news",
    "get_upcoming_economic_news",
    "register_economic_news_event",
    "register_economic_news_events",
    "remove_economic_news_event",

    # Version 23 signal integration
    "integrate_economic_news_into_signal",

    # ===========================
    # Version 24 Fundamental Analysis
    # ===========================
    "FundamentalData",
    "FundamentalAnalysisIntelligence",
    "analyze_currency_fundamentals",
    "analyze_symbol_fundamentals",
    "apply_fundamental_confidence",
    "clear_fundamental_data",
    "compare_currency_fundamentals",
    "fundamental_analysis_intelligence",
    "get_fundamental_analysis_configuration",
    "get_fundamental_data",
    "list_fundamental_data",
    "register_fundamental_data",
    "register_fundamental_data_many",
    "remove_fundamental_data",

    # Version 24 signal integration
    "integrate_fundamental_analysis_into_signal",

    # ===========================
    # Version 25 Market Regime Intelligence
    # ===========================
    "MarketRegimeIntelligence",
    "MarketRegimeResult",
    "analyze_market_regime",
    "apply_market_regime_confidence",
    "get_market_regime_configuration",
    "market_regime_intelligence",

    # Version 25 signal integration
    "integrate_market_regime_into_signal",
    "evaluate_market_regime_signal_integration",

    # ===========================
    # Version 27 Learning Intelligence
    # ===========================
    "LearningIntelligenceService",
    "LearningRecommendation",
    "LearningStatistics",
    "LearningTrade",
    "evaluate_learning_intelligence",
    "get_learning_intelligence_service",
    "get_learning_summary",
    "integrate_learning_intelligence",
    "register_completed_trade",
    "reset_learning_intelligence_service",

    # ===========================
    # Version 28 Persistent Learning
    # ===========================
    "calculate_planned_risk_reward",
    "determine_session_from_time",
    "get_completed_learning_trades",
    "get_learning_persistence_status",
    "initialise_learning_persistence",
    "rebuild_learning_from_database",
    "rebuild_learning_from_trades",
    "trade_history_to_learning_trade",

    # ===========================
    # Version 29 Learning Analytics
    # ===========================
    "CategoryPerformance",
    "ConfidenceCalibration",
    "LearningHealth",
    "build_category_performance",
    "get_confidence_calibration",
    "get_direction_performance",
    "get_learning_analytics_summary",
    "get_learning_health",
    "get_market_condition_performance",
    "get_risk_reward_performance",
    "get_session_performance",
    "get_streak_analysis",
    "get_symbol_performance",

    # ===========================
    # Version 30 Confidence Guardrail
    # ===========================
    "ConfidenceGuardrailResult",
    "GuardrailFactor",
    "MAXIMUM_CONFIDENCE_ADJUSTMENT",
    "MINIMUM_COMPLETED_TRADES",
    "MINIMUM_SIGNAL_CONFIDENCE",
    "apply_guardrail_to_signal",
    "build_factor",
    "calculate_guarded_confidence",
    "calculate_win_rate_adjustment",
    "extract_category_record",
    "get_confidence_guardrail_rules",
    "apply_complete_confidence_guardrail",
    "enforce_guardrail_decision",
    "get_confidence_guardrail_integration_status",
    "get_current_guardrail_analytics",
    "integrate_confidence_guardrail",
    "integrate_guardrail_into_pipeline_result",
    "normalise_signal_for_guardrail",

]