"""
Resource Manager for SafeSpace

This module provides resource management functionality for the SafeSpace package.
It detects available system resources and manages their allocation.
"""

import os
import sys
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import psutil

# Set up logging
logger = logging.getLogger(__name__)

class CoreType(Enum):
    """Types of CPU cores for resource allocation"""
    PERFORMANCE = "performance"
    EFFICIENCY = "efficiency"

@dataclass
class ResourceConfig:
    """Configuration for resource management"""
    performance_cores: int
    efficiency_cores: int
    cache_limit_bytes: int
    cache_dir: Path
    
    @classmethod
    def from_system(cls, cache_dir: Path) -> "ResourceConfig":
        """Create a resource configuration based on system capabilities"""
        # Get total CPU count
        total_cpus = psutil.cpu_count(logical=True)
        physical_cpus = psutil.cpu_count(logical=False)
        
        # Determine performance vs efficiency cores
        # On modern CPUs, we can assume about half are performance cores
        # and half are efficiency cores if there's a difference between
        # logical and physical
        if total_cpus > physical_cpus:
            performance_cores = max(1, physical_cpus // 2)
            efficiency_cores = max(1, physical_cpus - performance_cores)
        else:
            # On older CPUs, just split them evenly
            performance_cores = max(1, total_cpus // 2)
            efficiency_cores = max(1, total_cpus - performance_cores)
        
        # Get total memory and set cache limit to 10% of total memory
        total_memory = psutil.virtual_memory().total
        cache_limit = int(total_memory * 0.1)  # 10% of total memory
        
        return cls(
            performance_cores=performance_cores,
            efficiency_cores=efficiency_cores,
            cache_limit_bytes=cache_limit,
            cache_dir=cache_dir,
        )
    
    def to_dict(self) -> Dict[str, Union[int, str]]:
        """Convert the configuration to a dictionary"""
        return {
            "performance_cores": self.performance_cores,
            "efficiency_cores": self.efficiency_cores,
            "cache_limit_bytes": self.cache_limit_bytes,
            "cache_dir": str(self.cache_dir),
        }
    
    def save(self, config_file: Path) -> None:
        """Save the configuration to a file"""
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, config_file: Path) -> Optional["ResourceConfig"]:
        """Load the configuration from a file"""
        if not config_file.exists():
            return None
        
        try:
            with open(config_file, "r") as f:
                data = json.load(f)
            
            return cls(
                performance_cores=data["performance_cores"],
                efficiency_cores=data["efficiency_cores"],
                cache_limit_bytes=data["cache_limit_bytes"],
                cache_dir=Path(data["cache_dir"]),
            )
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return None


class ResourceManager:
    """Manages system resources for SafeSpace"""
    
    def __init__(self, cache_dir: Path) -> None:
        """Initialize the resource manager"""
        self.cache_dir = cache_dir
        self.config_file = cache_dir / "resource_config.json"
        
        # Load or create config
        config = ResourceConfig.load(self.config_file)
        if config is None:
            config = ResourceConfig.from_system(cache_dir)
            config.save(self.config_file)
        
        self.config = config
    
    def optimize_cores(self, core_type: CoreType) -> List[int]:
        """Get the CPU core IDs for the specified core type"""
        all_cpus = list(range(psutil.cpu_count(logical=True)))
        
        if core_type == CoreType.PERFORMANCE:
            # Use the first N cores for performance
            return all_cpus[:self.config.performance_cores]
        else:
            # Use the remaining cores for efficiency
            return all_cpus[self.config.performance_cores:self.config.performance_cores + self.config.efficiency_cores]
    
    def run_optimized(self, command: str, core_type: CoreType) -> int:
        """Run a command optimized for the specified core type"""
        if sys.platform == "darwin":  # macOS
            if core_type == CoreType.EFFICIENCY:
                # Use nice for lower priority on macOS
                command = f"nice -n 10 {command}"
            return os.system(command)
        else:  # Linux
            # Use taskset for CPU affinity on Linux
            cores = self.optimize_cores(core_type)
            core_list = ",".join(map(str, cores))
            return os.system(f"taskset -c {core_list} {command}")
    
    def cleanup_cache(self) -> None:
        """Clean up the cache directory based on cache limits"""
        if not self.cache_dir.exists():
            return
        
        # Get all files in cache dir
        cache_files = list(self.cache_dir.glob("**/*"))
        cache_files = [f for f in cache_files if f.is_file()]
        
        # Calculate total size
        total_size = sum(f.stat().st_size for f in cache_files)
        
        # If we're under the limit, do nothing
        if total_size <= self.config.cache_limit_bytes:
            return
        
        # Sort by access time (oldest first)
        cache_files.sort(key=lambda f: f.stat().st_atime)
        
        # Remove files until we're under the limit
        for file in cache_files:
            if total_size <= self.config.cache_limit_bytes:
                break
            
            size = file.stat().st_size
            try:
                file.unlink()
                total_size -= size
                logger.debug(f"Removed cache file: {file}")
            except OSError as e:
                logger.warning(f"Failed to remove cache file {file}: {e}")


def get_resource_manager(cache_dir: Path) -> ResourceManager:
    """Get or create a resource manager for the specified cache directory"""
    # Create cache dir if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    return ResourceManager(cache_dir)
