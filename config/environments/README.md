# Environment Configurations

This directory contains environment-specific configuration files.

## 📋 Contents

- **env.hardware-optimized** - Hardware-optimized environment configuration
- **env.local** - Local development environment configuration

## 🎯 Purpose

These files provide:
- Environment-specific overrides for configuration
- Hardware-specific optimizations
- Local development settings
- Deployment-specific parameters

## 🔗 Related Documentation

- For deployment guidance, see [docs/deployment/](../../docs/deployment/)
- For development setup, see [docs/development/](../../docs/development/)
- For system architecture, see [docs/architecture/](../../docs/architecture/)

## 📝 Usage

- **env.hardware-optimized**: Use for production deployments with specific hardware requirements
- **env.local**: Use for local development and testing
- Copy these files to `.env` in the project root to apply them
- Modify settings according to your specific environment needs

## ⚠️ Security Note

These files may contain sensitive information. Ensure they are not committed to version control.
