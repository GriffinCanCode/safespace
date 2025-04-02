# SafeSpace Usage Examples

## Basic Usage

Create a simple safe environment:

```bash
safespace
```

## Network Isolation

Create an environment with network isolation:

```bash
safespace -n
```

## VM Mode

Create an environment with virtual machine isolation:

```bash
safespace -v --memory 4G --cpus 2 --disk 20G
```

## Comprehensive Testing

Create an environment with comprehensive testing tools:

```bash
safespace --test
```

## Enhanced Development

Create an environment with enhanced development features:

```bash
safespace --enhanced
```

## Internal Mode

Create or manage an internal environment:

```bash
safespace internal
```

Clean up the internal environment:

```bash
safespace internal --cleanup
```

## Persistent Environments

Create a persistent environment that can be recalled across sessions:

```bash
safespace --persistent --name my-test-env
```

List all saved persistent environments:

```bash
safespace recall --list
```

Recall a specific environment by name:

```bash
safespace recall --name my-test-env
```

Recall a specific environment by ID:

```bash
safespace recall --id 3a7c8f9e-1b2d-4e5f-6g7h-8i9j0k1l2m3n
```

Delete a persistent environment:

```bash
safespace recall --name my-test-env --delete
```

Create a persistent environment with network isolation and enhanced testing features:

```bash
safespace --persistent --name network-test-env -n --test
```

## Settings Management

List all settings:

```bash
safespace settings list
```

Update a setting:

```bash
safespace settings set vm default_memory 4G
```

Reset settings to defaults:

```bash
safespace settings reset
``` 