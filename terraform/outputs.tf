output "sqs_queue_url" {
  description = "Paste into backend .env as SQS_QUEUE_URL"
  value       = aws_sqs_queue.emet_fact_check.url
}

output "sqs_queue_arn" {
  description = "Attach to IAM policies for API / worker send + receive."
  value       = aws_sqs_queue.emet_fact_check.arn
}

output "sqs_dlq_url" {
  value = aws_sqs_queue.emet_fact_check_dlq.url
}

output "cloudfront_url" {
  description = "HTTPS URL for the static frontend — paste into CLOUDFRONT_URL / CORS_ORIGINS."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "Use with aws cloudfront create-invalidation after deploy."
  value       = aws_cloudfront_distribution.frontend.id
}

output "s3_bucket_name" {
  description = "Sync Next static export: aws s3 sync out/ s3://THIS_BUCKET --delete"
  value       = aws_s3_bucket.frontend.bucket
}

output "s3_bucket_arn" {
  value = aws_s3_bucket.frontend.arn
}
