output "app_public_ip" {
  value = aws_eip.app_eip.public_ip
}

output "app_url" {
  value = "http://${aws_eip.app_eip.public_ip}"
}

output "db_endpoint" {
  value = aws_db_instance.postgres.endpoint
}
