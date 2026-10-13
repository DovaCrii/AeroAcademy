{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash({{COMANDO_LINT}})",
      "Bash({{COMANDO_FORMAT_CHECK}})",
      "Bash({{COMANDO_PRUEBAS}} *)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Read(./private/**)",
      "Read(**/*.pem)",
      "Read(**/*.key)",
      "Read(**/*.pfx)",
      "Read(**/id_rsa*)"
    ]
  }
}
