resource "aws_db_subnet_group" "db_subnets" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.public.id, aws_subnet.public_backup.id] # RDS requires at least 2 subnets
}

# We need a second subnet just for RDS requirements, even if we don't use it for compute
resource "aws_subnet" "public_backup" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = data.aws_availability_zones.available.names[1]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-backup"
  }
}

resource "aws_security_group" "db_sg" {
  name   = "${var.project_name}-db-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier            = "${var.project_name}-db"
  engine                = "postgres"
  engine_version        = "15"
  instance_class        = "db.t3.micro" # Free Tier eligible
  allocated_storage     = 20           # Free Tier eligible
  db_name               = "fitness_db"
  username              = var.db_username
  password              = var.db_password
  db_subnet_group_name  = aws_db_subnet_group.db_subnets.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  skip_final_snapshot   = true
  publicly_accessible   = false
}
