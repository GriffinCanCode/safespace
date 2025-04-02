# SafeSpace Test Suite

This directory contains comprehensive tests for the SafeSpace package.

## Test Coverage

The test suite covers the following components:

- Core utility functions (`utils.py`)
- Resource management (`resource_manager.py`)
- Environment isolation (`environment.py`)
- Network isolation (`network.py`)
- VM management (`vm.py`)
- Testing environment (`testing.py`)
- Environment templates (`templates.py`)
- Integration tests across components

## Running Tests

### Basic Test Run

To run all tests:

```bash
python -m pytest
```

To run with verbose output:

```bash
python -m pytest -v
```

### Running Specific Tests

To run only the utility tests:

```bash
python -m pytest tests/test_safespace.py::TestUtils
```

To run a specific test:

```bash
python -m pytest tests/test_safespace.py::TestUtils::test_format_size
```

To run only the template tests:

```bash
python -m pytest tests/test_safespace.py::TestTemplates
```

### Testing with Coverage

To run tests with coverage report:

```bash
python -m pytest --cov=safespace
```

For a more detailed coverage report:

```bash
python -m pytest --cov=safespace --cov-report=term-missing
```

To generate HTML coverage report:

```bash
python -m pytest --cov=safespace --cov-report=html
```

## Test Categories

The test suite is organized into the following categories:

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test multiple components working together
- **Performance tests**: Test resource optimization and performance
- **Edge case tests**: Test boundary conditions and error handling
- **Template tests**: Test predefined environment templates

## Test Markers

The test suite uses the following markers:

- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.performance`: Performance tests
- `@pytest.mark.network`: Tests requiring network isolation
- `@pytest.mark.vm`: Tests requiring VM functionality
- `@pytest.mark.templates`: Tests for environment templates

To run only integration tests:

```bash
python -m pytest -m integration
```

## Fixtures

The following fixtures are available for testing:

- `temp_safe_environment`: Creates a temporary SafeSpace environment
- `mock_network_isolation`: Mocks network isolation functionality
- `mock_vm_manager`: Mocks VM manager functionality

## Extending the Test Suite

When adding new tests, please follow these guidelines:

1. Use appropriate markers for different test types
2. Use fixtures to set up and tear down test environments
3. Mock external system calls where possible
4. Test for edge cases and error conditions
5. Update the DEBUG_CHECKLIST at the top of the file if necessary

## Debug Checklist

The DEBUG_CHECKLIST in the test file contains a list of critical tests that verify the integrity of the codebase. If you're fixing a bug, make sure these tests pass after your changes. 