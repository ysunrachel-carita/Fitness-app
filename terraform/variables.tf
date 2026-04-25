variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "fitness-app"
}

variable "db_username" {
  default = "fitness_admin"
}

variable "db_password" {
  description = "Database password"
  sensitive   = true
}

variable "container_image" {
  description = "The ECR image URL"
}

variable "ssh_public_key" {
  description = "Optional SSH public key for EC2 access"
  default     = ""
}
