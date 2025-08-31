# Cursor Background Agent Configuration

This directory contains configuration for Cursor background agents that work on this repository.

## Environment Setup

The `environment.json` file configures the Ubuntu-based VM environment with:

- **System Dependencies**: Python 3, FFmpeg, build tools, SQLite
- **Python Environment**: Virtual environment with project dependencies
- **Health Check**: Automatic environment validation

## Background Agent Tasks

Two background agents are configured to work on parallel tracks:

- **Agent 1** (`bg_agent1.md`): Data Integration & Testing Track
- **Agent 2** (`bg_agent2.md`): Content Generation Track

## Important Constraints

Background agents operate in isolated Ubuntu VMs without:
- Ollama service (no LLM access)
- whisper.cpp binary (audio processing unavailable)
- Live API keys (external services will fail)
- macOS-specific tools or paths

All agents are designed to work with graceful degradation and focus on:
- Code logic and structure improvements
- Error handling and fallback mechanisms
- DRY_RUN functionality testing
- File-based operations and validation

## Usage

1. Ensure your GitHub repository has read-write access configured
2. Start background agents from Cursor IDE
3. Agents will automatically clone the repo and set up the environment
4. Each agent will work on their assigned track and push changes to separate branches
