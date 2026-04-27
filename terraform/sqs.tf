# FIFO not required — single consumer worker pattern per capstone.

resource "aws_sqs_queue" "emet_fact_check_dlq" {
  name                      = "${var.project_name}-${var.environment}-fact-check-dlq"
  message_retention_seconds = var.sqs_message_retention_seconds

  sqs_managed_sse_enabled = true
}

resource "aws_sqs_queue" "emet_fact_check" {
  name                       = "${var.project_name}-${var.environment}-fact-check-jobs"
  visibility_timeout_seconds = var.sqs_visibility_timeout_seconds
  message_retention_seconds  = var.sqs_message_retention_seconds

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.emet_fact_check_dlq.arn
    maxReceiveCount     = 5
  })

  sqs_managed_sse_enabled = true
}
