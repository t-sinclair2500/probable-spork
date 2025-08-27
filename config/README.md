# Configuration

This directory contains configuration files and environment-specific settings.

## 📋 Contents

### [environments/](./environments/)
Environment-specific configuration files.

- **env.hardware-optimized** - Hardware-optimized environment configuration
- **env.local** - Local development environment configuration

### Configuration Files
- **global.yaml** - Main system configuration
- **blog.yaml** - Blog-specific configuration
- **brief.yaml** - Brief and content configuration
- **render.yaml** - Rendering and output configuration
- **sources.yaml** - Data source configuration
- **tts.yaml** - Text-to-speech configuration
- **ui.yaml** - User interface configuration

## 🎯 Purpose

These files provide:
- System-wide configuration settings
- Environment-specific overrides
- Feature toggles and parameters
- Integration credentials and endpoints

## 🔗 Related Documentation

- For deployment guidance, see [docs/deployment/](../docs/deployment/)
- For development setup, see [docs/development/](../docs/development/)
- For system architecture, see [docs/architecture/](../docs/architecture/)

## 📝 Usage

- Copy `.example` files to create your configuration
- Modify settings according to your environment
- Keep sensitive information in `.env` files (not committed to git)
- Use environment-specific files for different deployment scenarios
