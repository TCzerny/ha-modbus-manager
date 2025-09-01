# Language Policy

## 📝 Documentation Language Standards

**IMPORTANT**: All documentation and comments must be in **English**!

### ✅ Required English Content

- **Wiki Documentation**: All `.md` files in the `wiki/` directory
- **Code Comments**: All comments in Python files
- **Template Documentation**: Comments in YAML templates
- **README Files**: All README and documentation files
- **Git Commit Messages**: All commit messages
- **Issue Descriptions**: GitHub issues and discussions
- **API Documentation**: All API and developer documentation

### ❌ German Content (Not Allowed)

- ~~German wiki documentation~~
- ~~German code comments~~
- ~~German template comments~~
- ~~German README files~~
- ~~German commit messages~~

### 🎯 Exception: User Interface

The **user interface** (Home Assistant UI) can remain in German:
- Configuration flow labels
- Translation files (`translations/de.json`)
- User-facing error messages
- UI descriptions and help text

### 📋 Translation Files

Translation files should contain both languages:
- `translations/en.json` - English (primary)
- `translations/de.json` - German (secondary)

### 🔧 Code Comments

All Python code comments must be in English:

```python
# ✅ Correct - English comment
def create_aggregate_sensors(self, group_tag: str):
    """Create aggregate sensors for a specific group."""
    # Process each method
    for method in methods:
        # Create sensor with proper naming
        pass

# ❌ Wrong - German comment
def create_aggregate_sensors(self, group_tag: str):
    """Erstelle Aggregate-Sensoren für eine spezifische Gruppe."""
    # Verarbeite jede Methode
    for method in methods:
        # Erstelle Sensor mit korrektem Namen
        pass
```

### 📚 Documentation Structure

All documentation should follow this English structure:

```markdown
# Title in English

## Section in English

### Subsection in English

**Bold text** in English
*Italic text* in English
`Code examples` in English
```

### 🚀 Benefits of English Documentation

1. **International Accessibility**: Reaches global developer community
2. **GitHub Standards**: Aligns with GitHub best practices
3. **Professional Appearance**: Maintains professional project image
4. **Collaboration**: Enables international contributors
5. **Searchability**: Better search results in English

### 📞 Enforcement

- **Code Reviews**: All PRs checked for English compliance
- **Automated Checks**: Linting tools verify English comments
- **Documentation Reviews**: Wiki content reviewed for language
- **Commit Hooks**: Pre-commit hooks check commit messages

---

**Policy Version**: 1.0  
**Effective Date**: January 2025  
**Review Date**: March 2025
