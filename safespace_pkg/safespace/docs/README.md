# SafeSpace Documentation

This directory contains documentation for the SafeSpace package.

## Structure

- `documentation.json`: The main documentation file in JSON format. This file contains all information about SafeSpace features, functions, and templates.
- `documentation_cli.py`: CLI module for displaying the documentation in a readable format.
- `README.md`: This file.

## Using the Documentation

The documentation can be accessed through the CLI using several options:

```bash
# Show the main documentation menu
safespace --wordspace

# Show a specific section
safespace --wordspace-section <section_id>

# Show a specific subsection within a section
safespace --wordspace-section <section_id> --wordspace-subsection <subsection_id>

# Show the documentation as a tree
safespace --wordspace-tree

# Use the interactive documentation browser
safespace --wordspace-interactive
```

### Interactive Mode

The interactive mode allows you to navigate through the documentation using keyboard commands:
- Enter a section ID to view that section
- Enter a subsection ID to view that subsection
- Press 'b' to go back to the previous page
- Press 't' to view the tree of all sections (from the main menu)
- Press 'q' to quit the interactive browser

### Navigation

The documentation now includes navigation links that help you move between sections and subsections. These navigation links appear at the bottom of each page and include:
- Previous (←): Navigate to the previous section or subsection
- Up (↑): Navigate to the parent section
- Next (→): Navigate to the next section or subsection

## Available Section IDs
- `core-concepts`: Core concepts of SafeSpace
- `templates`: Environment templates
- `features`: Features of SafeSpace
- `commands`: Available commands
- `environment-management`: Environment management
- `advanced-usage`: Advanced usage
- `troubleshooting`: Troubleshooting

## Available Subsection IDs

### Core Concepts
- `isolation-levels`: Different isolation levels provided by SafeSpace
- `directory-structure`: Structure of SafeSpace environments
- `resource-management`: How resources are managed
- `security-features`: Security features implemented in SafeSpace

### Templates
- `basic-test`: Basic testing template
- `isolated-network`: Network isolation template
- `vm-based`: VM-based template
- `container-based`: Container-based template
- `comprehensive`: Comprehensive template with all features
- `enhanced-dev`: Enhanced development environment template
- `performance-test`: Performance testing template

### Features
- `network-isolation`: Network isolation features
- `vm-isolation`: VM isolation features
- `container-isolation`: Container isolation features
- `comprehensive-testing`: Comprehensive testing features
- `enhanced-development`: Enhanced development features
- `health-monitoring`: Health monitoring features

### Commands
- `main-command`: Main SafeSpace command
- `internal-command`: Internal testing environment command
- `foreclose-command`: Environment removal command
- `vm-commands`: VM management commands
- `container-commands`: Container management commands

### Environment Management
- `creating-environments`: Creating environments
- `using-templates`: Using templates
- `configuring-environments`: Configuring environments
- `running-in-environments`: Running commands in environments
- `managing-resources`: Managing environment resources
- `cleaning-up-environments`: Cleaning up environments

### Advanced Usage
- `custom-templates`: Creating custom templates
- `ci-cd-integration`: Integrating with CI/CD pipelines
- `network-configuration`: Advanced network configuration
- `vm-configuration`: Advanced VM configuration
- `container-configuration`: Advanced container configuration

### Troubleshooting
- `permission-issues`: Resolving permission issues
- `vm-issues`: Resolving VM issues
- `container-issues`: Resolving container issues
- `network-isolation-issues`: Resolving network isolation issues
- `resource-issues`: Resolving resource management issues
- `debugging`: Debugging SafeSpace

## Updating the Documentation

To update the documentation, edit the `documentation.json` file. The file is structured as follows:

```json
{
  "name": "SafeSpace",
  "version": "current",
  "description": "SafeSpace is a tool that creates isolated testing environments with various safety features, allowing for secure testing and development.",
  "sections": [
    {
      "title": "Section Title",
      "id": "section-id",
      "content": "Section content",
      "navigation": {
        "previous": "previous-section-id",
        "next": "next-section-id"
      },
      "subsections": [
        {
          "title": "Subsection Title",
          "id": "subsection-id",
          "content": "Subsection content",
          "navigation": {
            "previous": "previous-subsection-id",
            "parent": "parent-section-id",
            "next": "next-subsection-id"
          },
          "parameters": {
            "parameter1": "Parameter description",
            "parameter2": "Parameter description"
          }
        }
      ]
    }
  ]
}
```

When updating the documentation, make sure to:
1. Maintain the JSON structure
2. Use descriptive titles and IDs
3. Provide detailed content
4. Include all relevant parameters
5. Update the navigation links to ensure proper flow
6. Update the section and subsection IDs in this README if you add or change sections 