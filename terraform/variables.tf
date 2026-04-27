variable "project_name" {
  type        = string
  description = "Prefix for resource names (e.g. emet-capstone)."
  default     = "emet"
}

variable "aws_region" {
  type        = string
  description = "AWS region (must match backend AWS_REGION / boto3)."
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Deployment stage label (dev, staging, prod)."
  default     = "dev"
}

variable "sqs_visibility_timeout_seconds" {
  type        = number
  description = "Must exceed worst-case fact-check worker duration."
  default     = 960 # 16 minutes
}

variable "sqs_message_retention_seconds" {
  type    = number
  default = 1209600 # 14 days
}

variable "tags" {
  type        = map(string)
  description = "Extra tags merged onto all resources."
  default     = {}
}
