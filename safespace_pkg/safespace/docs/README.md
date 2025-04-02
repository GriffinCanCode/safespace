# SafeSpace Documentation

This directory contains documentation for the SafeSpace package.

## Structure

- `documentation.json`: The main documentation file in JSON format. This file contains all information about SafeSpace features, functions, and templates.
- `documentation_cli.py`: CLI module for displaying the documentation in a readable format.
- `README.md`: This file.

## Using the Documentation

The documentation can be accessed through the CLI using the `--wordspace` flag:

```bash
# Show the main documentation menu
safespace --wordspace

# Show a specific section
safespace --wordspace-section <section_id>

# Show the documentation as a tree
safespace --wordspace-tree
```

Available section IDs:
- `core-concepts`: Core concepts of SafeSpace
- `templates`: Environment templates
- `features`: Features of SafeSpace
- `commands`: Available commands
- `environment-management`: Environment management
- `advanced-usage`: Advanced usage
- `troubleshooting`: Troubleshooting

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
      "subsections": [
        {
          "title": "Subsection Title",
          "id": "subsection-id",
          "content": "Subsection content",
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
5. Update the section IDs in this README if you add or change sections 