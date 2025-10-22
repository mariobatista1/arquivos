import redis
import pickle
import json
import hashlib
import pandas as pd
import os
from typing import Any, Optional, Dict, List, Callable
from datetime import datetime, timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)

class CacheService:
    """
    Serviço de cache Redis para otimizar consultas ML
    """
    
    def __init__(self, host: Optional[str] = None, port: int = 6379, db: int = 0):
        """Inicializa conexão com Redis"""
        try:
            # Obter host e porta
            redis_host_env = os.getenv('REDIS_HOST', None)
            redis_port_env = os.getenv('REDIS_PORT', None)

            redis_host = host or redis_host_env or 'localhost'
            redis_port = int(redis_port_env) if redis_port_env else port
            redis_password = os.getenv('REDIS_PASSWORD', None)

            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=db,
                password=redis_password,
                decode_responses=False
            )

            # Configurações TTL
            self.ttl_settings = {
                'player_features': 900,
                'dashboard_metrics': 600,
                'churn_predictions': 1800,
                'player_timeline': 3600,
                'aggregated_data': 1800,
                'ml_models': 7200,
                'churn_metrics_data': 900,
                'risk_alerts_data': 600,
                'segmentation_data': 1800,
                'microtendencias_dashboard': 300,
            }

            logger.info(f"💾 CacheService initialized - Redis connected: {self.redis_client.ping()}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis client: {e}")
            raise
    
    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Gera chave única para cache baseada nos parâmetros"""
        # Remove None values to ensure consistent cache keys
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        # Serializar parâmetros de forma determinística
        key_data = json.dumps(clean_kwargs, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:8]
        cache_key = f"{prefix}:{key_hash}"
        
        # CRITICAL DEBUG logging for gateway filtering
        if 'gateway_id' in clean_kwargs and clean_kwargs['gateway_id'] is not None:
            logger.info(f"🔑 [CACHE-KEY-GATEWAY] Cache key generated with GATEWAY FILTER: {cache_key}")
            logger.info(f"🔑 [CACHE-KEY-GATEWAY] Gateway ID in key: {clean_kwargs.get('gateway_id')}")
            logger.info(f"🔑 [CACHE-KEY-GATEWAY] Full key data: {key_data}")
            logger.info(f"🔑 [CACHE-KEY-GATEWAY] Original kwargs: {kwargs}")
            logger.info(f"🔑 [CACHE-KEY-GATEWAY] Clean kwargs: {clean_kwargs}")
        else:
            logger.info(f"🔑 [CACHE-KEY-GLOBAL] Cache key generated WITHOUT gateway filter: {cache_key}")
            logger.info(f"🔑 [CACHE-KEY-GLOBAL] Full key data: {key_data}")
            logger.info(f"🔑 [CACHE-KEY-GLOBAL] Gateway_id in original kwargs: {kwargs.get('gateway_id')}")
        
        return cache_key
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Armazena valor no cache"""
        try:
            if isinstance(value, pd.DataFrame):
                # Serializar DataFrame de forma otimizada para bytes
                serialized = pickle.dumps(value)
            else:
                # Usar pickle para outros objetos
                serialized = pickle.dumps(value)
            
            result = self.redis_client.setex(
                key, 
                ttl or self.ttl_settings.get('default', 300), 
                serialized
            )
            
            if result:
                if 'gateway' in key or 'microtendencias' in key:
                    logger.info(f"💾 [CACHE-SET] Stored data for key: {key} (TTL: {ttl}s)")
                else:
                    logger.debug(f"🔄 Cache SET: {key} (TTL: {ttl}s)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Cache SET error for {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Recupera valor do cache"""
        try:
            cached_data = self.redis_client.get(key)
            if cached_data is None:
                if 'gateway' in key or 'microtendencias' in key:
                    logger.info(f"💾 [CACHE-MISS] No cached data for key: {key}")
                else:
                    logger.debug(f"🚫 Cache MISS: {key}")
                return None
            
            # Deserializar usando pickle (funciona para DataFrames e outros objetos)
            value = pickle.loads(cached_data)
            if 'gateway' in key or 'microtendencias' in key:
                logger.info(f"💾 [CACHE-HIT] Found cached data for key: {key}")
            else:
                logger.debug(f"✅ Cache HIT: {key}")
                
            return value
            
        except Exception as e:
            logger.error(f"❌ Cache GET error for {key}: {e}")
            return None
    
    def get_or_compute(self, cache_type: str, compute_func: Callable, ttl: Optional[int] = None, **kwargs) -> Any:
        """
        Padrão get-or-compute: busca no cache ou executa função
        """
        cache_key = self._generate_cache_key(cache_type, **kwargs)
        
        # Tentar buscar no cache primeiro
        cached_result = self.get(cache_key)
        
        logger.info(f"💾 Cache lookup for {cache_type}: {'HIT' if cached_result is not None else 'MISS'}")
        if cached_result is not None:
            return cached_result
        
        # Se não encontrado, computar resultado
        logger.debug(f"🔄 Computing: {cache_type} with {kwargs}")
        try:
            result = compute_func(**kwargs)
            
            # Armazenar no cache
            cache_ttl = ttl or self.ttl_settings.get(cache_type, 300)
            self.set(cache_key, result, cache_ttl)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Compute function failed for {cache_type}: {e}")
            raise
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Remove chaves que correspondem ao padrão"""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted_count = self.redis_client.delete(*keys)
                logger.info(f"🗑️ Cache invalidated: {deleted_count} keys matching '{pattern}'")
                return deleted_count
            return 0
        except Exception as e:
            logger.error(f"❌ Cache invalidation error for pattern {pattern}: {e}")
            return 0
    
    def invalidate_workspace(self, workspace_id: int) -> int:
        """Remove todos os caches de um workspace específico"""
        patterns = [
            f"player_features:*workspace_id*{workspace_id}*",
            f"dashboard_metrics:*workspace_id*{workspace_id}*",
            f"churn_predictions:*workspace_id*{workspace_id}*",
            f"player_timeline:*workspace_id*{workspace_id}*",
            f"aggregated_data:*workspace_id*{workspace_id}*",
            f"microtendencias_dashboard:*workspace_id*{workspace_id}*",  # Added microtendencias cache pattern
            f"dashboard_summary:*workspace_id*{workspace_id}*",  # Added dashboard summary cache pattern
        ]
        
        total_deleted = 0
        for pattern in patterns:
            total_deleted += self.invalidate_pattern(pattern)
        
        logger.info(f"🧹 Workspace {workspace_id} cache cleared: {total_deleted} keys")
        return total_deleted
    
    def invalidate_gateway_cache(self, workspace_id: int, gateway_id: Optional[int] = None) -> int:
        """Remove caches relacionados a um gateway específico ou todos os gateways"""
        if gateway_id is not None:
            # Invalidar cache específico do gateway
            patterns = [
                f"dashboard_summary:*workspace_id*{workspace_id}*gateway_id*{gateway_id}*",
                f"microtendencias_dashboard:*workspace_id*{workspace_id}*gateway_id*{gateway_id}*",
                f"gateway_performance:*workspace_id*{workspace_id}*gateway_id*{gateway_id}*",
            ]
            logger.info(f"🎯 [CACHE-INVALIDATE] Clearing cache for workspace {workspace_id}, gateway {gateway_id}")
        else:
            # Invalidar todos os caches relacionados a gateways
            patterns = [
                f"dashboard_summary:*workspace_id*{workspace_id}*",
                f"microtendencias_dashboard:*workspace_id*{workspace_id}*",
                f"gateway_performance:*workspace_id*{workspace_id}*",
            ]
            logger.info(f"🧹 [CACHE-INVALIDATE] Clearing ALL gateway caches for workspace {workspace_id}")
        
        total_deleted = 0
        for pattern in patterns:
            deleted = self.invalidate_pattern(pattern)
            total_deleted += deleted
            logger.info(f"🗑️ [CACHE-INVALIDATE] Pattern '{pattern}' cleared {deleted} keys")
        
        logger.info(f"✅ [CACHE-INVALIDATE] Total cleared: {total_deleted} keys")
        return total_deleted
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        try:
            info = self.redis_client.info()
            
            # Contar chaves por tipo
            key_counts = {}
            for cache_type in self.ttl_settings.keys():
                count = len(self.redis_client.keys(f"{cache_type}:*"))
                key_counts[cache_type] = count
            
            return {
                'connected': True,
                'used_memory': info.get('used_memory_human', '0B'),
                'total_keys': info.get('db0', {}).get('keys', 0) if 'db0' in info else 0,
                'key_counts': key_counts,
                'hit_rate': self._calculate_hit_rate(),
                'uptime_seconds': info.get('uptime_in_seconds', 0),
            }
        except Exception as e:
            logger.error(f"❌ Cache stats error: {e}")
            return {'connected': False, 'error': str(e)}
    
    def _calculate_hit_rate(self) -> float:
        """Calcula taxa de hits do cache (se disponível)"""
        try:
            info = self.redis_client.info()
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            
            if hits + misses == 0:
                return 0.0
            
            return hits / (hits + misses)
        except:
            return 0.0
    
    def health_check(self) -> Dict[str, Any]:
        """Verifica saúde do serviço de cache"""
        try:
            # Teste de write/read
            test_key = "health_check_test"
            test_value = {"timestamp": datetime.now().isoformat(), "test": True}
            
            # Teste SET
            set_result = self.redis_client.setex(test_key, 60, pickle.dumps(test_value))
            
            # Teste GET
            get_result = self.redis_client.get(test_key)
            retrieved_value = pickle.loads(get_result) if get_result else None
            
            # Limpar teste
            self.redis_client.delete(test_key)
            
            return {
                'status': 'healthy',
                'redis_connected': True,
                'write_test': set_result is not None,
                'read_test': retrieved_value == test_value,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Cache health check failed: {e}")
            return {
                'status': 'unhealthy',
                'redis_connected': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def clear_all_cache(self) -> int:
        """Limpa TODOS os dados do cache"""
        try:
            logger.warning("🗑️ [CACHE-FLUSH] Clearing ALL cache data...")
            result = self.redis_client.flushdb()
            logger.warning("✅ [CACHE-FLUSH] ALL cache data cleared successfully")
            return 1 if result else 0
        except Exception as e:
            logger.error(f"❌ [CACHE-FLUSH] Failed to clear all cache: {e}")
            return 0
    
    def clear_microtendencias_cache(self, workspace_id: int = None) -> int:
        """Limpa cache específico de microtendências"""
        try:
            patterns = [
                "microtendencias_dashboard:*",
                "dashboard_summary:*", 
                "microtendencias_trends:*",
                "microtendencias_gateway_performance:*"
            ]
            
            if workspace_id:
                logger.info(f"🗑️ [CACHE-CLEAR] Clearing microtendencias cache for workspace {workspace_id}")
            else:
                logger.info("🗑️ [CACHE-CLEAR] Clearing ALL microtendencias cache")
            
            total_deleted = 0
            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                if keys:
                    deleted = self.redis_client.delete(*keys)
                    total_deleted += deleted
                    logger.info(f"🗑️ [CACHE-CLEAR] Pattern '{pattern}': deleted {deleted} keys")
            
            logger.info(f"✅ [CACHE-CLEAR] Total microtendencias keys cleared: {total_deleted}")
            return total_deleted
            
        except Exception as e:
            logger.error(f"❌ [CACHE-CLEAR] Failed to clear microtendencias cache: {e}")
            return 0


# Instância global do cache
cache_service = CacheService()


def cached_function(cache_type: str, ttl: Optional[int] = None):
    """
    Decorator para cachear funções automaticamente
    
    Usage:
        @cached_function('player_features', ttl=300)
        def get_player_features(workspace_id: int, cpf: str):
            return expensive_computation()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Converter args para kwargs se possível
            if args:
                func_kwargs = dict(zip(func.__code__.co_varnames, args))
                func_kwargs.update(kwargs)
            else:
                func_kwargs = kwargs
            
            return cache_service.get_or_compute(
                cache_type=cache_type,
                compute_func=lambda **kw: func(**kw),
                ttl=ttl,
                **func_kwargs
            )
        
        return wrapper
    return decorator


def batch_cache_player_timelines(workspace_id: int, player_id_list: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Cache otimizado para múltiplas timelines de jogadores
    """
    cache_keys = {player_id: cache_service._generate_cache_key('player_timeline', workspace_id=workspace_id, player_id=player_id) 
                  for player_id in player_id_list}
    
    # Verificar quais estão em cache
    cached_results = {}
    missing_player_ids = []
    
    for player_id, cache_key in cache_keys.items():
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            cached_results[player_id] = cached_data
        else:
            missing_player_ids.append(player_id)
    
    logger.info(f"📊 Batch timeline cache: {len(cached_results)} hits, {len(missing_player_ids)} misses")
    
    # Se todos estão em cache, retornar
    if not missing_player_ids:
        return cached_results
    
    # Buscar os que faltam (implementar na database.py)
    from ..utils.database import DatabaseManager
    db_manager = DatabaseManager()
    
    missing_data = db_manager.get_players_timeline_data_batch(workspace_id, missing_player_ids)
    
    # Cachear os novos dados
    ttl = cache_service.ttl_settings['player_timeline']
    for player_id, timeline_data in missing_data.items():
        cache_key = cache_keys[player_id]
        cache_service.set(cache_key, timeline_data, ttl)
    
    # Combinar resultados
    all_results = {**cached_results, **missing_data}
    return all_results