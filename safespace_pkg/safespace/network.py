"""
Network Isolation Module for SafeSpace

This module provides network isolation functionality for the SafeSpace package.
It creates isolated network namespaces and configures virtual interfaces for
complete network isolation.
"""

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from .utils import log_status, Colors
from .settings import get_settings

logger = logging.getLogger(__name__)

class NetworkIsolation:
    """Manages network isolation features for SafeSpace environments."""

    def __init__(self, env_dir: Path, sudo_password: Optional[str] = None):
        """
        Initialize NetworkIsolation.

        Args:
            env_dir: Path to the environment directory
            sudo_password: Optional sudo password for privileged operations
        """
        # Get settings
        settings = get_settings()
        network_settings = settings.network
        
        self.env_dir = env_dir
        self.sudo_password = sudo_password
        self.namespace_name = "safespace_net"
        self.veth_host = "veth0"
        self.veth_namespace = "veth1"
        self.is_linux = platform.system() == "Linux"
        self.is_macos = platform.system() == "Darwin"
        
        # Apply settings
        self.network_cidr = network_settings.default_subnet
        self.create_tap_device = network_settings.create_tap_device
        self.enable_nat = network_settings.enable_nat
        
        # Network conditions simulation settings
        self.simulate_conditions = network_settings.simulate_conditions
        self.latency = network_settings.default_latency
        self.jitter = network_settings.default_jitter
        self.packet_loss = network_settings.default_packet_loss
        self.packet_corruption = network_settings.default_packet_corruption
        self.packet_reordering = network_settings.default_packet_reordering
        self.bandwidth = network_settings.default_bandwidth
        self.current_conditions_active = False
        
        # Extract network components from CIDR
        network_parts = self.network_cidr.split('/')
        base_ip = network_parts[0].rsplit('.', 1)[0]
        
        # Platform-specific settings
        if self.is_macos:
            self.tap_interface = "utun7"  # macOS uses utun interfaces
        else:
            self.tap_interface = "tap0"
            
        self.host_ip = f"{base_ip}.1"
        self.namespace_ip = f"{base_ip}.2"
        self.tap_ip = f"{base_ip}.3"
        self.env_file = env_dir / ".env"
        
    def _sudo_cmd(self, cmd: List[str]) -> Tuple[int, str, str]:
        """
        Run a command with sudo privileges.

        Args:
            cmd: Command to run as a list of strings

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        logger.debug(f"Running sudo command: {' '.join(cmd)}")
        
        if not self.sudo_password:
            logger.error("No sudo password set")
            return 1, "", "No sudo password provided"
            
        full_cmd = ["sudo", "-S"] + cmd
        
        try:
            process = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=f"{self.sudo_password}\n")
            return process.returncode, stdout, stderr
        except Exception as e:
            logger.error(f"Error running sudo command: {e}")
            return 1, "", str(e)

    def setup(self) -> bool:
        """
        Set up network isolation.

        Returns:
            bool: True if setup was successful, False otherwise
        """
        log_status("Setting up network isolation...", Colors.YELLOW)
        
        if self.is_linux:
            return self._setup_linux()
        elif self.is_macos:
            return self._setup_macos()
        else:
            log_status("Network isolation is only supported on Linux and macOS", Colors.RED)
            return False

    def _setup_linux(self) -> bool:
        """
        Set up network isolation on Linux using network namespaces.

        Returns:
            bool: True if setup was successful, False otherwise
        """
        # Create a new network namespace
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "add", self.namespace_name])
        if rc != 0:
            logger.error(f"Failed to create network namespace: {stderr}")
            return False
            
        # Create virtual interface pair
        rc, _, stderr = self._sudo_cmd(["ip", "link", "add", self.veth_host, "type", "veth", "peer", "name", self.veth_namespace])
        if rc != 0:
            logger.error(f"Failed to create virtual interfaces: {stderr}")
            return False
            
        # Move veth1 to namespace
        rc, _, stderr = self._sudo_cmd(["ip", "link", "set", self.veth_namespace, "netns", self.namespace_name])
        if rc != 0:
            logger.error(f"Failed to move interface to namespace: {stderr}")
            return False
            
        # Configure interfaces
        rc, _, stderr = self._sudo_cmd(["ip", "addr", "add", f"{self.host_ip}/24", "dev", self.veth_host])
        if rc != 0:
            logger.error(f"Failed to configure host interface: {stderr}")
            return False
            
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.namespace_name, "ip", "addr", "add", f"{self.namespace_ip}/24", "dev", self.veth_namespace])
        if rc != 0:
            logger.error(f"Failed to configure namespace interface: {stderr}")
            return False
            
        # Bring up interfaces
        rc, _, stderr = self._sudo_cmd(["ip", "link", "set", self.veth_host, "up"])
        if rc != 0:
            logger.error(f"Failed to bring up host interface: {stderr}")
            return False
            
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.namespace_name, "ip", "link", "set", self.veth_namespace, "up"])
        if rc != 0:
            logger.error(f"Failed to bring up namespace interface: {stderr}")
            return False
            
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.namespace_name, "ip", "link", "set", "lo", "up"])
        if rc != 0:
            logger.error(f"Failed to bring up namespace loopback: {stderr}")
            return False
            
        # Setup NAT for internet access
        rc, _, stderr = self._sudo_cmd(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", self.network_cidr, "-j", "MASQUERADE"])
        if rc != 0:
            logger.error(f"Failed to setup NAT: {stderr}")
            return False
            
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.namespace_name, "ip", "route", "add", "default", "via", self.host_ip])
        if rc != 0:
            logger.error(f"Failed to add default route: {stderr}")
            return False
            
        # Enable IP forwarding
        rc, _, stderr = self._sudo_cmd(["sh", "-c", f"echo 1 > /proc/sys/net/ipv4/ip_forward"])
        if rc != 0:
            logger.error(f"Failed to enable IP forwarding: {stderr}")
            return False
            
        # Store network namespace info
        self._update_env_file({
            "NETWORK_NAMESPACE": self.namespace_name,
            "VETH_HOST": self.veth_host,
            "VETH_NAMESPACE": self.veth_namespace
        })
            
        log_status("Network isolation configured successfully", Colors.GREEN)
        return True

    def _setup_macos(self) -> bool:
        """
        Set up network isolation on macOS using pf and dnctl.

        Returns:
            bool: True if setup was successful, False otherwise
        """
        # On macOS, we'll use a different approach
        # Instead of trying to configure utun interfaces which require special privileges,
        # we'll create a local loopback alias and use pf to restrict traffic
        
        # Create a loopback alias
        rc, _, stderr = self._sudo_cmd(["ifconfig", "lo0", "alias", self.tap_ip, "netmask", "255.255.255.0"])
        if rc != 0:
            logger.error(f"Failed to create loopback alias: {stderr}")
            return False
            
        # Create a temporary pf.conf file
        pf_conf_path = self.env_dir / "pf.conf"
        with open(pf_conf_path, "w") as f:
            f.write(f"# SafeSpace network isolation\n")
            f.write(f"# Block all outgoing connections from our virtual environment\n")
            f.write(f"block out quick from {self.tap_ip} to any\n")
            f.write(f"# Allow connections to our loopback subnet\n")
            f.write(f"pass out quick from {self.tap_ip} to {self.network_cidr}\n")
            f.write(f"pass in quick from {self.network_cidr} to {self.tap_ip}\n")
        
        # Load the pf rules
        rc, _, stderr = self._sudo_cmd(["pfctl", "-f", str(pf_conf_path)])
        if rc != 0:
            logger.error(f"Failed to load pf rules: {stderr}")
            return False
            
        # Enable pf if not already enabled
        self._sudo_cmd(["pfctl", "-e"])
            
        # Store network configuration info
        self._update_env_file({
            "LOOPBACK_ALIAS": self.tap_ip,
            "PF_CONF_PATH": str(pf_conf_path)
        })
            
        log_status("Network isolation on macOS configured successfully", Colors.GREEN)
        return True

    def cleanup(self) -> bool:
        """
        Clean up network isolation.

        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        log_status("Cleaning up network isolation...", Colors.YELLOW)
        
        if self.is_linux:
            return self._cleanup_linux()
        elif self.is_macos:
            return self._cleanup_macos()
        else:
            return False

    def _cleanup_linux(self) -> bool:
        """
        Clean up network isolation on Linux.

        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        # Remove NAT rule
        self._sudo_cmd(["iptables", "-t", "nat", "-D", "POSTROUTING", "-s", self.network_cidr, "-j", "MASQUERADE"])
        
        # Remove virtual interfaces and namespace
        self._sudo_cmd(["ip", "link", "delete", self.veth_host])
        self._sudo_cmd(["ip", "netns", "delete", self.namespace_name])
        
        log_status("Network isolation cleaned up", Colors.GREEN)
        return True

    def _cleanup_macos(self) -> bool:
        """
        Clean up network isolation on macOS.

        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        # Remove the loopback alias
        self._sudo_cmd(["ifconfig", "lo0", "-alias", self.tap_ip])
        
        # Disable pf rules related to our network
        pf_conf_path = self.env_dir / "pf.conf"
        if pf_conf_path.exists():
            # Create an empty ruleset for cleanup
            with open(pf_conf_path, "w") as f:
                f.write("# Empty ruleset for cleanup\n")
                
            # Load the empty ruleset
            self._sudo_cmd(["pfctl", "-f", str(pf_conf_path)])
            
            # Remove the file
            pf_conf_path.unlink()
        
        log_status("Network isolation on macOS cleaned up", Colors.GREEN)
        return True

    def run_command(self, cmd: List[str]) -> Tuple[int, str, str]:
        """
        Run a command inside the isolated network namespace.

        Args:
            cmd: Command to run as a list of strings

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if self.is_linux:
            full_cmd = ["ip", "netns", "exec", self.namespace_name] + cmd
            return self._sudo_cmd(full_cmd)
        elif self.is_macos:
            # On macOS, we use environment variables to direct network traffic
            # to our loopback alias
            env_cmd = [
                "env",
                f"SAFESPACE_IP={self.tap_ip}",
                f"SAFESPACE_NETWORK={self.network_cidr}",
                # Force standard utilities to use our loopback alias
                "HOSTALIASES=" + str(self.env_dir / "hosts")
            ] + cmd
            
            # Create HOSTALIASES file to redirect hostnames to our loopback
            with open(self.env_dir / "hosts", "w") as f:
                f.write(f"# SafeSpace hosts file\n")
                f.write(f"localhost {self.tap_ip}\n")
                
            return self._sudo_cmd(env_cmd)
        else:
            logger.error("Running commands in network isolation is only supported on Linux and macOS")
            return 1, "", "Not supported on this platform"

    def _update_env_file(self, env_vars: Dict[str, str]) -> None:
        """
        Update environment file with new variables.

        Args:
            env_vars: Dictionary of environment variables to add
        """
        try:
            with open(self.env_file, "a") as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
        except Exception as e:
            logger.error(f"Failed to update environment file: {e}")

    def setup_network_conditions(self, 
                                latency: Optional[str] = None, 
                                jitter: Optional[str] = None,
                                packet_loss: Optional[float] = None,
                                packet_corruption: Optional[float] = None,
                                packet_reordering: Optional[float] = None,
                                bandwidth: Optional[str] = None) -> bool:
        """
        Set up network condition simulation using traffic control.
        
        Args:
            latency: Added latency (e.g., "100ms")
            jitter: Jitter for latency (e.g., "10ms")
            packet_loss: Packet loss as percentage (0-100)
            packet_corruption: Packet corruption as percentage (0-100)
            packet_reordering: Packet reordering as percentage (0-100)
            bandwidth: Bandwidth limit (e.g., "1mbit")
            
        Returns:
            bool: True if setup was successful, False otherwise
        """
        # Update parameters if provided
        if latency is not None:
            self.latency = latency
        if jitter is not None:
            self.jitter = jitter
        if packet_loss is not None:
            self.packet_loss = packet_loss
        if packet_corruption is not None:
            self.packet_corruption = packet_corruption
        if packet_reordering is not None:
            self.packet_reordering = packet_reordering
        if bandwidth is not None:
            self.bandwidth = bandwidth
            
        # Enable simulation
        self.simulate_conditions = True
        
        log_status(f"Setting up network condition simulation...", Colors.YELLOW)
        
        # Clean up any existing conditions first
        self.reset_network_conditions()
        
        if self.is_linux:
            return self._setup_linux_network_conditions()
        elif self.is_macos:
            return self._setup_macos_network_conditions()
        else:
            log_status("Network condition simulation is only supported on Linux and macOS", Colors.RED)
            return False
            
    def _setup_linux_network_conditions(self) -> bool:
        """
        Set up network condition simulation on Linux using tc.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        # Determine which interface to apply conditions to
        target_interface = self.veth_namespace
        
        # Create commands to set up network conditions
        # First, add the qdisc (tc requires this before adding rules)
        rc, _, stderr = self._sudo_cmd([
            "ip", "netns", "exec", self.namespace_name, 
            "tc", "qdisc", "add", "dev", target_interface, "root", "netem"
        ])
        
        if rc != 0:
            logger.error(f"Failed to set up tc qdisc: {stderr}")
            return False
            
        # Now, apply conditions (build the command based on what's enabled)
        conditions_cmd = ["ip", "netns", "exec", self.namespace_name, "tc", "qdisc", "change", 
                          "dev", target_interface, "root", "netem"]
        
        # Add latency and jitter if set
        if self.latency:
            conditions_cmd.extend(["delay", self.latency])
            if self.jitter:
                conditions_cmd.extend([self.jitter])
                
        # Add packet loss if set
        if self.packet_loss > 0:
            conditions_cmd.extend(["loss", f"{self.packet_loss}%"])
            
        # Add corruption if set
        if self.packet_corruption > 0:
            conditions_cmd.extend(["corrupt", f"{self.packet_corruption}%"])
            
        # Add reordering if set
        if self.packet_reordering > 0:
            conditions_cmd.extend(["reorder", f"{self.packet_reordering}%"])
            
        # Run the conditions command
        rc, _, stderr = self._sudo_cmd(conditions_cmd)
        if rc != 0:
            logger.error(f"Failed to set up network conditions: {stderr}")
            return False
            
        # If bandwidth is set, add a rate limit
        if self.bandwidth:
            # We need to use tbf (token bucket filter) for bandwidth limiting
            # First remove the existing qdisc
            self._sudo_cmd([
                "ip", "netns", "exec", self.namespace_name, 
                "tc", "qdisc", "del", "dev", target_interface, "root"
            ])
            
            # Add tbf with the specified bandwidth
            rc, _, stderr = self._sudo_cmd([
                "ip", "netns", "exec", self.namespace_name, 
                "tc", "qdisc", "add", "dev", target_interface, "root", "tbf", 
                "rate", self.bandwidth, "burst", "32kbit", "latency", "400ms"
            ])
            
            if rc != 0:
                logger.error(f"Failed to set up bandwidth limit: {stderr}")
                return False
        
        self.current_conditions_active = True
        log_status(f"Network conditions applied: latency={self.latency}, jitter={self.jitter}, " +
                  f"packet_loss={self.packet_loss}%, bandwidth={self.bandwidth}", Colors.GREEN)
        return True
    
    def _setup_macos_network_conditions(self) -> bool:
        """
        Set up network condition simulation on macOS using pfctl and dummynet.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        # macOS uses dummynet for traffic shaping
        # First, check if dummynet is loaded
        rc, stdout, _ = self._sudo_cmd(["kldstat", "-m", "dummynet"])
        if "dummynet" not in stdout:
            # Load dummynet module
            rc, _, stderr = self._sudo_cmd(["kldload", "dummynet"])
            if rc != 0:
                logger.error(f"Failed to load dummynet module: {stderr}")
                return False
        
        # Create a pipe for traffic shaping
        rc, _, stderr = self._sudo_cmd(["dnctl", "pipe", "1", "config"])
        if rc != 0:
            logger.error(f"Failed to create dummynet pipe: {stderr}")
            return False
        
        # Configure pipe with network conditions
        pipe_cmd = ["dnctl", "pipe", "1", "config"]
        
        # Add bandwidth limit if set
        if self.bandwidth:
            pipe_cmd.extend(["bw", self.bandwidth])
            
        # Add latency if set
        if self.latency:
            # Convert ms to number
            latency_ms = int(self.latency.replace("ms", ""))
            pipe_cmd.extend(["delay", str(latency_ms)])
            
        # Add packet loss if set
        if self.packet_loss > 0:
            pipe_cmd.extend(["plr", str(self.packet_loss / 100.0)])  # dummynet uses 0-1 range
        
        # Run the pipe configuration command
        rc, _, stderr = self._sudo_cmd(pipe_cmd)
        if rc != 0:
            logger.error(f"Failed to configure dummynet pipe: {stderr}")
            return False
        
        # Create pf rule to direct traffic to the pipe
        pf_rule = f"dummynet out from {self.tap_ip} to any pipe 1\ndummynet in from any to {self.tap_ip} pipe 1"
        pf_file = self.env_dir / "pf_dummynet.conf"
        
        with open(pf_file, "w") as f:
            f.write(pf_rule)
        
        # Load the pf rule
        rc, _, stderr = self._sudo_cmd(["pfctl", "-f", str(pf_file)])
        if rc != 0:
            logger.error(f"Failed to load pf rules for dummynet: {stderr}")
            return False
        
        # Ensure pf is enabled
        self._sudo_cmd(["pfctl", "-e"])
        
        self.current_conditions_active = True
        log_status(f"Network conditions applied: latency={self.latency}, packet_loss={self.packet_loss}%, " +
                  f"bandwidth={self.bandwidth}", Colors.GREEN)
        return True
    
    def update_network_conditions(self, 
                                 latency: Optional[str] = None, 
                                 jitter: Optional[str] = None,
                                 packet_loss: Optional[float] = None,
                                 packet_corruption: Optional[float] = None,
                                 packet_reordering: Optional[float] = None,
                                 bandwidth: Optional[str] = None) -> bool:
        """
        Update existing network condition simulation parameters.
        
        Args:
            latency: Added latency (e.g., "100ms")
            jitter: Jitter for latency (e.g., "10ms")
            packet_loss: Packet loss as percentage (0-100)
            packet_corruption: Packet corruption as percentage (0-100)
            packet_reordering: Packet reordering as percentage (0-100)
            bandwidth: Bandwidth limit (e.g., "1mbit")
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        # Update parameters if provided
        if latency is not None:
            self.latency = latency
        if jitter is not None:
            self.jitter = jitter
        if packet_loss is not None:
            self.packet_loss = packet_loss
        if packet_corruption is not None:
            self.packet_corruption = packet_corruption
        if packet_reordering is not None:
            self.packet_reordering = packet_reordering
        if bandwidth is not None:
            self.bandwidth = bandwidth
        
        # If conditions are already active, reapply with new settings
        if self.current_conditions_active:
            return self.setup_network_conditions()
        else:
            log_status("No active network conditions to update. Use setup_network_conditions first.", Colors.YELLOW)
            return False
    
    def reset_network_conditions(self) -> bool:
        """
        Reset network conditions to normal operation (remove all simulated conditions).
        
        Returns:
            bool: True if reset was successful, False otherwise
        """
        if not self.current_conditions_active:
            logger.debug("No network conditions to reset")
            return True
            
        log_status("Resetting network conditions...", Colors.YELLOW)
        
        if self.is_linux:
            # Remove all tc qdiscs on the target interface
            rc, _, stderr = self._sudo_cmd([
                "ip", "netns", "exec", self.namespace_name, 
                "tc", "qdisc", "del", "dev", self.veth_namespace, "root"
            ])
            
            # It's okay if it fails because there might not be any qdiscs
            if rc != 0:
                logger.debug(f"No qdiscs to remove or error: {stderr}")
                
            # Add a default pfifo qdisc
            self._sudo_cmd([
                "ip", "netns", "exec", self.namespace_name, 
                "tc", "qdisc", "add", "dev", self.veth_namespace, "root", "pfifo"
            ])
            
        elif self.is_macos:
            # Delete the dummynet pipe
            self._sudo_cmd(["dnctl", "pipe", "1", "delete"])
            
            # Remove pf rules for dummynet
            pf_file = self.env_dir / "pf_dummynet.conf"
            if pf_file.exists():
                with open(pf_file, "w") as f:
                    f.write("# Empty ruleset for cleanup\n")
                    
                # Load the empty ruleset
                self._sudo_cmd(["pfctl", "-f", str(pf_file)])
                
                # Remove the file
                pf_file.unlink()
        
        self.current_conditions_active = False
        log_status("Network conditions reset to normal", Colors.GREEN)
        return True
        
    def get_current_network_conditions(self) -> Dict[str, Any]:
        """
        Get current network condition settings.
        
        Returns:
            Dict[str, Any]: Dictionary of current network conditions
        """
        return {
            "active": self.current_conditions_active,
            "simulate_conditions": self.simulate_conditions,
            "latency": self.latency,
            "jitter": self.jitter,
            "packet_loss": self.packet_loss,
            "packet_corruption": self.packet_corruption,
            "packet_reordering": self.packet_reordering,
            "bandwidth": self.bandwidth
        }
