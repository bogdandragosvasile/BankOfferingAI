# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------
variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Deployment environment (staging / prod)"
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "prod"], var.environment)
    error_message = "environment must be 'staging' or 'prod'."
  }
}

variable "cluster_name" {
  description = "Name of the EKS cluster and resource prefix"
  type        = string
  default     = "bankoffer"
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# ---------------------------------------------------------------------------
# EKS
# ---------------------------------------------------------------------------
variable "eks_cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.29"
}

variable "node_instance_types" {
  description = "EC2 instance types for the managed node group"
  type        = list(string)
  default     = ["m6i.xlarge"]
}

variable "node_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 3
}

variable "node_min_size" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 6
}

# ---------------------------------------------------------------------------
# RDS
# ---------------------------------------------------------------------------
variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_name" {
  description = "Name of the initial PostgreSQL database"
  type        = string
  default     = "bankoffer"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "bankoffer_admin"
  sensitive   = true
}

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16.2"
}

# ---------------------------------------------------------------------------
# MSK (Kafka)
# ---------------------------------------------------------------------------
variable "kafka_version" {
  description = "Apache Kafka version for MSK"
  type        = string
  default     = "3.6.0"
}

variable "kafka_instance_type" {
  description = "MSK broker instance type"
  type        = string
  default     = "kafka.t3.small"
}

variable "kafka_number_of_brokers" {
  description = "Number of Kafka broker nodes (must be a multiple of AZs)"
  type        = number
  default     = 3
}

variable "kafka_ebs_volume_size" {
  description = "EBS volume size in GiB per broker"
  type        = number
  default     = 100
}
