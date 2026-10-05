variable "aws_region" {
  description = "AWS region for the lab instance."
  type        = string
  default     = "ap-southeast-1"
}

variable "instance_type" {
  description = "EC2 instance type used by the monitored lab host."
  type        = string
  default     = "t3.micro"
}

variable "monitoring_cidr" {
  description = "Public IP/CIDR of the K3s monitoring host allowed to scrape node_exporter."
  type        = string

  validation {
    condition     = can(cidrhost(var.monitoring_cidr, 0)) && var.monitoring_cidr != "0.0.0.0/0"
    error_message = "monitoring_cidr must be a valid, restricted IPv4 CIDR and cannot be 0.0.0.0/0."
  }
}

variable "name" {
  description = "Name prefix for AWS lab resources."
  type        = string
  default     = "cloud-ops-lab"
}

