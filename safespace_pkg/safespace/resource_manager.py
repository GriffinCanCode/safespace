"""
Resource Manager for SafeSpace

This module provides resource management functionality for the SafeSpace package.
It detects available system resources and manages their allocation.
"""

import os
import sys
import json
import logging
import time
import platform
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import psutil

from .settings import get_settings
from .utils import log_status, Colors, format_size

# Set up logging
logger = logging.getLogger(__name__)

class CoreType(Enum):
    """Types of CPU cores for resource allocation"""
    PERFORMANCE = "performance"
    EFFICIENCY = "efficiency"

class WorkloadType(Enum):
    """Types of workloads for resource allocation"""
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"

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
        
        # Initialize dynamic resource tracking
        self.last_resource_check = 0
        self.resource_check_interval = 5  # seconds
        self.current_load = self._get_system_load()
        self.current_workload_type = self._determine_workload_type()
    
    def _get_system_load(self) -> Dict[str, float]:
        """Get current system resource load"""
        # Get CPU and memory load
        cpu_load = psutil.cpu_percent(interval=0.1) / 100.0
        memory_load = psutil.virtual_memory().percent / 100.0
        
        # Get disk I/O load - this is platform-dependent
        # We'll use a simple approximation based on available disk counters
        disk_io_load = 0.0
        try:
            # Different platforms have different disk I/O counter attributes
            # We'll try to get read/write counts as a generic measure
            disk_counters = psutil.disk_io_counters(perdisk=True)
            if disk_counters:
                # Calculate total read/write operations across all disks
                total_ops = sum(
                    (getattr(disk, 'read_count', 0) + getattr(disk, 'write_count', 0))
                    for disk in disk_counters.values()
                )
                # Normalize to a 0-1 scale (assuming 10,000 ops is high load)
                # This is a rough approximation
                disk_io_load = min(1.0, total_ops / 10000.0)
        except (AttributeError, ZeroDivisionError):
            # Fallback if disk counters aren't available
            disk_io_load = 0.0
        
        return {
            "cpu": cpu_load,
            "memory": memory_load,
            "disk_io": disk_io_load,
        }
    
    def _determine_workload_type(self) -> WorkloadType:
        """Determine the current workload type based on system load"""
        load = self.current_load
        cpu_load = load["cpu"]
        memory_load = load["memory"]
        
        # Determine workload type based on CPU and memory usage
        if cpu_load > 0.7 or memory_load > 0.8:
            return WorkloadType.HEAVY
        elif cpu_load > 0.3 or memory_load > 0.5:
            return WorkloadType.MEDIUM
        else:
            return WorkloadType.LIGHT
    
    def update_resource_status(self) -> bool:
        """Update the resource status if needed and return True if updated"""
        current_time = time.time()
        
        # Always update on the first call
        if self.last_resource_check == 0:
            self.last_resource_check = current_time
            self.current_load = self._get_system_load()
            old_workload_type = self.current_workload_type
            self.current_workload_type = self._determine_workload_type()
            # Log if workload type changed
            if old_workload_type != self.current_workload_type:
                logger.debug(f"Workload type changed to {self.current_workload_type.value}")
            return True
        
        # Check if we need to update based on the interval
        if current_time - self.last_resource_check < self.resource_check_interval:
            return False
        
        self.last_resource_check = current_time
        self.current_load = self._get_system_load()
        new_workload_type = self._determine_workload_type()
        
        # Return True if workload type changed
        if new_workload_type != self.current_workload_type:
            self.current_workload_type = new_workload_type
            logger.debug(f"Workload type changed to {self.current_workload_type.value}")
            return True
        
        return False
    
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
        # Update resource status before running command
        self.update_resource_status()
        
        # Adjust priority based on workload
        nice_value = 0
        if self.current_workload_type == WorkloadType.HEAVY:
            # Lower priority on heavy system load
            nice_value = 15 if core_type == CoreType.EFFICIENCY else 5
        elif self.current_workload_type == WorkloadType.MEDIUM:
            nice_value = 10 if core_type == CoreType.EFFICIENCY else 0
        
        if sys.platform == "darwin":  # macOS
            if nice_value > 0:
                # Use nice for lower priority on macOS
                command = f"nice -n {nice_value} {command}"
            return os.system(command)
        else:  # Linux
            # Use taskset for CPU affinity on Linux
            cores = self.optimize_cores(core_type)
            # Dynamically adjust cores based on workload
            if self.current_workload_type == WorkloadType.HEAVY:
                # Use fewer cores when system is under heavy load
                cores = cores[:max(1, len(cores) // 2)]
            
            core_list = ",".join(map(str, cores))
            if nice_value > 0:
                return os.system(f"nice -n {nice_value} taskset -c {core_list} {command}")
            else:
                return os.system(f"taskset -c {core_list} {command}")
    
    def get_recommended_resource_limits(self) -> Dict[str, Union[int, float]]:
        """Get recommended resource limits based on current system state"""
        # Update resource status
        self.update_resource_status()
        
        # Get total system resources
        total_memory = psutil.virtual_memory().total
        total_cpus = psutil.cpu_count(logical=True)
        
        # Calculate available resources
        available_memory = psutil.virtual_memory().available
        available_cpu_percent = 100 - psutil.cpu_percent(interval=0.1)
        
        # Calculate recommended limits based on workload type
        if self.current_workload_type == WorkloadType.LIGHT:
            # Can use more resources when system load is light
            memory_limit = int(available_memory * 0.7)  # 70% of available memory
            cpu_limit = max(1, int(total_cpus * (available_cpu_percent / 100) * 0.7))
        elif self.current_workload_type == WorkloadType.MEDIUM:
            # Moderate resource usage
            memory_limit = int(available_memory * 0.5)  # 50% of available memory
            cpu_limit = max(1, int(total_cpus * (available_cpu_percent / 100) * 0.5))
        else:  # HEAVY
            # Conservative resource usage
            memory_limit = int(available_memory * 0.3)  # 30% of available memory
            cpu_limit = max(1, int(total_cpus * (available_cpu_percent / 100) * 0.3))
        
        # Ensure minimum values
        memory_limit = max(memory_limit, 256 * 1024 * 1024)  # Minimum 256MB
        cpu_limit = max(cpu_limit, 1)
        
        return {
            "memory_bytes": memory_limit,
            "cpus": cpu_limit,
            "io_weight": 50 if self.current_workload_type == WorkloadType.HEAVY else 100,
        }
    
    def cleanup_cache(self) -> None:
        """
        Clean up cache directory based on cache_limit_bytes.
        
        This method removes old cache files to keep the cache size
        under the configured limit. It also uses the content-addressable 
        cache system if available.
        """
        # Get resource status to ensure we have the latest metrics
        self.update_resource_status()
        
        try:
            # Import artifact_cache here to avoid circular imports
            from .artifact_cache import (
                get_vm_image_cache, 
                get_test_artifact_cache
            )
            
            # Check if the cache directory exists
            if not self.config.cache_dir.exists():
                return
            
            # Get the current cache size
            cache_size = sum(
                f.stat().st_size for f in self.config.cache_dir.glob('**/*')
                if f.is_file()
            )
            
            # If we're under the limit, no cleanup needed
            if cache_size <= self.config.cache_limit_bytes:
                return
            
            # If content-addressable cache is available, use it for cleanup
            vm_image_cache = get_vm_image_cache(self.config.cache_dir / "vm")
            test_artifact_cache = get_test_artifact_cache(self.config.cache_dir / "test")
            
            # Calculate how much space we need to free up
            bytes_to_free = cache_size - self.config.cache_limit_bytes
            bytes_freed = 0
            
            # Clean up VM images if needed (prioritize VM image cleanup)
            if bytes_freed < bytes_to_free:
                # Clean VM image cache with appropriate limit
                remaining_bytes_needed = bytes_to_free - bytes_freed
                vm_cache_limit = max(0, self.config.cache_limit_bytes // 2)
                vm_bytes_freed = vm_image_cache.cache.cleanup(vm_cache_limit)
                bytes_freed += vm_bytes_freed
            
            # Clean up test artifacts if needed
            if bytes_freed < bytes_to_free:
                # Clean test artifact cache with appropriate limit
                test_artifact_cache.cleanup_test_artifacts(max_age_days=7)
            
            # Fallback to traditional cleanup if needed
            if bytes_freed < bytes_to_free:
                self._traditional_cache_cleanup()
                
            logger.info(f"Cache cleaned up: freed {format_size(bytes_freed)}")
            
        except ImportError:
            # Fallback to traditional cleanup if artifact_cache module is not available
            self._traditional_cache_cleanup()
    
    def _traditional_cache_cleanup(self) -> None:
        """Traditional cache cleanup method as fallback."""
        try:
            # Check if the cache directory exists
            if not self.config.cache_dir.exists():
                return
            
            # Get all files in the cache directory with their modification time
            cache_files = [
                (f, f.stat().st_mtime) for f in self.config.cache_dir.glob('**/*')
                if f.is_file() and not f.name.startswith('.')
            ]
            
            # Sort by modification time (oldest first)
            cache_files.sort(key=lambda x: x[1])
            
            # Calculate total size
            total_size = sum(f.stat().st_size for f, _ in cache_files)
            
            # Remove files until we're under the limit
            for file_path, _ in cache_files:
                if total_size <= self.config.cache_limit_bytes:
                    break
                    
                # Get file size before removing
                file_size = file_path.stat().st_size
                
                # Remove the file
                try:
                    file_path.unlink()
                    total_size -= file_size
                    logger.debug(f"Removed cache file: {file_path}")
                except OSError as e:
                    logger.warning(f"Failed to remove cache file {file_path}: {e}")
                    
            logger.info(f"Cache cleanup complete. New size: {format_size(total_size)}")
            
        except Exception as e:
            logger.exception(f"Error cleaning up cache: {e}")
    
    def adaptive_cache_limit(self) -> int:
        """
        Dynamically adjust cache limit based on available disk space.
        
        Returns:
            int: Adjusted cache limit in bytes
        """
        # Get disk stats for the cache directory's disk
        disk_stats = psutil.disk_usage(str(self.config.cache_dir))
        
        # Base cache limit is 10% of total memory
        base_limit = self.config.cache_limit_bytes
        
        # If disk is getting full (>85% used), reduce cache limit
        if disk_stats.percent > 85:
            # Scale down cache limit based on how full the disk is
            scale_factor = max(0.1, (100 - disk_stats.percent) / 15)  # 1.0 at 85%, 0.1 at 100%
            return int(base_limit * scale_factor)
        
        # If disk has plenty of space, we can potentially use more cache
        # but never more than 20% of total memory
        total_memory = psutil.virtual_memory().total
        max_cache = int(total_memory * 0.2)
        
        # Only increase if disk is less than 70% full
        if disk_stats.percent < 70:
            scale_factor = min(2.0, 1.0 + (70 - disk_stats.percent) / 50)  # 1.0 at 70%, 2.0 at 20%
            return min(int(base_limit * scale_factor), max_cache)
        
        return base_limit


def get_resource_manager(cache_dir: Path) -> ResourceManager:
    """Get or create a resource manager for the specified cache directory"""
    # Create cache dir if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    return ResourceManager(cache_dir)
