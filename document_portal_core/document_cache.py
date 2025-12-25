"""
Document Cache Module for Document Portal.
Implements multi-layer caching strategy to reduce LLM costs and processing time.

Caching Layers:
- L1: In-memory LRU cache (fast, 100MB, 1-hour TTL)
- L2: Redis cache (distributed, 1GB, 7-day TTL)
- L3: Disk cache (persistent, unlimited, 30-day TTL)

Cache Keys:
- OCR results: ocr:{image_hash}
- Gemini results: gemini:{image_hash}
- Extraction results: extract:{user_id}
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from PIL import Image
from logger import GLOBAL_LOGGER as log

# Try to import Redis (optional dependency)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    log.warning("Redis not available. Using in-memory cache only.")


class DocumentCache:
    """
    Multi-layer caching for document processing results.
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        memory_cache_size: int = 100,
        disk_cache_dir: str = "cache"
    ):
        """
        Initialize document cache with multiple layers.

        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            memory_cache_size: Max items in memory cache
            disk_cache_dir: Directory for disk cache
        """
        # L1: In-memory cache (LRU)
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.memory_cache_size = memory_cache_size
        self.memory_access_times: Dict[str, datetime] = {}

        # L2: Redis cache (distributed, optional)
        self.redis = None
        if REDIS_AVAILABLE:
            try:
                self.redis = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=False,  # We'll handle encoding
                    socket_connect_timeout=1
                )
                # Test connection
                self.redis.ping()
                log.info("Redis cache connected successfully")
            except Exception as e:
                log.warning(f"Redis connection failed: {e}. Using memory cache only.")
                self.redis = None

        # L3: Disk cache (persistent)
        self.disk_cache_dir = Path(disk_cache_dir)
        self.disk_cache_dir.mkdir(exist_ok=True, parents=True)

        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "saves": 0,
            "evictions": 0
        }

    def get_image_hash(self, image_path: Path) -> str:
        """
        Generate perceptual hash of image content.
        Fast and robust to minor variations (rotation, compression).

        Args:
            image_path: Path to image file

        Returns:
            16-character hexadecimal hash

        Performance: ~0.01-0.02 seconds
        """
        try:
            with Image.open(image_path) as img:
                # Resize to 8x8 for fast perceptual hashing
                img_small = img.resize((8, 8), Image.Resampling.LANCZOS).convert('L')
                pixels = list(img_small.getdata())

                # Calculate average pixel value
                avg = sum(pixels) / len(pixels)

                # Create bit string (1 if above average, 0 otherwise)
                bits = ''.join('1' if p > avg else '0' for p in pixels)

                # Hash the bit string
                return hashlib.md5(bits.encode()).hexdigest()
        except Exception as e:
            log.error(f"Image hash generation failed: {e}")
            # Fallback to file hash
            return self._get_file_hash(image_path)

    def _get_file_hash(self, file_path: Path) -> str:
        """Fallback: Hash file content (slower but reliable)."""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _evict_lru(self):
        """Evict least recently used item from memory cache."""
        if not self.memory_access_times:
            return

        # Find least recently used
        lru_key = min(self.memory_access_times.items(), key=lambda x: x[1])[0]

        # Evict
        del self.memory_cache[lru_key]
        del self.memory_access_times[lru_key]
        self.stats["evictions"] += 1

    def _get_from_memory(self, key: str) -> Optional[Any]:
        """Get value from L1 memory cache."""
        if key in self.memory_cache:
            self.memory_access_times[key] = datetime.now()
            return self.memory_cache[key]
        return None

    def _save_to_memory(self, key: str, value: Any):
        """Save value to L1 memory cache with LRU eviction."""
        # Evict if cache is full
        if len(self.memory_cache) >= self.memory_cache_size:
            self._evict_lru()

        self.memory_cache[key] = value
        self.memory_access_times[key] = datetime.now()

    def _get_from_redis(self, key: str) -> Optional[Any]:
        """Get value from L2 Redis cache."""
        if not self.redis:
            return None

        try:
            cached = self.redis.get(key)
            if cached:
                return json.loads(cached.decode('utf-8'))
            return None
        except Exception as e:
            log.warning(f"Redis get failed: {e}")
            return None

    def _save_to_redis(self, key: str, value: Any, ttl_seconds: int):
        """Save value to L2 Redis cache with TTL."""
        if not self.redis:
            return

        try:
            serialized = json.dumps(value)
            self.redis.setex(key, ttl_seconds, serialized)
        except Exception as e:
            log.warning(f"Redis save failed: {e}")

    def _get_from_disk(self, key: str) -> Optional[Any]:
        """Get value from L3 disk cache."""
        cache_file = self.disk_cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        try:
            # Check if expired
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime > timedelta(days=30):
                cache_file.unlink()  # Delete expired
                return None

            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Disk cache read failed: {e}")
            return None

    def _save_to_disk(self, key: str, value: Any):
        """Save value to L3 disk cache."""
        cache_file = self.disk_cache_dir / f"{key}.json"

        try:
            with open(cache_file, 'w') as f:
                json.dump(value, f)
        except Exception as e:
            log.warning(f"Disk cache write failed: {e}")

    def get_ocr_text(self, image_hash: str) -> Optional[str]:
        """
        Get cached OCR text result.

        Args:
            image_hash: Hash of image content

        Returns:
            Cached OCR text or None if not cached
        """
        key = f"ocr:{image_hash}"

        # Try L1 (memory)
        cached = self._get_from_memory(key)
        if cached:
            self.stats["hits"] += 1
            log.debug(f"OCR cache hit (memory): {image_hash[:8]}")
            return cached.get("text")

        # Try L2 (Redis)
        cached = self._get_from_redis(key)
        if cached:
            self.stats["hits"] += 1
            log.debug(f"OCR cache hit (Redis): {image_hash[:8]}")
            # Promote to L1
            self._save_to_memory(key, cached)
            return cached.get("text")

        # Try L3 (Disk)
        cached = self._get_from_disk(key)
        if cached:
            self.stats["hits"] += 1
            log.debug(f"OCR cache hit (disk): {image_hash[:8]}")
            # Promote to L1 and L2
            self._save_to_memory(key, cached)
            self._save_to_redis(key, cached, 604800)  # 7 days
            return cached.get("text")

        self.stats["misses"] += 1
        return None

    def save_ocr_text(self, image_hash: str, text: str, metadata: Dict[str, Any] = None):
        """
        Cache OCR text result across all layers.

        Args:
            image_hash: Hash of image content
            text: Extracted OCR text
            metadata: Optional metadata (processing time, confidence, etc.)
        """
        key = f"ocr:{image_hash}"
        value = {
            "text": text,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }

        # Save to all layers
        self._save_to_memory(key, value)
        self._save_to_redis(key, value, 604800)  # 7 days
        self._save_to_disk(key, value)

        self.stats["saves"] += 1
        log.debug(f"OCR result cached: {image_hash[:8]}")

    def get_gemini_result(self, image_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get cached Gemini Vision API result.

        Args:
            image_hash: Hash of image content

        Returns:
            Cached Gemini result or None if not cached
        """
        key = f"gemini:{image_hash}"

        # Try L1 (memory)
        cached = self._get_from_memory(key)
        if cached:
            self.stats["hits"] += 1
            log.info(f"Gemini cache hit (memory) - SAVED $$: {image_hash[:8]}")
            return cached.get("result")

        # Try L2 (Redis)
        cached = self._get_from_redis(key)
        if cached:
            self.stats["hits"] += 1
            log.info(f"Gemini cache hit (Redis) - SAVED $$: {image_hash[:8]}")
            # Promote to L1
            self._save_to_memory(key, cached)
            return cached.get("result")

        # Try L3 (Disk)
        cached = self._get_from_disk(key)
        if cached:
            self.stats["hits"] += 1
            log.info(f"Gemini cache hit (disk) - SAVED $$: {image_hash[:8]}")
            # Promote to L1 and L2
            self._save_to_memory(key, cached)
            self._save_to_redis(key, cached, 2592000)  # 30 days (expensive calls)
            return cached.get("result")

        self.stats["misses"] += 1
        return None

    def save_gemini_result(self, image_hash: str, result: Dict[str, Any]):
        """
        Cache Gemini Vision API result (expensive, cache longer).

        Args:
            image_hash: Hash of image content
            result: Gemini API response
        """
        key = f"gemini:{image_hash}"
        value = {
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

        # Save to all layers with longer TTL (expensive API calls)
        self._save_to_memory(key, value)
        self._save_to_redis(key, value, 2592000)  # 30 days
        self._save_to_disk(key, value)

        self.stats["saves"] += 1
        log.info(f"Gemini result cached: {image_hash[:8]}")

    def get_extraction_result(self, document_id: str, extraction_type: str) -> Optional[Dict[str, Any]]:
        """
        Get cached extraction result (ID, invoice, etc.).

        Args:
            document_id: Document identifier (user_id, invoice_number, etc.)
            extraction_type: Type of extraction (id, invoice, contract)

        Returns:
            Cached extraction result or None
        """
        key = f"extract:{extraction_type}:{document_id}"
        cached = self._get_from_redis(key) or self._get_from_disk(key)

        if cached:
            self.stats["hits"] += 1
            return cached.get("result")

        self.stats["misses"] += 1
        return None

    def save_extraction_result(
        self,
        document_id: str,
        extraction_type: str,
        result: Dict[str, Any],
        ttl_days: int = 7
    ):
        """
        Cache extraction result.

        Args:
            document_id: Document identifier
            extraction_type: Type of extraction
            result: Extraction result
            ttl_days: Time to live in days
        """
        key = f"extract:{extraction_type}:{document_id}"
        value = {
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

        self._save_to_redis(key, value, ttl_days * 86400)
        self._save_to_disk(key, value)

        self.stats["saves"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            {
                "hits": int,
                "misses": int,
                "hit_rate": float,
                "saves": int,
                "evictions": int,
                "memory_size": int,
                "redis_connected": bool
            }
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            **self.stats,
            "hit_rate": hit_rate,
            "hit_rate_percent": hit_rate * 100,
            "memory_size": len(self.memory_cache),
            "redis_connected": self.redis is not None
        }

    def clear_cache(self, cache_type: str = "all"):
        """
        Clear cache (for testing or maintenance).

        Args:
            cache_type: "memory", "redis", "disk", or "all"
        """
        if cache_type in ["memory", "all"]:
            self.memory_cache.clear()
            self.memory_access_times.clear()
            log.info("Memory cache cleared")

        if cache_type in ["redis", "all"] and self.redis:
            try:
                self.redis.flushdb()
                log.info("Redis cache cleared")
            except Exception as e:
                log.error(f"Redis clear failed: {e}")

        if cache_type in ["disk", "all"]:
            for cache_file in self.disk_cache_dir.glob("*.json"):
                cache_file.unlink()
            log.info("Disk cache cleared")


# Singleton instance
DOCUMENT_CACHE = DocumentCache(
    redis_host=os.getenv("REDIS_HOST", "localhost"),
    redis_port=int(os.getenv("REDIS_PORT", 6379)),
    redis_db=int(os.getenv("REDIS_DB", 0))
)
