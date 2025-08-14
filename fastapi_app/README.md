# FastAPI Operator Console

FastAPI orchestrator for the Probable Spork video pipeline with HITL gates.

## Features

- **Job Management**: Create, monitor, and control pipeline jobs
- **HITL Gates**: Human-in-the-loop approval for critical stages
- **Real-time Events**: SSE streaming and polling endpoints
- **Security**: Bearer token authentication, rate limiting, and CORS controls
- **Asset Management**: Track and manage pipeline artifacts

## Security Features

### Authentication
- Bearer token required for all non-`/healthz` routes
- Token read from `ADMIN_TOKEN` environment variable or `conf/operator.yaml`
- Default token: `default-admin-token-change-me` (change in production!)

### Server Binding
- **Default**: Binds to `127.0.0.1` (local-only) for security
- **External**: Set `allow_external_bind: true` in config to enable `0.0.0.0` binding
- Explicit opt-in required for external access

### CORS (Cross-Origin Resource Sharing)
- **Disabled by default** for security
- Enable by setting `security.cors.enabled: true` in `conf/operator.yaml`
- Configure allowed origins, methods, and headers explicitly
- See `conf/operator.cors.example.yaml` for UI integration

### Rate Limiting
- **Job Creation**: Configurable limit per minute (default: 5)
- **API Requests**: Configurable limit per minute per client (default: 60)
- **Burst Protection**: Configurable burst size allowance
- **Health Endpoint**: Exempt from rate limiting

### Security Headers
- HSTS (HTTP Strict Transport Security)
- Content Security Policy (CSP)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY (configurable)
- X-XSS-Protection: 1; mode=block

## Quick Start

1. **Start the server**:
   ```bash
   make op-console
   ```

2. **Test security**:
   ```bash
   make test-security
   ```

3. **Enable CORS for UI** (optional):
   ```bash
   # Copy and modify the example config
   cp conf/operator.cors.example.yaml conf/operator.yaml
   # Edit to customize CORS settings
   ```

## Configuration

Edit `conf/operator.yaml` to customize:

- Server binding and port
- Security settings and rate limits
- CORS configuration
- Gate requirements and timeouts
- Storage paths and retention

## API Endpoints

- `GET /healthz` - Health check (no auth required)
- `GET /api/v1/config/operator` - Get sanitized configuration
- `POST /api/v1/jobs` - Create new job
- `GET /api/v1/jobs` - List all jobs
- `GET /api/v1/jobs/{job_id}` - Get job details
- `POST /api/v1/jobs/{job_id}/approve` - Approve gate
- `POST /api/v1/jobs/{job_id}/reject` - Reject gate
- `GET /api/v1/jobs/{job_id}/events/stream` - SSE event stream

## Security Best Practices

1. **Change Default Token**: Set `ADMIN_TOKEN` environment variable
2. **Local Binding**: Use `127.0.0.1` unless external access is required
3. **CORS Restriction**: Only enable CORS for trusted origins
4. **Rate Limiting**: Adjust limits based on expected usage
5. **Monitor Logs**: Watch for authentication failures and rate limit hits

## Troubleshooting

### CORS Issues
- Ensure CORS is enabled in `conf/operator.yaml`
- Check that your origin is in `allow_origins`
- Verify `allow_credentials` matches your needs

### Rate Limiting
- Check rate limit configuration in `conf/operator.yaml`
- Monitor logs for rate limit warnings
- Adjust limits if legitimate requests are blocked

### Binding Issues
- Verify `server.host` is set correctly
- Set `allow_external_bind: true` for `0.0.0.0` binding
- Check firewall settings for external access
