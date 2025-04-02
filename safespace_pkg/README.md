# SafeSpace

SafeSpace is a comprehensive environment isolation and testing tool. It creates isolated testing environments with various safety features including network isolation, virtual machine environments, and comprehensive testing setups.

## Features

- **Environment Isolation**: Create isolated filesystem environments for testing
- **Network Isolation**: Create isolated network namespaces (Linux) or network controls (macOS)
- **VM Mode**: Spin up lightweight virtual machines for complete isolation
- **Comprehensive Testing Mode**: Generate testing environments with all necessary configurations
- **Resource Optimization**: Automatically allocate resources based on system capabilities
- **Cross-Platform Support**: Works on Linux and macOS

## Installation

### From PyPI (recommended):

```bash
pip install safespace
```

### With optional dependencies:

```bash
# For network isolation features
pip install safespace[network]

# For VM features
pip install safespace[vm]

# For development
pip install safespace[dev]
```

### From source:

```bash
git clone https://github.com/griffincancode/safespace.git
cd safespace
pip install -e .
```

## Usage

### Basic Usage

Create an isolated environment:

```bash
safespace
```

### Network Isolation

Create an environment with network isolation:

```bash
safespace --network
```

### VM Mode

Create an environment with a virtual machine:

```bash
safespace --vm
```

### Comprehensive Testing Mode

Create a comprehensive testing environment:

```bash
safespace --test
```

### Enhanced Mode

Create an enhanced development environment:

```bash
safespace --enhanced
```

### Internal Mode

Create/manage an internal testing environment:

```bash
safespace internal
```

### Cleanup

Clean up an environment:

```bash
safespace --cleanup
```

### Complete Removal (Foreclose)

Completely remove an environment:

```bash
safespace foreclose
```

## Configuration

SafeSpace can be configured with the following options:

- `--memory=SIZE`: Specify VM memory size (e.g., "2G")
- `--cpus=NUM`: Specify number of CPUs for VM
- `--disk=SIZE`: Specify VM disk size (e.g., "20G")

## Development

This package is currently under development. The core functionality has been implemented, but some advanced features are still in progress:

### Implemented Features
- Basic environment isolation and management
- Resource management and optimization
- Internal mode for creating persistent test environments
- Command-line interface with core commands
- Utility functions for working with files, directories, and processes

### In Progress
- Network isolation mode
- VM mode
- Comprehensive testing environment generators
- Platform-specific optimizations

### Contributing
Contributions are welcome! Here's how you can help:

1. **Run the tests**:
   ```bash
   pytest
   ```

2. **Build the package locally**:
   ```bash
   python -m build
   ```

3. **Install in development mode**:
   ```bash
   pip install -e .
   ```

4. **Areas that need help**:
   - Adding tests for the CLI
   - Implementing network isolation for macOS
   - Enhancing VM support
   - Improving documentation

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
