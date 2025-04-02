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
import tempfile
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
    CONFIG = "config"
    DATA = "data"


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
    
    def __post_init__(self):
        """Ensure type is an ArtifactType."""
        if isinstance(self.type, str):
            self.type = ArtifactType(self.type)
    
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
    A content-addressable cache for artifacts.
    
    Files are stored using their SHA256 hash as the key, allowing for deduplication
    of identical files and verification of file integrity.
    """
    
    def __init__(self, cache_dir: Path, default_artifact_type: ArtifactType = ArtifactType.OTHER):
        """
        Initialize the content-addressable cache.
        
        Args:
            cache_dir: The directory to use for the cache
            default_artifact_type: The default artifact type to use
        """
        self.cache_dir = cache_dir
        self.index_file = cache_dir / "cache_index.json"
        self.default_artifact_type = default_artifact_type
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up logger
        self.logger = logging.getLogger(__name__)
        
        # Initialize or load the artifact index
        self.artifact_index: Dict[str, ArtifactMetadata] = {}
        self._load_index()
    
    def _load_index(self) -> None:
        """Load the artifact index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    index_data = json.load(f)
                
                # Convert the loaded data to ArtifactMetadata objects
                self.artifact_index = {}
                for file_hash, metadata in index_data.items():
                    self.artifact_index[file_hash] = ArtifactMetadata(
                        hash=metadata['hash'],
                        original_name=metadata['original_name'],
                        type=ArtifactType(metadata['type']),
                        size=metadata['size'],
                        source_url=metadata.get('source_url'),
                        creation_time=metadata['creation_time'],
                        access_time=metadata['access_time'],
                        access_count=metadata['access_count'],
                        custom_metadata=metadata.get('metadata', {})
                    )
                
                self.logger.info(f"Loaded cache index with {len(self.artifact_index)} artifacts")
            except (json.JSONDecodeError, OSError) as e:
                self.logger.warning(f"Failed to load cache index: {e}")
                self.artifact_index = {}
    
    def _save_index(self) -> None:
        """Save the artifact index to disk."""
        try:
            # Convert the ArtifactMetadata objects to dictionaries
            index_data = {}
            for file_hash, metadata in self.artifact_index.items():
                index_data[file_hash] = {
                    'hash': metadata.hash,
                    'original_name': metadata.original_name,
                    'type': metadata.type.value,
                    'size': metadata.size,
                    'source_url': metadata.source_url,
                    'creation_time': metadata.creation_time,
                    'access_time': metadata.access_time,
                    'access_count': metadata.access_count,
                    'metadata': metadata.custom_metadata
                }
            
            # Write the index to disk
            with open(self.index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
                
            self.logger.debug(f"Saved cache index with {len(self.artifact_index)} artifacts")
        except OSError as e:
            self.logger.warning(f"Failed to save cache index: {e}")
    
    def _update_access_time(self, file_hash: str) -> None:
        """
        Update the access time and count for an artifact.
        
        Args:
            file_hash: The hash of the artifact
        """
        if file_hash in self.artifact_index:
            metadata = self.artifact_index[file_hash]
            metadata.access_time = time.time()
            metadata.access_count += 1
            self._save_index()
    
    def _compute_hash(self, file_path: Path) -> str:
        """
        Compute the SHA256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Hexadecimal digest of the hash
        """
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _get_artifact_path(self, file_hash: str) -> Path:
        """
        Get the path to an artifact.
        
        Args:
            file_hash: The hash of the artifact
            
        Returns:
            Path: Path to the artifact in the cache
        """
        return self.cache_dir / file_hash
    
    def add_file(self, file_path: Path, original_name: str = "", 
                source_url: str = "", custom_metadata: Dict = None) -> Optional[Path]:
        """
        Add a file to the cache.
        
        Args:
            file_path: Path to the file to add
            original_name: Original name of the file
            source_url: URL the file was downloaded from
            custom_metadata: Additional metadata for the file
            
        Returns:
            Optional[Path]: Path to the cached file, or None if adding failed
        """
        try:
            # Compute the hash of the file
            file_hash = self._compute_hash(file_path)
            
            # Check if the file is already in the cache
            if file_hash in self.artifact_index:
                self.logger.info(f"File {original_name} already in cache")
                self._update_access_time(file_hash)
                return self._get_artifact_path(file_hash)
            
            # Copy the file to the cache
            cache_path = self._get_artifact_path(file_hash)
            shutil.copy2(file_path, cache_path)
            
            # Add to the index
            self.artifact_index[file_hash] = ArtifactMetadata(
                hash=file_hash,
                original_name=original_name or file_path.name,
                type=self.default_artifact_type,
                size=file_path.stat().st_size,
                source_url=source_url,
                creation_time=time.time(),
                access_time=time.time(),
                access_count=1,
                custom_metadata=custom_metadata or {}
            )
            
            # Save the index
            self._save_index()
            
            self.logger.info(f"Added {original_name} to cache with hash {file_hash}")
            return cache_path
        except OSError as e:
            self.logger.error(f"Failed to add file to cache: {e}")
            return None
    
    def get_by_url(self, url: str) -> Optional[Path]:
        """
        Get a file from the cache by URL.
        
        Args:
            url: The URL the file was downloaded from
            
        Returns:
            Optional[Path]: Path to the cached file, or None if not found
        """
        # Find artifacts with the matching URL
        for file_hash, metadata in self.artifact_index.items():
            if metadata.source_url == url:
                # Update access time and count
                self._update_access_time(file_hash)
                
                # Return the path to the cached file
                return self._get_artifact_path(file_hash)
        
        return None
    
    def cleanup(self, max_size_bytes: int = None) -> int:
        """
        Clean up the cache, removing old or unused artifacts.
        
        Args:
            max_size_bytes: Maximum size of the cache in bytes
            
        Returns:
            int: Number of bytes freed
        """
        if not max_size_bytes:
            return 0
            
        # Calculate current cache size
        current_size = sum(metadata.size for metadata in self.artifact_index.values())
        
        # If we're under the limit, no cleanup needed
        if current_size <= max_size_bytes:
            return 0
            
        # We need to free up space
        bytes_to_free = current_size - max_size_bytes
        bytes_freed = 0
        
        # Sort artifacts by access time (oldest first)
        sorted_artifacts = sorted(
            self.artifact_index.items(),
            key=lambda x: (x[1].access_time, -x[1].access_count)
        )
        
        # Remove artifacts until we've freed enough space
        removed_hashes = []
        for file_hash, metadata in sorted_artifacts:
            # Skip if we've freed enough space
            if bytes_freed >= bytes_to_free:
                break
                
            # Remove the artifact
            artifact_path = self._get_artifact_path(file_hash)
            if artifact_path.exists():
                artifact_path.unlink()
                
            # Update tracking
            bytes_freed += metadata.size
            removed_hashes.append(file_hash)
            self.logger.info(f"Removed {metadata.original_name} from cache (freed {format_size(metadata.size)})")
        
        # Update the index
        for file_hash in removed_hashes:
            del self.artifact_index[file_hash]
            
        # Save the index
        self._save_index()
        
        self.logger.info(f"Cache cleanup complete: freed {format_size(bytes_freed)}")
        return bytes_freed


class CachedDownloader:
    """Utility for downloading files with caching capabilities."""
    
    def __init__(self, cache: ContentAddressableCache):
        """
        Initialize the downloader with a cache.
        
        Args:
            cache: The ContentAddressableCache to use
        """
        self.cache = cache
        self.logger = logging.getLogger(__name__)
    
    def download_file(self, url: str, dest_path: Path) -> bool:
        """
        Download a file from a URL to a destination path.
        
        Args:
            url: URL to download from
            dest_path: Path to save the file to
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create parent directories if they don't exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the file in chunks to handle large files
            with requests.get(url, stream=True) as response:
                response.raise_for_status()
                
                # Get total file size, if available
                total_size = int(response.headers.get('content-length', 0))
                self.logger.info(f"Downloading {url} ({format_size(total_size)})")
                
                # Write file in chunks
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            
            return True
        except Exception as e:
            self.logger.exception(f"Error downloading file from {url}: {e}")
            if dest_path.exists():
                dest_path.unlink()
            return False


class VMImageCache:
    """Cache specifically designed for VM images with verification."""
    
    def __init__(self, cache_dir: Path):
        """
        Initialize the VM image cache.
        
        Args:
            cache_dir: Directory to store cached VM images
        """
        self.cache = ContentAddressableCache(
            cache_dir, 
            default_artifact_type=ArtifactType.VM_IMAGE
        )
        self.logger = logging.getLogger(__name__)
    
    def get_vm_image(self, url: str, dest_path: Path, sha256_url: str) -> bool:
        """
        Get a VM image, either from cache or by downloading.
        
        Args:
            url: URL to download the VM image from
            dest_path: Where to copy the VM image to
            sha256_url: URL for the SHA256 checksum file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Try to get from cache first
            cached_file = self.cache.get_by_url(url)
            if cached_file:
                self.logger.info(f"Using cached VM image for {url}")
                shutil.copy2(cached_file, dest_path)
                return True
                
            # Download both the image and its checksum
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_dir = Path(tmpdir)
                iso_path = temp_dir / Path(url).name
                sha_path = temp_dir / f"{Path(url).name}.sha256"
                
                # Download image
                self.logger.info(f"Downloading VM image from {url}")
                downloader = CachedDownloader(self.cache)
                if not downloader.download_file(url, iso_path):
                    self.logger.error(f"Failed to download VM image from {url}")
                    return False
                    
                # Download checksum
                self.logger.info(f"Downloading checksum from {sha256_url}")
                if not downloader.download_file(sha256_url, sha_path):
                    self.logger.error(f"Failed to download checksum from {sha256_url}")
                    return False
                
                # Verify the image
                self.logger.info("Verifying VM image integrity")
                if self._verify_vm_image(iso_path, sha_path):
                    # Add to cache and copy to destination
                    self.logger.info("VM image verified, adding to cache")
                    cached_path = self.cache.add_file(
                        iso_path,
                        original_name=Path(url).name,
                        source_url=url,
                        custom_metadata={"sha256_url": sha256_url}
                    )
                    if cached_path:
                        shutil.copy2(cached_path, dest_path)
                        return True
                    else:
                        self.logger.error("Failed to add verified image to cache")
                else:
                    self.logger.error("VM image verification failed")
            
            return False
        except Exception as e:
            self.logger.exception(f"Error getting VM image: {e}")
            return False
    
    def _verify_vm_image(self, iso_path: Path, sha_path: Path) -> bool:
        """
        Verify a VM image against its SHA256 checksum.
        
        Args:
            iso_path: Path to the ISO file
            sha_path: Path to the SHA256 checksum file
            
        Returns:
            bool: True if verification was successful, False otherwise
        """
        try:
            # Read the expected hash from the sha file
            with open(sha_path, 'r') as f:
                hash_line = f.readline().strip()
                expected_hash = hash_line.split()[0]
            
            # Calculate the actual hash
            hasher = hashlib.sha256()
            with open(iso_path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    hasher.update(chunk)
            actual_hash = hasher.hexdigest()
            
            return actual_hash.lower() == expected_hash.lower()
        except Exception as e:
            self.logger.exception(f"Error verifying VM image: {e}")
            return False


class TestArtifactCache:
    """Cache specialized for test artifacts."""
    
    def __init__(self, cache_dir: Path):
        """
        Initialize the test artifact cache.
        
        Args:
            cache_dir: Directory to store cached test artifacts
        """
        self.cache = ContentAddressableCache(
            cache_dir, 
            default_artifact_type=ArtifactType.TEST_ARTIFACT
        )
        self.logger = logging.getLogger(__name__)
    
    def cache_test_file(self, file_path: Path, category: str) -> Optional[Path]:
        """
        Cache a test file.
        
        Args:
            file_path: Path to the file to cache
            category: Category of the test artifact (e.g., 'fixtures', 'reports')
            
        Returns:
            Optional[Path]: Path to the cached file, or None if caching failed
        """
        try:
            metadata = {
                "category": category,
                "test_artifact": True
            }
            
            return self.cache.add_file(
                file_path,
                original_name=file_path.name,
                custom_metadata=metadata
            )
        except Exception as e:
            self.logger.exception(f"Error caching test file: {e}")
            return None
    
    def get_test_file(self, file_path: Path, output_path: Path) -> bool:
        """
        Retrieve a test file from the cache.
        
        Args:
            file_path: Original path of the file
            output_path: Where to place the retrieved file
            
        Returns:
            bool: True if the file was retrieved, False otherwise
        """
        try:
            # Compute the hash of the file path to look for
            hasher = hashlib.sha256()
            hasher.update(str(file_path).encode())
            file_hash = hasher.hexdigest()
            
            # Check if we have any matches in metadata
            for cached_hash, metadata in self.cache.artifact_index.items():
                if metadata.original_name == file_path.name:
                    # Found a match, copy it to the output path
                    cached_path = self.cache._get_artifact_path(cached_hash)
                    if cached_path.exists():
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(cached_path, output_path)
                        self.cache._update_access_time(cached_hash)
                        return True
            
            # No match found
            return False
        except Exception as e:
            self.logger.exception(f"Error retrieving test file: {e}")
            return False
    
    def cleanup_test_artifacts(self, max_age_days: int = 7) -> int:
        """
        Clean up old test artifacts.
        
        Args:
            max_age_days: Maximum age of test artifacts in days
            
        Returns:
            int: Number of artifacts removed
        """
        try:
            now = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            removed_count = 0
            
            # Find old artifacts
            for file_hash, metadata in list(self.cache.artifact_index.items()):
                if metadata.type != ArtifactType.TEST_ARTIFACT:
                    continue
                    
                age = now - metadata.access_time
                if age > max_age_seconds:
                    # Remove old artifact
                    artifact_path = self.cache._get_artifact_path(file_hash)
                    if artifact_path.exists():
                        artifact_path.unlink()
                    
                    # Remove from index
                    del self.cache.artifact_index[file_hash]
                    removed_count += 1
                    
            # Save the index if we removed anything
            if removed_count > 0:
                self.cache._save_index()
                self.logger.info(f"Removed {removed_count} old test artifacts")
                
            return removed_count
        except Exception as e:
            self.logger.exception(f"Error cleaning up test artifacts: {e}")
            return 0


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


def get_vm_image_cache(cache_dir: Path) -> 'VMImageCache':
    """
    Get or create a VMImageCache instance for the given cache directory.
    
    Args:
        cache_dir: Path to the cache directory
        
    Returns:
        VMImageCache: An instance of VMImageCache
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    return VMImageCache(cache_dir)


def get_test_artifact_cache(cache_dir: Path) -> TestArtifactCache:
    """
    Get or create a TestArtifactCache instance for the given cache directory.
    
    Args:
        cache_dir: Path to the cache directory
        
    Returns:
        TestArtifactCache: An instance of TestArtifactCache
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    return TestArtifactCache(cache_dir) 