# Security Group for DB
resource "aws_security_group" "db_sg" {
  name        = "${var.project_name}-db-sg"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- RDS Instance (Postgres) ---
resource "aws_db_instance" "postgres" {
  count                  = var.db_type == "rds" ? 1 : 0
  identifier            = "${var.project_name}-db"
  engine                = "postgres"
  engine_version        = "15"
  instance_class        = "db.t3.micro"
  allocated_storage     = 20
  db_name               = "fitness_db"
  username              = var.db_username
  password              = var.db_password
  db_subnet_group_name  = aws_db_subnet_group.db_subnets.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  skip_final_snapshot   = true
}

# --- Aurora Cluster (Postgres) ---
resource "aws_rds_cluster" "aurora" {
  count                  = var.db_type == "aurora" ? 1 : 0
  cluster_identifier     = "${var.project_name}-aurora-cluster"
  engine                 = "aurora-postgresql"
  engine_version         = "15.3"
  database_name          = "fitness_db"
  master_username        = var.db_username
  master_password        = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.db_subnets.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  skip_final_snapshot    = true
}

resource "aws_rds_cluster_instance" "aurora_instances" {
  count              = var.db_type == "aurora" ? 1 : 0
  identifier         = "${var.project_name}-aurora-instance"
  cluster_identifier = aws_rds_cluster.aurora[0].id
  instance_class     = "db.t3.medium" # Aurora has higher min requirements
  engine             = aws_rds_cluster.aurora[0].engine
  engine_version     = aws_rds_cluster.aurora[0].engine_version
}

resource "aws_db_subnet_group" "db_subnets" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}
