# SafeSpace

A comprehensive environment isolation and testing tool that creates secure, isolated environments with configurable features.

<div align="center">

![SafeSpace](https://img.shields.io/badge/SafeSpace-Environment%20Isolation-blue)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

## 🔒 Core Features

| Feature | Description | Status |
|---------|-------------|--------|
| **Environment Isolation** | Create isolated filesystem environments | ✅ Implemented |
| **Resource Management** | Optimize resource allocation and caching | ✅ Implemented |
| **Template System** | Pre-configured environment templates | ✅ Implemented |
| **Network Isolation** | Create isolated network namespaces | ✅ Implemented |
| **VM Integration** | Lightweight virtual machines for complete isolation | ✅ Implemented |
| **Testing Framework** | Comprehensive testing environments | ✅ Implemented |

## 📋 Environment Template Types

<details>
<summary>Click to view available templates</summary>

| Template ID | Name | Description |
|-------------|------|-------------|
| `basic` | Basic Test | Basic testing environment with minimal configuration |
| `network` | Isolated Network | Environment with network isolation for testing network boundaries |
| `vm` | VM Based | Environment with VM support for isolated execution testing |
| `comprehensive` | Comprehensive | Full-featured environment with network isolation, VM, and enhanced testing |
| `development` | Enhanced Development | Environment optimized for development with IDE integration and tooling |
| `performance` | Performance Test | Environment configured for performance benchmarking and testing |

</details>

## 🚀 Installation

```bash
# From PyPI
pip install safespace

# With optional dependencies
pip install safespace[network]  # For network isolation features
pip install safespace[vm]       # For VM features
pip install safespace[dev]      # For development
```

## 💻 Usage

### Basic Usage

```bash
# Create a basic isolated environment
safespace

# Create with network isolation
safespace --network

# Create with VM support
safespace --vm

# Create with comprehensive testing
safespace --test

# Create with enhanced development features
safespace --enhanced
```

### Additional Configuration

```bash
# Configure VM resources
safespace --vm --memory=4G --cpus=4 --disk=20G

# Internal mode for persistent environments
safespace internal

# Clean up an environment
safespace --cleanup

# Completely remove an internal environment
safespace foreclose
```

## 🔄 Resource Management

SafeSpace includes a sophisticated resource manager that:

- Intelligently allocates performance and efficiency cores
- Manages cache size and cleanup
- Optimizes resource usage based on system capabilities

```mermaid
graph TD
    A[System Resources] --> B[Resource Manager]
    B --> C[Performance Cores]
    B --> D[Efficiency Cores]
    B --> E[Cache Management]
    C --> F[High-Priority Tasks]
    D --> G[Background Tasks]
    E --> H[Auto-Cleanup]
```

## 🏗️ Architecture

SafeSpace uses a modular architecture with the following components:

```mermaid
graph LR
    A[SafeEnvironment] --> B[NetworkIsolation]
    A --> C[VMManager]
    A --> D[TestEnvironment]
    A --> E[ResourceManager]
    F[Templates] --> A
```

## 🧪 Testing Features

Environments can be configured with comprehensive testing capabilities:

- Directory structure for tests, source code, and configuration
- Pre-configured testing tools (pytest, pytest-cov, pytest-benchmark)
- Code quality tools (black, isort, mypy, ruff)
- Security scanning (safety, bandit)

## 📦 Environment Features

### Directory Structure

```
safe_env/
├── cache/      # Cache directory
├── logs/       # Log files
├── data/       # Environment data
├── tmp/        # Temporary files
└── .env        # Environment variables
```

### Enhanced Development Environment

- IDE support (VS Code settings)
- Git hooks (pre-commit configuration)
- CI/CD workflows
- Development scripts

## 📄 License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
