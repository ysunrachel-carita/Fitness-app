variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "fitness-app"
}

variable "db_type" {
  description = "Type of database to deploy: 'rds' or 'aurora'"
  default     = "rds"
}

variable "db_username" {
  default = "fitness_admin"
}

variable "db_password" {
  description = "Database password (should be provided via environment variable or secret)"
  sensitive   = true
}

variable "container_image" {
  description = "The ECR image URL"
  default     = ""
}
