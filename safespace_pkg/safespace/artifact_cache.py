"""
Content-Addressable Artifact Cache for SafeSpace

This module provides advanced caching for artifacts such as VM images and test artifacts
using content-addressable storage to improve performance of repeated operations.
"""

import hashlib
import json
import logging
import os
import shutil
import stat
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from urllib.parse import urlparse

import requests

from .utils import log_status, format_size, Colors, run_command

# Set up logging
logger = logging.getLogger(__name__)

class ArtifactType(Enum):
    """Types of artifacts that can be cached"""
    VM_IMAGE = "vm_image"
    TEST_ARTIFACT = "test_artifact"
    CONTAINER_IMAGE = "container_image"
    PACKAGE = "package"
    OTHER = "other"


@dataclass
class ArtifactMetadata:
    """Metadata for a cached artifact"""
    hash: str  # Content hash
    original_name: str
    type: ArtifactType
    size: int
    source_url: Optional[str] = None
    creation_time: float = field(default_factory=time.time)
    access_time: float = field(default_factory=time.time)
    access_count: int = 0
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to a dictionary for serialization"""
        data = asdict(self)
        # Convert enum to string
        data["type"] = self.type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactMetadata":
        """Create metadata from a dictionary"""
        # Convert string to enum
        data["type"] = ArtifactType(data["type"])
        return cls(**data)


class ContentAddressableCache:
    """
    Content-addressable storage system for caching artifacts.
    
    This cache stores files based on their content hash, allowing for:
    - Deduplication of identical files
    - Verification of file integrity
    - Quick lookup of previously seen files
    - Efficient storage and retrieval of artifacts
    """
    
    def __init__(self, cache_dir: Path, max_size_bytes: int = None, 
                 index_file: str = "artifacts.json") -> None:
        """
        Initialize the content-addressable cache.
        
        Args:
            cache_dir: Directory to store cached artifacts
            max_size_bytes: Maximum size of the cache in bytes. If None, no limit.
            index_file: Name of the file to store the artifact index
        """
        self.cache_dir = cache_dir
        self.content_dir = cache_dir / "content"
        self.metadata_dir = cache_dir / "metadata"
        self.max_size_bytes = max_size_bytes
        self.index_file = cache_dir / index_file
        
        # Ensure cache directories exist
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Load index file if it exists
        self.artifact_index: Dict[str, ArtifactMetadata] = {}
        self._load_index()
    
    def _compute_hash(self, file_path: Path) -> str:
        """
        Compute the SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            The SHA-256 hash digest as a hexadecimal string
        """
        hash_obj = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    
    def _compute_hash_from_url(self, url: str) -> Optional[str]:
        """
        Check if a URL contains a hash in its path or query parameters.
        
        Args:
            url: The URL to check
            
        Returns:
            The hash if found, None otherwise
        """
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # Common patterns:
        # 1. Hash in filename: /path/to/file-a1b2c3d4.ext
        # 2. Hash in directory: /path/to/a1b2c3d4/file.ext
        # 3. Hash in query: /path/to/file.ext?hash=a1b2c3d4
        
        # Check query params for hash
        query_params = parsed_url.query.split('&')
        for param in query_params:
            if param.startswith('hash=') or param.startswith('sha256='):
                return param.split('=')[1]
        
        return None
    
    def _load_index(self) -> None:
        """Load the artifact index from the index file"""
        if not self.index_file.exists():
            return
        
        try:
            with open(self.index_file, "r") as f:
                index_data = json.load(f)
                
            for hash_val, metadata in index_data.items():
                self.artifact_index[hash_val] = ArtifactMetadata.from_dict(metadata)
                
            logger.debug(f"Loaded {len(self.artifact_index)} artifacts from cache index")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error loading cache index: {e}")
    
    def _save_index(self) -> None:
        """Save the artifact index to the index file"""
        index_data = {
            hash_val: metadata.to_dict() 
            for hash_val, metadata in self.artifact_index.items()
        }
        
        try:
            with open(self.index_file, "w") as f:
                json.dump(index_data, f, indent=2)
        except (OSError, IOError) as e:
            logger.error(f"Error saving cache index: {e}")
    
    def _update_access_time(self, hash_val: str) -> None:
        """Update the access time for an artifact"""
        if hash_val in self.artifact_index:
            self.artifact_index[hash_val].access_time = time.time()
            self.artifact_index[hash_val].access_count += 1
    
    def _get_cache_size(self) -> int:
        """Get the total size of all files in the cache"""
        return sum(metadata.size for metadata in self.artifact_index.values())
    
    def _cleanup(self, required_space: int = 0) -> None:
        """
        Clean up the cache to stay within size limits.
        
        Args:
            required_space: Additional space needed for a new artifact
        """
        if not self.max_size_bytes:
            return
        
        current_size = self._get_cache_size()
        target_size = self.max_size_bytes - required_space
        
        if current_size <= target_size:
            return
        
        # Sort artifacts by access time (oldest first)
        artifacts_to_consider = list(self.artifact_index.items())
        artifacts_to_consider.sort(key=lambda x: (x[1].access_time, -x[1].access_count))
        
        # Remove artifacts until we're under the limit
        for hash_val, metadata in artifacts_to_consider:
            if current_size <= target_size:
                break
            
            content_path = self.content_dir / hash_val
            metadata_path = self.metadata_dir / f"{hash_val}.json"
            
            try:
                if content_path.exists():
                    content_path.unlink()
                if metadata_path.exists():
                    metadata_path.unlink()
                    
                current_size -= metadata.size
                del self.artifact_index[hash_val]
                
                logger.debug(f"Removed artifact from cache: {metadata.original_name} [{hash_val}]")
            except OSError as e:
                logger.warning(f"Failed to remove cached artifact {hash_val}: {e}")
        
        # Save updated index
        self._save_index()
    
    def put(self, file_path: Path, artifact_type: ArtifactType, 
            source_url: Optional[str] = None, custom_metadata: Dict[str, Any] = None) -> str:
        """
        Add a file to the cache.
        
        Args:
            file_path: Path to the file to cache
            artifact_type: Type of artifact
            source_url: Optional URL source of the artifact
            custom_metadata: Optional custom metadata
            
        Returns:
            The content hash of the added file
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Compute file hash
        file_hash = self._compute_hash(file_path)
        file_size = file_path.stat().st_size
        
        # Check if file is already in cache
        if file_hash in self.artifact_index:
            # Update access time and count
            self._update_access_time(file_hash)
            logger.debug(f"Artifact already in cache: {file_path.name} [{file_hash}]")
            return file_hash
        
        # Clean up cache if needed to make room for the new file
        self._cleanup(required_space=file_size)
        
        # Create new paths
        content_path = self.content_dir / file_hash
        metadata_path = self.metadata_dir / f"{file_hash}.json"
        
        # Copy file to content directory
        try:
            shutil.copy2(file_path, content_path)
            
            # On Unix systems, make sure the file is read-only
            if os.name == "posix":
                content_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            
            # Create metadata
            metadata = ArtifactMetadata(
                hash=file_hash,
                original_name=file_path.name,
                type=artifact_type,
                size=file_size,
                source_url=source_url,
                custom_metadata=custom_metadata or {}
            )
            
            # Save metadata file
            with open(metadata_path, "w") as f:
                json.dump(metadata.to_dict(), f, indent=2)
            
            # Update artifact index
            self.artifact_index[file_hash] = metadata
            self._save_index()
            
            logger.debug(f"Added artifact to cache: {file_path.name} [{file_hash}]")
            return file_hash
            
        except (OSError, IOError) as e:
            logger.error(f"Error adding artifact to cache: {e}")
            if content_path.exists():
                content_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()
            raise
    
    def get(self, hash_val: str, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Retrieve a file from the cache.
        
        Args:
            hash_val: Hash of the file to retrieve
            output_path: Optional path to copy the file to
            
        Returns:
            Path to the cached file or copied file, or None if not found
        """
        # Check if file is in cache
        if hash_val not in self.artifact_index:
            return None
        
        # Update access time
        self._update_access_time(hash_val)
        self._save_index()
        
        # Path to cached file
        content_path = self.content_dir / hash_val
        
        if not content_path.exists():
            # File is in index but not on disk
            logger.warning(f"Cached file not found on disk: {hash_val}")
            del self.artifact_index[hash_val]
            self._save_index()
            return None
        
        if output_path:
            # Copy file to output path
            try:
                shutil.copy2(content_path, output_path)
                return output_path
            except (OSError, IOError) as e:
                logger.error(f"Error copying cached file: {e}")
                return None
        
        return content_path
    
    def get_with_name(self, hash_val: str, output_dir: Path, 
                      use_original_name: bool = True) -> Optional[Path]:
        """
        Retrieve a file from the cache and save it with its original name.
        
        Args:
            hash_val: Hash of the file to retrieve
            output_dir: Directory to save the file to
            use_original_name: Whether to use the original filename
            
        Returns:
            Path to the copied file, or None if not found
        """
        # Check if file is in cache
        if hash_val not in self.artifact_index:
            return None
        
        metadata = self.artifact_index[hash_val]
        
        # Determine output filename
        if use_original_name:
            output_name = metadata.original_name
        else:
            # Use hash and preserve file extension
            original_parts = metadata.original_name.rsplit('.', 1)
            if len(original_parts) > 1:
                output_name = f"{hash_val}.{original_parts[1]}"
            else:
                output_name = hash_val
        
        output_path = output_dir / output_name
        return self.get(hash_val, output_path)
    
    def contains(self, hash_val: str) -> bool:
        """
        Check if a file is in the cache.
        
        Args:
            hash_val: Hash of the file to check
            
        Returns:
            True if the file is in the cache, False otherwise
        """
        # First check the index
        if hash_val not in self.artifact_index:
            return False
        
        # Then verify the file exists
        content_path = self.content_dir / hash_val
        if not content_path.exists():
            # Remove from index if file doesn't exist
            del self.artifact_index[hash_val]
            self._save_index()
            return False
        
        return True
    
    def get_metadata(self, hash_val: str) -> Optional[ArtifactMetadata]:
        """
        Get metadata for a cached file.
        
        Args:
            hash_val: Hash of the file
            
        Returns:
            Metadata for the file, or None if not found
        """
        if not self.contains(hash_val):
            return None
        
        return self.artifact_index[hash_val]
    
    def list_artifacts(self, artifact_type: Optional[ArtifactType] = None) -> List[Tuple[str, ArtifactMetadata]]:
        """
        List artifacts in the cache.
        
        Args:
            artifact_type: Optional type to filter by
            
        Returns:
            List of (hash, metadata) tuples
        """
        artifacts = list(self.artifact_index.items())
        
        if artifact_type:
            artifacts = [(h, m) for h, m in artifacts if m.type == artifact_type]
        
        return artifacts
    
    def remove(self, hash_val: str) -> bool:
        """
        Remove a file from the cache.
        
        Args:
            hash_val: Hash of the file to remove
            
        Returns:
            True if the file was removed, False otherwise
        """
        if hash_val not in self.artifact_index:
            return False
        
        content_path = self.content_dir / hash_val
        metadata_path = self.metadata_dir / f"{hash_val}.json"
        
        try:
            if content_path.exists():
                content_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()
                
            del self.artifact_index[hash_val]
            self._save_index()
            
            return True
        except OSError as e:
            logger.warning(f"Failed to remove cached artifact {hash_val}: {e}")
            return False
    
    def clear(self) -> None:
        """Clear all files from the cache"""
        for hash_val in list(self.artifact_index.keys()):
            self.remove(hash_val)
        
        # Make sure the index is empty and saved
        self.artifact_index = {}
        self._save_index()
    
    def verify_integrity(self) -> Tuple[int, int]:
        """
        Verify the integrity of all cached files.
        
        Returns:
            Tuple of (valid_count, invalid_count)
        """
        valid_count = 0
        invalid_count = 0
        
        for hash_val, metadata in list(self.artifact_index.items()):
            content_path = self.content_dir / hash_val
            
            if not content_path.exists():
                logger.warning(f"Cached file not found on disk: {hash_val}")
                del self.artifact_index[hash_val]
                invalid_count += 1
                continue
            
            # Verify hash
            computed_hash = self._compute_hash(content_path)
            if computed_hash != hash_val:
                logger.warning(f"Hash mismatch for cached file: expected {hash_val}, got {computed_hash}")
                # Remove corrupted file
                self.remove(hash_val)
                invalid_count += 1
            else:
                valid_count += 1
        
        # Save updated index
        self._save_index()
        
        return valid_count, invalid_count


class CachedDownloader:
    """
    A utility for downloading files with caching.
    
    This class wraps the ContentAddressableCache to provide an easy way
    to download files while taking advantage of caching.
    """
    
    def __init__(self, cache: ContentAddressableCache) -> None:
        """
        Initialize the cached downloader.
        
        Args:
            cache: The ContentAddressableCache to use
        """
        self.cache = cache
    
    def download(self, url: str, output_path: Path, 
                 artifact_type: ArtifactType = ArtifactType.OTHER,
                 expected_hash: Optional[str] = None,
                 custom_metadata: Dict[str, Any] = None) -> bool:
        """
        Download a file with caching.
        
        If the file is already in the cache, it will be retrieved from there.
        Otherwise, it will be downloaded and added to the cache.
        
        Args:
            url: URL to download
            output_path: Path to save the file to
            artifact_type: Type of artifact
            expected_hash: Optional expected hash for verification
            custom_metadata: Optional custom metadata
            
        Returns:
            True if the download was successful, False otherwise
        """
        # Extract filename from URL
        filename = os.path.basename(urlparse(url).path)
        if not filename:
            filename = "downloaded_file"
        
        # Try to get file hash from URL
        url_hash = self._compute_hash_from_url(url)
        
        # If we have an expected hash, use it
        file_hash = expected_hash or url_hash
        
        # If we have a hash, check if the file is already in the cache
        if file_hash and self.cache.contains(file_hash):
            logger.info(f"Using cached version of {filename}")
            # Retrieve from cache
            cached_path = self.cache.get(file_hash, output_path)
            return cached_path is not None
        
        # If not in cache or we don't have a hash, download the file
        logger.info(f"Downloading {url}")
        
        # Create temporary file
        temp_dir = Path(output_path.parent / ".temp")
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / f"download_{int(time.time())}_{filename}"
        
        try:
            # Download file
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            # If we have an expected hash, verify it
            if expected_hash:
                computed_hash = self.cache._compute_hash(temp_path)
                if computed_hash != expected_hash:
                    logger.error(f"Hash mismatch: expected {expected_hash}, got {computed_hash}")
                    return False
                file_hash = computed_hash
            
            # Add to cache
            file_hash = self.cache.put(
                temp_path, 
                artifact_type, 
                source_url=url,
                custom_metadata=custom_metadata
            )
            
            # Get from cache to output path
            cached_path = self.cache.get(file_hash, output_path)
            return cached_path is not None
            
        except (requests.RequestException, OSError) as e:
            logger.error(f"Error downloading {url}: {e}")
            return False
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
    
    def _compute_hash_from_url(self, url: str) -> Optional[str]:
        """Extract a hash from a URL, if present"""
        return self.cache._compute_hash_from_url(url)


class VMImageCache:
    """
    Specialized cache for VM images.
    
    This class wraps ContentAddressableCache to provide specific functionality
    for caching and retrieving VM images.
    """
    
    def __init__(self, cache: ContentAddressableCache) -> None:
        """
        Initialize the VM image cache.
        
        Args:
            cache: The ContentAddressableCache to use
        """
        self.cache = cache
        self.downloader = CachedDownloader(cache)
    
    def get_vm_image(self, url: str, target_path: Path, 
                     sha256_url: Optional[str] = None) -> bool:
        """
        Get a VM image, either from cache or by downloading it.
        
        Args:
            url: URL to download the VM image from
            target_path: Path to save the VM image to
            sha256_url: Optional URL to download the SHA256 hash from
            
        Returns:
            True if the VM image was successfully obtained, False otherwise
        """
        expected_hash = None
        
        # If we have a SHA256 URL, download and parse it
        if sha256_url:
            # Download SHA256 file to memory
            try:
                response = requests.get(sha256_url)
                response.raise_for_status()
                
                # Parse SHA256 file (format: "hash filename")
                sha_content = response.text.strip()
                
                # Extract hash from first line that contains a hash
                for line in sha_content.splitlines():
                    parts = line.split()
                    if len(parts) >= 1 and len(parts[0]) == 64:
                        expected_hash = parts[0]
                        break
                
                if not expected_hash:
                    logger.warning(f"Could not extract hash from {sha256_url}")
            except requests.RequestException as e:
                logger.warning(f"Error downloading SHA256 file: {e}")
        
        # Prepare custom metadata
        custom_metadata = {
            "vm_image": True,
            "sha256_url": sha256_url
        }
        
        # Download/retrieve from cache
        return self.downloader.download(
            url, 
            target_path, 
            artifact_type=ArtifactType.VM_IMAGE,
            expected_hash=expected_hash,
            custom_metadata=custom_metadata
        )
    
    def list_vm_images(self) -> List[Tuple[str, ArtifactMetadata]]:
        """
        List all VM images in the cache.
        
        Returns:
            List of (hash, metadata) tuples
        """
        return self.cache.list_artifacts(ArtifactType.VM_IMAGE)
    
    def get_image_info(self, hash_val: str) -> Dict[str, Any]:
        """
        Get information about a VM image.
        
        Args:
            hash_val: Hash of the VM image
            
        Returns:
            Dictionary with information about the VM image
        """
        metadata = self.cache.get_metadata(hash_val)
        if not metadata:
            return {}
        
        return {
            "hash": metadata.hash,
            "name": metadata.original_name,
            "size": format_size(metadata.size),
            "source": metadata.source_url,
            "cached_time": time.ctime(metadata.creation_time),
            "last_used": time.ctime(metadata.access_time),
            "use_count": metadata.access_count,
        }


class TestArtifactCache:
    """
    Specialized cache for test artifacts.
    
    This class provides functionality for caching test-related artifacts
    such as test data, fixtures, and other test resources.
    """
    
    def __init__(self, cache: ContentAddressableCache) -> None:
        """
        Initialize the test artifact cache.
        
        Args:
            cache: The ContentAddressableCache to use
        """
        self.cache = cache
    
    def cache_artifact(self, file_path: Path, 
                       category: str = "general") -> str:
        """
        Add a test artifact to the cache.
        
        Args:
            file_path: Path to the file to cache
            category: Category of the test artifact
            
        Returns:
            The content hash of the added file
        """
        custom_metadata = {"category": category}
        
        return self.cache.put(
            file_path,
            ArtifactType.TEST_ARTIFACT,
            custom_metadata=custom_metadata
        )
    
    def cache_directory(self, dir_path: Path, 
                        category: str = "general", 
                        exclude_patterns: List[str] = None) -> List[str]:
        """
        Add all files in a directory to the cache.
        
        Args:
            dir_path: Path to the directory to cache
            category: Category of the test artifacts
            exclude_patterns: Patterns to exclude
            
        Returns:
            List of content hashes of added files
        """
        exclude_patterns = exclude_patterns or [
            ".git", "__pycache__", "*.pyc", 
            ".pytest_cache", "*.egg-info", "*.so", "*.o"
        ]
        
        # Compile patterns into a function
        def should_exclude(path: Path) -> bool:
            path_str = str(path)
            return any(pattern in path_str for pattern in exclude_patterns)
        
        # Find all files in the directory
        files_to_cache = []
        for root, _, files in os.walk(dir_path):
            root_path = Path(root)
            if should_exclude(root_path):
                continue
                
            for file in files:
                file_path = root_path / file
                if not should_exclude(file_path):
                    files_to_cache.append(file_path)
        
        # Cache files in parallel
        hashes = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for file_path in files_to_cache:
                # Determine relative path for categorization
                rel_path = file_path.relative_to(dir_path)
                # Use dirname as subcategory
                subcategory = f"{category}/{rel_path.parent}"
                futures.append(
                    executor.submit(self.cache_artifact, file_path, subcategory)
                )
            
            for future in futures:
                hashes.append(future.result())
        
        return hashes
    
    def get_artifact(self, hash_val: str, output_path: Path) -> Optional[Path]:
        """
        Retrieve a test artifact from the cache.
        
        Args:
            hash_val: Hash of the file to retrieve
            output_path: Path to save the file to
            
        Returns:
            Path to the retrieved file, or None if not found
        """
        return self.cache.get(hash_val, output_path)
    
    def list_artifacts(self, category: Optional[str] = None) -> List[Tuple[str, ArtifactMetadata]]:
        """
        List test artifacts in the cache.
        
        Args:
            category: Optional category to filter by
            
        Returns:
            List of (hash, metadata) tuples
        """
        artifacts = self.cache.list_artifacts(ArtifactType.TEST_ARTIFACT)
        
        if category:
            artifacts = [
                (h, m) for h, m in artifacts 
                if m.custom_metadata.get("category", "").startswith(category)
            ]
        
        return artifacts


def get_artifact_cache(cache_dir: Path, max_size_mb: int = 2048) -> ContentAddressableCache:
    """
    Get or create a content-addressable cache.
    
    Args:
        cache_dir: Directory to store the cache
        max_size_mb: Maximum size of the cache in megabytes
        
    Returns:
        ContentAddressableCache instance
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert max size to bytes
    max_size_bytes = max_size_mb * 1024 * 1024
    
    return ContentAddressableCache(cache_dir, max_size_bytes)


def get_vm_image_cache(cache_dir: Path) -> VMImageCache:
    """
    Get or create a VM image cache.
    
    Args:
        cache_dir: Directory to store the cache
        
    Returns:
        VMImageCache instance
    """
    cache = get_artifact_cache(cache_dir)
    return VMImageCache(cache)


def get_test_artifact_cache(cache_dir: Path) -> TestArtifactCache:
    """
    Get or create a test artifact cache.
    
    Args:
        cache_dir: Directory to store the cache
        
    Returns:
        TestArtifactCache instance
    """
    cache = get_artifact_cache(cache_dir)
    return TestArtifactCache(cache) 