# Contributing to Modbus Manager

Thank you for your interest in contributing to Modbus Manager! This document provides guidelines and information for contributors.

## 🚀 Development Setup

### Prerequisites
- Python 3.9+
- Home Assistant development environment
- Git

### Local Development
1. **Clone the repository**:
   ```bash
   git clone https://github.com/tczerny/ha-modbus-manager.git
   cd ha-modbus-manager
   ```

2. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Setup Home Assistant development environment**:
   ```bash
   python -m pip install homeassistant
   ```

## 🏗️ Architecture Overview

### Core Components
- **`__init__.py`**: Main integration setup and hub management
- **`config_flow.py`**: Configuration UI and validation
- **`sensor.py`**: Sensor entity implementation
- **`number.py`**: Number entity implementation (read/write)
- **`select.py`**: Select entity implementation (read/write)
- **`switch.py`**: Switch entity implementation (read/write)
- **`binary_sensor.py`**: Binary sensor implementation
- **`button.py`**: Button entity implementation
- **`text.py`**: Text entity implementation (read/write)
- **`aggregates.py`**: Aggregation and group management
- **`template_loader.py`**: YAML template loading and validation
- **`register_optimizer.py`**: Register reading optimization
- **`performance_monitor.py`**: Performance monitoring and metrics

### Key Principles
- **Use Standard Home Assistant APIs**: Always prefer standard HA functions over custom implementations
- **No Custom Modbus Implementation**: Leverage the built-in Home Assistant Modbus integration
- **Template-Based**: All device configurations are defined in YAML templates
- **Performance First**: Optimize register reading and monitor performance

## 📝 Code Style

### Python
- Follow PEP 8 guidelines
- Use type hints where possible
- Document all public functions and classes
- Keep functions focused and single-purpose

### YAML Templates
- Use consistent indentation (2 spaces)
- Include all required fields
- Provide meaningful default values
- Document complex configurations

### Error Handling
- Use try-catch blocks for external operations
- Log errors with context information
- Provide user-friendly error messages
- Implement graceful degradation

## 🧪 Testing

### Manual Testing
1. **Install in Home Assistant**:
   - Copy files to `custom_components/modbus_manager/`
   - Restart Home Assistant
   - Add integration through UI

2. **Test with Real Devices**:
   - Use provided templates (Sungrow, Compleo EBox)
   - Test all entity types (sensor, number, select, switch, etc.)
   - Verify aggregation functionality

### Automated Testing
- Run linting: `python -m flake8 custom_components/modbus_manager/`
- Check type hints: `python -m mypy custom_components/modbus_manager/`
- Validate YAML: `python -c "import yaml; yaml.safe_load(open('template.yaml'))"`

## 📋 Pull Request Process

### Before Submitting
1. **Test your changes** thoroughly
2. **Update documentation** if needed
3. **Follow the coding style** guidelines
4. **Ensure no breaking changes** unless documented

### PR Requirements
- **Clear description** of changes and purpose
- **Screenshots** for UI changes
- **Test results** from real devices
- **Documentation updates** if applicable

### Review Process
- All PRs require review
- Maintainers will test with real devices
- Performance impact will be evaluated
- Breaking changes require major version bump

## 🔧 Adding New Features

### Entity Types
1. **Create entity file** (e.g., `new_entity.py`)
2. **Implement required methods** from base entity class
3. **Add to PLATFORMS** in `const.py`
4. **Register in `__init__.py`**
5. **Update template loader** if new fields needed
6. **Add to documentation**

### Template Features
1. **Define new fields** in `template_loader.py`
2. **Update validation** logic
3. **Add default values** in `OPTIONAL_FIELDS`
4. **Create example templates**
5. **Update README.md**

### Performance Features
1. **Implement in separate module** (e.g., `new_optimizer.py`)
2. **Add configuration options** to config flow
3. **Integrate with performance monitor**
4. **Document performance benefits**

## 🐛 Bug Reports

### Required Information
- **Home Assistant version**
- **Modbus Manager version**
- **Device template used**
- **Error messages and logs**
- **Steps to reproduce**
- **Expected vs actual behavior**

### Logs
Enable debug logging for Modbus Manager:
```yaml
logger:
  default: info
  logs:
    custom_components.modbus_manager: debug
```

## 📚 Documentation

### Code Documentation
- Use docstrings for all public functions
- Include parameter descriptions
- Document return values and exceptions
- Provide usage examples

### User Documentation
- Keep README.md up to date
- Include configuration examples
- Document troubleshooting steps
- Add screenshots for UI features

## 🤝 Community Guidelines

### Communication
- Be respectful and constructive
- Help other contributors
- Share knowledge and experiences
- Report issues promptly

### Recognition
- Contributors will be credited in releases
- Significant contributions may receive maintainer status
- Community feedback is valued and appreciated

## 📞 Getting Help

### Questions and Discussion
- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Home Assistant Community**: For integration-specific help

### Development Support
- **Code Review**: Request review for complex changes
- **Architecture Discussion**: Discuss major design decisions
- **Performance Optimization**: Get help with optimization strategies

## 🎯 Roadmap

### Short Term
- Additional device templates
- Enhanced error handling
- Performance optimizations

### Long Term
- Advanced aggregation features
- Template validation improvements
- Integration with other HA components

---

Thank you for contributing to Modbus Manager! Your contributions help make this integration better for everyone in the Home Assistant community.
