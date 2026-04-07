Get-Content .env | Where-Object { $_ -match "^[^#=]+=" } | ForEach-Object {
    $name, $value = $_ -split '=', 2
    $value = $value.Trim('"').Trim("'")
    [Environment]::SetEnvironmentVariable($name, $value, "Process")
}
npx -y n8n
