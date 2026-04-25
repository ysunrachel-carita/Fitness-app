output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "db_endpoint" {
  value = local.db_endpoint
}
