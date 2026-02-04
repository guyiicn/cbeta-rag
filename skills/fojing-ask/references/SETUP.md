# Fojing-Ask Skill Setup Guide

## Overview
The fojing-ask skill provides access to the CBETA (Chinese Buddhist Electronic Text Association) RAG API for searching Buddhist scriptures and texts.

## Configuration

### Step 1: Create Configuration Directory
```bash
mkdir -p ~/.config/cbeta-rag
```

### Step 2: Create Configuration File
Create `~/.config/cbeta-rag/config.json` with the following content:

```json
{
  "api_url": "http://192.168.50.12:8000",
  "api_key": "cbeta-rag-secret-key-2024",
  "default_top_k": 5
}
```

### Configuration Fields

| Field | Description | Example |
|-------|-------------|---------|
| `api_url` | Base URL of the CBETA RAG API server | `http://192.168.50.12:8000` |
| `api_key` | Authentication key for API access | `cbeta-rag-secret-key-2024` |
| `default_top_k` | Default number of search results to return | `5` |

### Step 3: Verify Configuration
Test your setup with the verification command:

```bash
python3 ~/.claude/skills/fojing-ask/scripts/fojing_ask.py search "金刚经"
```

Expected output: Search results from the CBETA database with relevant Buddhist texts.

## API Server Details

- **Host**: Jetson at 192.168.50.12
- **Port**: 8000
- **Protocol**: HTTP
- **Status**: Ensure the API server is running before using the skill

## Troubleshooting

### Connection Refused
**Problem**: `Connection refused` error when running verification command

**Solution**:
1. Verify the API server is running on the Jetson device
2. Check network connectivity: `ping 192.168.50.12`
3. Verify the port is accessible: `curl http://192.168.50.12:8000/health`

### Authentication Failed
**Problem**: `401 Unauthorized` or authentication error

**Solution**:
1. Verify the `api_key` in `~/.config/cbeta-rag/config.json` is correct
2. Check that the key matches the server's expected value
3. Ensure the config file has proper JSON formatting

### Invalid Configuration
**Problem**: `Config file not found` or parsing errors

**Solution**:
1. Verify the config file exists: `cat ~/.config/cbeta-rag/config.json`
2. Validate JSON syntax using a JSON validator
3. Ensure file permissions allow reading: `chmod 644 ~/.config/cbeta-rag/config.json`

### No Search Results
**Problem**: Search returns empty results

**Solution**:
1. Verify the search query is valid Chinese text
2. Check that `default_top_k` is set to a reasonable value (1-20)
3. Ensure the API server has the CBETA database loaded

## Security Notes

- **Never commit** `~/.config/cbeta-rag/config.json` to version control
- **Keep API keys private** - do not share the config file
- **Use environment variables** for sensitive data in production environments
- **Rotate API keys** periodically for security

## Next Steps

1. Ensure the CBETA RAG API server is running on the Jetson device
2. Create the configuration file with your API credentials
3. Run the verification command to confirm connectivity
4. Use the fojing-ask skill in Claude to search Buddhist texts

## Support

For issues or questions:
- Check the troubleshooting section above
- Verify API server status and connectivity
- Review configuration file format and permissions
- Consult the skill's main documentation
