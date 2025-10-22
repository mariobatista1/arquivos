"""
Configurações da aplicação ML
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Carregar arquivo .env explicitamente ANTES de qualquer coisa
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Debug removido - configuração funcionando

class Settings(BaseSettings):
    """Configurações da aplicação"""
    
    # Database - suporte para URL completa ou componentes individuais
    database_url_complete: Optional[str] = Field(default=None, env="DATABASE_URL")
    database_host: str = Field(default="postgres", env="DB_HOST")
    database_port: int = Field(default=5432, env="DB_PORT")
    database_name: str = Field(default="playercore_retain", env="DB_NAME")
    database_user: str = Field(default="postgres", env="DB_USER")
    database_password: str = Field(default="playercore123", env="DB_PASSWORD")
    
    # API
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8001, env="API_PORT")
    api_debug: bool = Field(default=True, env="API_DEBUG")
    
    # ML Models
    models_path: str = Field(default="models/saved", env="MODELS_PATH")
    model_retrain_interval_hours: int = Field(default=24, env="MODEL_RETRAIN_INTERVAL")
    
    # Feature Engineering
    feature_window_days: int = Field(default=90, env="FEATURE_WINDOW_DAYS")
    churn_prediction_days: int = Field(default=30, env="CHURN_PREDICTION_DAYS")
    
    # Segmentation
    top_percentile_threshold: float = Field(default=0.8, env="TOP_PERCENTILE_THRESHOLD")
    
    # Cache
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_ttl_seconds: int = Field(default=3600, env="CACHE_TTL")  # 1 hora
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    model_config = {
        "env_file": Path(__file__).parent.parent.parent / ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",  # Permite campos extras do .env
        "protected_namespaces": ("settings_",),
        "case_sensitive": False
    }
    
    def __init__(self, **kwargs):
        # Forçar carregamento das variáveis de ambiente
        super().__init__(**kwargs)
        
        # Override com valores do environment se estiverem disponíveis
        if os.getenv('DATABASE_URL'):
            object.__setattr__(self, 'database_url_complete', os.getenv('DATABASE_URL'))
        if os.getenv('DB_HOST'):
            object.__setattr__(self, 'database_host', os.getenv('DB_HOST'))
        if os.getenv('DB_USER'):
            object.__setattr__(self, 'database_user', os.getenv('DB_USER'))
        if os.getenv('DB_PASSWORD'):
            object.__setattr__(self, 'database_password', os.getenv('DB_PASSWORD'))
        if os.getenv('DB_NAME'):
            object.__setattr__(self, 'database_name', os.getenv('DB_NAME'))
        if os.getenv('DB_PORT'):
            object.__setattr__(self, 'database_port', int(os.getenv('DB_PORT')))
    
    @property
    def database_url(self) -> str:
        """URL de conexão com o banco de dados"""
        if self.database_url_complete:
            # Substituir postgresql:// por postgresql+asyncpg:// e remover sslmode para asyncpg
            url = self.database_url_complete.replace("postgresql://", "postgresql+asyncpg://", 1)
            # asyncpg não aceita sslmode na URL, SSL será configurado no connect_args
            url = url.replace("?sslmode=require", "").replace("&sslmode=require", "").replace("?sslmode=disable", "").replace("&sslmode=disable", "")
            return url
        else:
            # Escapar a senha se contiver caracteres especiais
            from urllib.parse import quote_plus
            escaped_password = quote_plus(self.database_password)
            return f"postgresql+asyncpg://{self.database_user}:{escaped_password}@{self.database_host}:{self.database_port}/{self.database_name}"
    
    @property
    def database_url_sync(self) -> str:
        """URL de conexão síncrona com o banco de dados"""
        if self.database_url_complete:
            # Substituir postgresql:// por postgresql+psycopg2://
            return self.database_url_complete.replace("postgresql://", "postgresql+psycopg2://", 1)
        else:
            # Escapar a senha se contiver caracteres especiais
            from urllib.parse import quote_plus
            escaped_password = quote_plus(self.database_password)
            return f"postgresql+psycopg2://{self.database_user}:{escaped_password}@{self.database_host}:{self.database_port}/{self.database_name}"

# Instância global das configurações
settings = Settings()

# Configurações específicas para diferentes ambientes
class DevelopmentSettings(Settings):
    """Configurações para desenvolvimento"""
    api_debug: bool = True
    log_level: str = "DEBUG"
    cache_enabled: bool = False

class ProductionSettings(Settings):
    """Configurações para produção"""
    api_debug: bool = False
    log_level: str = "WARNING"
    cache_enabled: bool = True
    model_retrain_interval_hours: int = 12

class TestingSettings(Settings):
    """Configurações para testes"""
    database_name: str = "playercore_retain_test"
    api_debug: bool = True
    log_level: str = "DEBUG"
    cache_enabled: bool = False

def get_settings(environment: Optional[str] = None) -> Settings:
    """
    Retorna as configurações baseadas no ambiente
    """
    env = environment or os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()

# Configurações para algoritmos ML
class MLConfig:
    """Configurações específicas para Machine Learning"""
    
    # Churn Prediction
    CHURN_FEATURES = [
        'days_since_last_deposit',
        'total_deposits',
        'avg_ticket',
        'deposit_frequency',
        'ticket_trend',
        'days_as_player',
        'last_7_days_activity',
        'last_30_days_activity'
    ]
    
    CHURN_MODEL_PARAMS = {
        'n_estimators': 100,
        'max_depth': 10,
        'min_samples_split': 5,
        'min_samples_leaf': 2,
        'random_state': 42
    }
    
    # LTV Prediction
    LTV_FEATURES = [
        'total_deposits',
        'avg_ticket',
        'deposit_frequency',
        'days_as_player',
        'current_balance',
        'segment',
        'payment_method_diversity'
    ]
    
    LTV_MODEL_PARAMS = {
        'n_estimators': 150,
        'max_depth': 12,
        'learning_rate': 0.1,
        'random_state': 42
    }
    
    # Risk Scoring
    RISK_WEIGHTS = {
        'days_since_last_deposit': 0.25,
        'ticket_trend': 0.20,
        'frequency_change': 0.20,
        'total_value_at_risk': 0.15,
        'segment_stability': 0.10,
        'engagement_score': 0.10
    }
    
    # Segmentation
    SEGMENT_CRITERIA = {
        'top_20_min_deposits': 5,
        'top_20_min_value': 1000,
        'high_risk_threshold': 70,
        'medium_risk_threshold': 40
    }

ml_config = MLConfig()