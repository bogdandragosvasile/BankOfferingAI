output "eks_cluster_endpoint" {
  description = "EKS cluster API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "eks_cluster_certificate_authority" {
  description = "Base64-encoded certificate data for the EKS cluster"
  value       = module.eks.cluster_certificate_authority
  sensitive   = true
}

output "rds_endpoint" {
  description = "RDS PostgreSQL connection endpoint"
  value       = module.rds.db_endpoint
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = module.rds.db_port
}

output "kafka_bootstrap_servers" {
  description = "MSK bootstrap broker connection string (TLS)"
  value       = module.kafka.bootstrap_brokers_tls
}

output "kafka_zookeeper_connect" {
  description = "MSK Zookeeper connection string"
  value       = module.kafka.zookeeper_connect
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}
