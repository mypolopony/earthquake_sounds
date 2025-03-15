provider "aws" {
  region = "us-west-1"
}

##################################
# Networking and Security Groups #
##################################

# Create a VPC for AWS MSK
resource "aws_vpc" "msk_vpc" {
  cidr_block = "10.0.0.0/16"

  enable_dns_support   = true
  enable_dns_hostnames = true
}

# Create Private Subnets for MSK Brokers (spread across 2 AZs)
resource "aws_subnet" "msk_subnet_1" {
  vpc_id            = aws_vpc.msk_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-west-1b"
}

resource "aws_subnet" "msk_subnet_2" {
  vpc_id            = aws_vpc.msk_vpc.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "us-west-1c"
}

# Create a Security Group for MSK
resource "aws_security_group" "msk_sg" {
  vpc_id = aws_vpc.msk_vpc.id
  name   = "msk-security-group"

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1" # Allow ALL ports
    cidr_blocks = ["10.0.0.0/16"]
  }

  # Fully open outbound traffic (All protocols)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1" # Allow ALL ports
    cidr_blocks = ["10.0.0.0/16"]
  }
}

# VPN Security Group
resource "aws_security_group" "vpn_security_group" {
  name        = "vpn-security-group"
  description = "Security group for AWS Client VPN"
  vpc_id      = aws_vpc.msk_vpc.id

  # Allow inbound VPN client traffic
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow VPN clients to communicate with VPC resources
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["192.168.0.0/22"] # Allow all traffic within VPN
  }

  # Allow outbound traffic to VPC
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "vpn-security-group"
  }
}

# VPN Endpoint
resource "aws_ec2_client_vpn_endpoint" "vpn" {
  description            = "My Client VPN Endpoint"
  vpc_id                 = aws_vpc.msk_vpc.id
  client_cidr_block      = "192.168.0.0/22"
  server_certificate_arn = "arn:aws:acm:us-west-1:897729117324:certificate/c2ba7fb0-2b43-4c40-9e03-418d4fcb5485"

  authentication_options {
    type                       = "certificate-authentication"
    root_certificate_chain_arn = "arn:aws:acm:us-west-1:897729117324:certificate/c2ba7fb0-2b43-4c40-9e03-418d4fcb5485"
  }

  connection_log_options {
    enabled = false
  }

  security_group_ids = [aws_security_group.vpn_security_group.id] # Attach VPN SG

  dns_servers = ["10.0.0.2"]

  split_tunnel = true
}

# Only route 10.* traffic via VPN
#resource "aws_ec2_client_vpn_route" "vpn_route_vpc" {
#  client_vpn_endpoint_id = aws_ec2_client_vpn_endpoint.vpn.id
#  destination_cidr_block = "10.0.0.0/16"
#  target_vpc_subnet_id   = aws_subnet.msk_subnet_1.id
#}

# Associate VPN with Subnet
resource "aws_ec2_client_vpn_network_association" "vpn_association" {
  client_vpn_endpoint_id = aws_ec2_client_vpn_endpoint.vpn.id
  subnet_id              = aws_subnet.msk_subnet_1.id
}

# Authorize VPN Clients to Access VPC
resource "aws_ec2_client_vpn_authorization_rule" "vpn_auth" {
  client_vpn_endpoint_id = aws_ec2_client_vpn_endpoint.vpn.id
  target_network_cidr    = "10.0.0.0/16" # Allow access to the entire VPC
  authorize_all_groups   = true          # Authorize all users (restrict if needed)
}

# Internet Gateway (IGW) for external traffic
resource "aws_internet_gateway" "vpn_igw" {
  vpc_id = aws_vpc.msk_vpc.id
  tags = {
    Name = "vpn-internet-gateway"
  }
}

# VPN Return Route 
#resource "aws_route" "vpn_return_route" {
#  route_table_id         = aws_route_table.private_route_table.id
#  destination_cidr_block = "192.168.0.0/22"
#  network_interface_id   = "eni-02b4b949e110c5c86" # VPN ENI ID (found via console)
#}

# Public subnet
resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.msk_vpc.id
  cidr_block              = "10.0.3.0/24" # A new subnet outside your private range
  map_public_ip_on_launch = true
  availability_zone       = "us-west-1b"
}

# Route Table for Public Subnet
resource "aws_route_table" "public_route_table" {
  vpc_id = aws_vpc.msk_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.vpn_igw.id
  }

  tags = {
    Name = "public-route-table"
  }
}

# Route table for Private Subnets
resource "aws_route_table" "private_route_table" {
  vpc_id = aws_vpc.msk_vpc.id
  tags = {
    Name = "private-route-table"
  }
}

# Associate Private Subnets to Private Route Table
resource "aws_route_table_association" "private_subnet_1_assoc" {
  subnet_id      = aws_subnet.msk_subnet_1.id
  route_table_id = aws_route_table.private_route_table.id
}
resource "aws_route_table_association" "private_subnet_2_assoc" {
  subnet_id      = aws_subnet.msk_subnet_2.id
  route_table_id = aws_route_table.private_route_table.id
}

# Associate Public subnet with Public Route Table
resource "aws_route_table_association" "public_subnet_association" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_route_table.id
}


# NAT Gateway
resource "aws_nat_gateway" "vpn_nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public_subnet.id # PUBLIC subnet
}
resource "aws_eip" "nat" {
  domain = "vpc"
}

# Route traffic to the NAT Gateway
resource "aws_route" "private_nat_route" {
  route_table_id         = aws_route_table.private_route_table.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.vpn_nat.id
}

############# 
# MSK Setup #
#############

# Main resource
resource "aws_msk_cluster" "msk_snowflake" {
  cluster_name           = "snowflake-msk"
  kafka_version          = "3.3.1"
  number_of_broker_nodes = 2 # Reduce brokers to save cost

  broker_node_group_info {
    instance_type   = "kafka.t3.small" # Use smallest instance for cost efficiency
    client_subnets  = [aws_subnet.msk_subnet_1.id, aws_subnet.msk_subnet_2.id]
    security_groups = [aws_security_group.msk_sg.id]

    storage_info {
      ebs_storage_info {
        volume_size = 100 # Minimum storage for cost optimization
      }
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.msk_config.arn
    revision = aws_msk_configuration.msk_config.latest_revision
  }
}

# Ensure MSK is deployed with private DNS
resource "aws_msk_configuration" "msk_config" {
  name           = "msk-private-dns"
  kafka_versions = ["3.3.1"]

  server_properties = <<PROPERTIES
auto.create.topics.enable = true
default.replication.factor = 2
num.partitions = 3
PROPERTIES
}

# Broker Connection Details
output "msk_bootstrap_brokers" {
  value = aws_msk_cluster.msk_snowflake.bootstrap_brokers
}

###############
# Kafka Topic #
###############

# Secret for Kafka Admin
#resource "aws_msk_scram_secret_association" "msk_snowflake_secret" {
#  cluster_arn = aws_msk_cluster.msk_snowflake.arn
#  secret_arn  = aws_secretsmanager_secret.msk_admin_secret.arn
#}

# Create Kafka Topic
# resource "null_resource" "create_kafka_topic" {
#  provisioner "local-exec" {
#    command = <<EOT
#      kafka-topics --create \
#      --topic obspy-snowflake \
#      --bootstrap-server ${aws_msk_cluster.msk_snowflake.bootstrap_brokers} \
#      --partitions 3 --replication-factor 2
#    EOT
#  }
#}

############
# IAM Role #
############

# IAM Role for Snowflake Kafka Connector
resource "aws_iam_role" "snowflake_kafka_connector_role" {
  name = "snowflake-kafka-connector-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "kafka.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# IAM Policy for Snowflake Kafka Connector
resource "aws_iam_policy" "snowflake_kafka_policy" {
  name        = "snowflake-kafka-policy"
  description = "Permissions for Kafka to stream to Snowflake"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = "arn:aws:s3:::kafka-snowflake-backup/*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:PutLogEvents", "logs:CreateLogStream", "logs:DescribeLogStreams"]
        Resource = "*"
      }
    ]
  })
}

# Attach the policy to the role
resource "aws_iam_role_policy_attachment" "attach_snowflake_kafka_policy" {
  role       = aws_iam_role.snowflake_kafka_connector_role.name
  policy_arn = aws_iam_policy.snowflake_kafka_policy.arn
}
