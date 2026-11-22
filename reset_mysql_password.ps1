# reset_mysql_password.ps1
# Run this in PowerShell as Administrator
# It resets the MySQL root password to: root123

$mysqlBin  = "C:\Program Files\MySQL\MySQL Server 8.0\bin"
$initFile  = "$env:TEMP\mysql_init.sql"

# Write the password reset command to a temp file
"ALTER USER 'root'@'localhost' IDENTIFIED BY 'root123';" | Out-File -FilePath $initFile -Encoding ASCII

Write-Host "Stopping MySQL service..." -ForegroundColor Yellow
net stop MySQL80 2>&1 | Out-Null

Write-Host "Starting MySQL with init file to reset password..." -ForegroundColor Yellow
$proc = Start-Process -FilePath "$mysqlBin\mysqld.exe" `
    -ArgumentList "--init-file=$initFile", "--console" `
    -PassThru -WindowStyle Hidden

Write-Host "Waiting for MySQL to apply the reset (10 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "Stopping temporary MySQL instance..." -ForegroundColor Yellow
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

Write-Host "Starting MySQL service normally..." -ForegroundColor Yellow
net start MySQL80 2>&1 | Out-Null
Start-Sleep -Seconds 3

Write-Host "Testing new password (root123)..." -ForegroundColor Yellow
$result = & "$mysqlBin\mysql.exe" -u root -proot123 --connect-timeout=5 -e "SELECT 'Password reset SUCCESS';" 2>&1

if ($result -match "SUCCESS") {
    Write-Host ""
    Write-Host "SUCCESS! MySQL root password has been reset to: root123" -ForegroundColor Green
    Write-Host "You can close this window now." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Could not verify. Output: $result" -ForegroundColor Red
    Write-Host "Try running: mysql -u root -proot123 -e ""SELECT 1;"" to test manually." -ForegroundColor Yellow
}

# Clean up temp file
Remove-Item $initFile -ErrorAction SilentlyContinue
